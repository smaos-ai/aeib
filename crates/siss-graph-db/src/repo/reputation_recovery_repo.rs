use sqlx::{PgPool, Uuid};
use chrono::{DateTime, Utc, Duration};

#[derive(Debug, Clone, sqlx::FromRow)]
pub struct RepuationRecoveryRecord {
    pub id: Uuid,
    pub sovereign_id: Uuid,
    pub recovery_started_at: DateTime<Utc>,
    pub score_at_entry: i16,
    pub probation_exit_reason: String,
    pub recovery_window_weeks: i32,
    pub recovery_progress_weeks: i32,
    pub last_progress_update_at: DateTime<Utc>,
    pub slashes_during_recovery: i32,
    pub anomalies_during_recovery: i32,
    pub settlement_bonus_during_recovery: i32,
    pub score_adjustments_applied: i32,
    pub recovery_completed_at: Option<DateTime<Utc>>,
    pub recovery_exit_status: Option<String>,
    pub score_at_exit: Option<i16>,
}

/// Pure function: Compute recovered base score from weeks elapsed
/// Formula: 85 + (weeks / 8) × 15, clamped to [85, 100]
pub fn recovered_base_score(weeks_elapsed: u32) -> i16 {
    let progress = std::cmp::min(weeks_elapsed, 8) as i16;
    85 + (progress * 15) / 8
}

/// Pure function: Compute final recovery score (base + Phase 19 signals)
pub fn compute_recovery_score(
    weeks_elapsed: u32,
    slash_count: i64,
    anomaly_count: i64,
    settled_count: i64,
) -> i16 {
    let base = recovered_base_score(weeks_elapsed);

    // Reuse Phase 19 penalty/bonus functions (imported from peer_scoring_repo)
    let slash_penalty = std::cmp::min(30, (slash_count * 10) as i16);
    let anomaly_penalty = std::cmp::min(20, (anomaly_count * 8) as i16);
    let settlement_bonus = std::cmp::min(20, (settled_count * 5) as i16);

    let score = (base as i32 - slash_penalty as i32 - anomaly_penalty as i32
        + settlement_bonus as i32) as i16;
    score.clamp(0, 100)
}

/// Pure function: Calculate weeks elapsed since recovery started
pub fn weeks_elapsed(recovery_started_at: DateTime<Utc>) -> u32 {
    let elapsed = Utc::now() - recovery_started_at;
    (elapsed.num_days() / 7) as u32
}

/// Auto-transition probation → recovery (triggered by Phase 16 sweep)
pub async fn auto_exit_probation_to_recovery(
    pool: &PgPool,
    sovereign_id: Uuid,
    exit_reason: &str, // 'clean_30_days', 'manual_override', 'appeal_success'
) -> Result<Uuid, sqlx::Error> {
    let recovery_id = Uuid::new_v4();

    // Compute entry score (current peer_scoring)
    let score_at_entry: i16 = sqlx::query_scalar(
        "SELECT score FROM peer_scoring WHERE sovereign_id = $1"
    )
    .bind(sovereign_id)
    .fetch_one(pool)
    .await?;

    // Insert recovery_log record
    sqlx::query(
        "INSERT INTO reputation_recovery_log
         (id, sovereign_id, score_at_entry, probation_exit_reason, recovery_progress_weeks)
         VALUES ($1, $2, $3, $4, $5)"
    )
    .bind(recovery_id)
    .bind(sovereign_id)
    .bind(score_at_entry)
    .bind(exit_reason)
    .bind(0)
    .execute(pool)
    .await?;

    // Transition sovereigns.status → 'recovering'
    sqlx::query("UPDATE sovereigns SET status = 'recovering' WHERE id = $1")
        .bind(sovereign_id)
        .execute(pool)
        .await?;

    Ok(recovery_id)
}

/// Weekly sweep: advance recovery progress, check for completion
pub async fn sweep_recovery_progress(pool: &PgPool) -> Result<SweepResult, sqlx::Error> {
    let mut advanced = 0;
    let mut completed = 0;

    // Fetch all active recovery records
    let records: Vec<RepuationRecoveryRecord> = sqlx::query_as(
        "SELECT * FROM reputation_recovery_log WHERE recovery_exit_status IS NULL"
    )
    .fetch_all(pool)
    .await?;

    for record in records {
        let weeks = weeks_elapsed(record.recovery_started_at);

        // Update progress
        sqlx::query(
            "UPDATE reputation_recovery_log
             SET recovery_progress_weeks = $1, last_progress_update_at = NOW()
             WHERE id = $2"
        )
        .bind(weeks as i32)
        .bind(record.id)
        .execute(pool)
        .await?;

        advanced += 1;

        // Check for completion (8+ weeks)
        if weeks >= 8 {
            // Auto-transition to active
            let _ = auto_exit_recovery_to_active(pool, record.sovereign_id).await;
            completed += 1;
        }
    }

    Ok(SweepResult {
        sovereigns_advanced: advanced,
        sovereigns_completed: completed,
        sovereigns_violated: 0,
    })
}

/// Auto-transition recovery → active (success, called by sweep at week 8)
pub async fn auto_exit_recovery_to_active(
    pool: &PgPool,
    sovereign_id: Uuid,
) -> Result<(), sqlx::Error> {
    // Compute final score
    let final_score: i16 = sqlx::query_scalar(
        "SELECT score FROM peer_scoring WHERE sovereign_id = $1"
    )
    .bind(sovereign_id)
    .fetch_one(pool)
    .await?;

    // Mark recovery as complete
    sqlx::query(
        "UPDATE reputation_recovery_log
         SET recovery_completed_at = NOW(), recovery_exit_status = 'success', score_at_exit = $1
         WHERE sovereign_id = $2 AND recovery_exit_status IS NULL"
    )
    .bind(final_score)
    .bind(sovereign_id)
    .execute(pool)
    .await?;

    // Transition sovereigns.status → 'active'
    sqlx::query("UPDATE sovereigns SET status = 'active' WHERE id = $1")
        .bind(sovereign_id)
        .execute(pool)
        .await?;

    Ok(())
}

/// Immediate re-quarantine on violation (called by gatekeeper)
pub async fn violation_during_recovery_to_quarantine(
    pool: &PgPool,
    sovereign_id: Uuid,
    violation_reason: &str,
) -> Result<(), sqlx::Error> {
    // Mark recovery as failed
    sqlx::query(
        "UPDATE reputation_recovery_log
         SET recovery_completed_at = NOW(), recovery_exit_status = 'failure'
         WHERE sovereign_id = $1 AND recovery_exit_status IS NULL"
    )
    .bind(sovereign_id)
    .execute(pool)
    .await?;

    // Transition sovereigns.status → 'quarantined' (IMMEDIATE, NO APPEAL COOLDOWN)
    sqlx::query("UPDATE sovereigns SET status = 'quarantined' WHERE id = $1")
        .bind(sovereign_id)
        .execute(pool)
        .await?;

    Ok(())
}

/// Get active recovery record for scoring (called by peer_scoring_repo)
pub async fn get_active_recovery(
    pool: &PgPool,
    sovereign_id: Uuid,
) -> Result<Option<RepuationRecoveryRecord>, sqlx::Error> {
    sqlx::query_as(
        "SELECT * FROM reputation_recovery_log
         WHERE sovereign_id = $1 AND recovery_exit_status IS NULL
         ORDER BY recovery_started_at DESC LIMIT 1"
    )
    .bind(sovereign_id)
    .fetch_optional(pool)
    .await
}

#[derive(Debug, Clone)]
pub struct SweepResult {
    pub sovereigns_advanced: i32,
    pub sovereigns_completed: i32,
    pub sovereigns_violated: i32,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_recovered_base_score_week_0() {
        assert_eq!(recovered_base_score(0), 85);
    }

    #[test]
    fn test_recovered_base_score_week_4() {
        assert_eq!(recovered_base_score(4), 92);
    }

    #[test]
    fn test_recovered_base_score_week_8() {
        assert_eq!(recovered_base_score(8), 100);
    }

    #[test]
    fn test_recovered_base_score_capped_at_100() {
        assert_eq!(recovered_base_score(16), 100);
    }

    #[test]
    fn test_recovery_score_clean_week_0() {
        let score = compute_recovery_score(0, 0, 0, 0);
        assert_eq!(score, 85);
    }

    #[test]
    fn test_recovery_score_with_slashes() {
        let score = compute_recovery_score(0, 2, 0, 0);
        assert_eq!(score, 85 - 20);
    }

    #[test]
    fn test_recovery_score_with_settlement_bonus() {
        let score = compute_recovery_score(0, 0, 0, 3);
        assert_eq!(score, 85 + 15);
    }

    #[test]
    fn test_recovery_score_clamped_to_100() {
        let score = compute_recovery_score(8, 0, 0, 10);
        assert_eq!(score, 100);
    }

    #[test]
    fn test_weeks_elapsed_now() {
        let weeks = weeks_elapsed(Utc::now());
        assert_eq!(weeks, 0);
    }

    #[test]
    fn test_weeks_elapsed_7_days_ago() {
        let start = Utc::now() - Duration::days(7);
        let weeks = weeks_elapsed(start);
        assert_eq!(weeks, 1);
    }
}
