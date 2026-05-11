use crate::repo::reputation_recovery_repo;
use sqlx::PgPool;
use uuid::Uuid;

/// Map sovereign status to health score (0–100)
fn status_to_score(status: &str) -> i16 {
    match status {
        "active" => 100,
        "probation" => 80,
        "quarantined" => 0,
        _ => 50, // unknown
    }
}

// ============================================================================
// Phase 19: Multi-Dimensional Peer Scoring
// ============================================================================

/// Compute slash penalty from count of recent slash events (30 days).
/// Formula: min(30, count * 10)
pub fn slash_penalty_from_count(count: i64) -> i16 {
    std::cmp::min(30, (count * 10) as i16)
}

/// Compute anomaly penalty from count of recent high/critical anomalies (30 days).
/// Formula: min(20, count * 8)
pub fn anomaly_penalty_from_count(count: i64) -> i16 {
    std::cmp::min(20, (count * 8) as i16)
}

/// Compute settlement bonus from count of settled invoices (all-time).
/// Formula: min(20, count * 5)
pub fn settlement_bonus_from_count(count: i64) -> i16 {
    std::cmp::min(20, (count * 5) as i16)
}

/// Compute final enriched score from base + signal adjustments.
/// Formula: clamp(base - slash_penalty - anomaly_penalty + settlement_bonus, 0, 100)
pub fn compute_enriched_score(
    base: i16,
    slash_count: i64,
    anomaly_count: i64,
    settled_count: i64,
) -> i16 {
    if base == 0 {
        // Quarantined sovereigns always score 0; no adjustments
        return 0;
    }

    let slash_penalty = slash_penalty_from_count(slash_count);
    let anomaly_penalty = anomaly_penalty_from_count(anomaly_count);
    let settlement_bonus = settlement_bonus_from_count(settled_count);

    let score = (base as i32 - slash_penalty as i32 - anomaly_penalty as i32
        + settlement_bonus as i32) as i16;
    score.clamp(0, 100)
}

/// Compute score for a sovereign using multi-dimensional enriched scoring and upsert to peer_scoring.
///
/// Handles four statuses:
/// - recovering: Phase 20 graduated base (85 + weeks/8*15) + Phase 19 signals
/// - active: Phase 19 base (100) + signals
/// - probation: Phase 19 base (80) + signals
/// - quarantined: Always 0 (no enrichment)
pub async fn compute_and_upsert_score(
    pool: &PgPool,
    sovereign_id: Uuid,
) -> Result<i16, sqlx::Error> {
    // Fetch sovereign's status
    let status: Option<String> = sqlx::query_scalar("SELECT status FROM sovereigns WHERE id = $1")
        .bind(sovereign_id)
        .fetch_optional(pool)
        .await?
        .flatten();

    let status = status.unwrap_or_else(|| "unknown".to_string());

    // Fetch signal counts (needed for all non-quarantined statuses)
    let slash_count: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM slashing_events
         WHERE sovereign_id = $1 AND slashed_at >= NOW() - INTERVAL '30 days'",
    )
    .bind(sovereign_id)
    .fetch_one(pool)
    .await?;

    let anomaly_count: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM behavioral_anomalies
         WHERE sovereign_id = $1 AND severity IN ('high', 'critical')
         AND detected_at >= NOW() - INTERVAL '30 days'",
    )
    .bind(sovereign_id)
    .fetch_one(pool)
    .await?;

    let settled_count: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM settlement_invoices
         WHERE debtor_sovereign_id = $1 AND status = 'settled'",
    )
    .bind(sovereign_id)
    .fetch_one(pool)
    .await?;

    // Compute score based on status
    let score = match status.as_str() {
        "recovering" => {
            // Phase 20: Graduated recovery + Phase 19 signals
            if let Ok(Some(recovery)) =
                reputation_recovery_repo::get_active_recovery(pool, sovereign_id).await
            {
                let weeks = reputation_recovery_repo::weeks_elapsed(recovery.recovery_started_at);
                reputation_recovery_repo::compute_recovery_score(
                    weeks,
                    slash_count,
                    anomaly_count,
                    settled_count,
                )
            } else {
                // Stale status; shouldn't happen but fallback to unknown
                50
            }
        }
        "active" => {
            // Phase 19: Active base (100) + signals
            compute_enriched_score(100, slash_count, anomaly_count, settled_count)
        }
        "probation" => {
            // Phase 19: Probation base (80) + signals
            compute_enriched_score(80, slash_count, anomaly_count, settled_count)
        }
        "quarantined" => {
            // Always 0; no enrichment
            0
        }
        _ => {
            // Unknown status
            50
        }
    };

    // Upsert peer_scoring
    sqlx::query(
        "INSERT INTO peer_scoring (sovereign_id, score, health_status, computed_at)
         VALUES ($1, $2, $3, NOW())
         ON CONFLICT (sovereign_id) DO UPDATE
         SET score = EXCLUDED.score, health_status = EXCLUDED.health_status, computed_at = NOW()",
    )
    .bind(sovereign_id)
    .bind(score)
    .bind(&status)
    .execute(pool)
    .await?;

    Ok(score)
}

/// Run one sweep pass: compute scores for all sovereigns
pub async fn run_scoring_pass(pool: &PgPool) -> Result<u64, sqlx::Error> {
    let sovereigns: Vec<Uuid> = sqlx::query_scalar("SELECT id FROM sovereigns")
        .fetch_all(pool)
        .await?;

    let mut count = 0u64;
    for sovereign_id in sovereigns {
        if compute_and_upsert_score(pool, sovereign_id).await.is_ok() {
            count += 1;
        }
    }

    Ok(count)
}

/// Start background scoring sweep
pub fn start_peer_scoring_sweep(
    pool: PgPool,
    interval: std::time::Duration,
) -> tokio::task::JoinHandle<()> {
    tokio::spawn(async move {
        let mut ticker = tokio::time::interval(interval);
        loop {
            ticker.tick().await;
            let _ = run_scoring_pass(&pool).await;
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_peer_score_active_is_100() {
        let score = status_to_score("active");
        assert_eq!(score, 100, "active status should score 100");
    }

    #[test]
    fn test_peer_score_probation_is_80() {
        let score = status_to_score("probation");
        assert_eq!(score, 80, "probation status should score 80");
    }

    #[test]
    fn test_peer_score_quarantined_is_0() {
        let score = status_to_score("quarantined");
        assert_eq!(score, 0, "quarantined status should score 0");
    }

    // ============================================================================
    // Phase 19: Multi-dimensional scoring unit tests (no DB, pure functions)
    // ============================================================================

    #[test]
    fn test_slash_penalty_zero_slashes() {
        let penalty = slash_penalty_from_count(0);
        assert_eq!(penalty, 0, "zero slashes should produce zero penalty");
    }

    #[test]
    fn test_slash_penalty_three_slashes() {
        let penalty = slash_penalty_from_count(3);
        assert_eq!(
            penalty, 30,
            "three slashes (3 * 10) should produce 30 penalty, capped at 30"
        );
    }

    #[test]
    fn test_slash_penalty_caps_at_30() {
        let penalty = slash_penalty_from_count(10);
        assert_eq!(penalty, 30, "penalty should cap at 30 regardless of count");
    }

    #[test]
    fn test_anomaly_penalty_zero() {
        let penalty = anomaly_penalty_from_count(0);
        assert_eq!(penalty, 0, "zero anomalies should produce zero penalty");
    }

    #[test]
    fn test_anomaly_penalty_caps_at_20() {
        let penalty = anomaly_penalty_from_count(5);
        assert_eq!(
            penalty, 20,
            "five anomalies (5 * 8 = 40, capped) should produce 20 penalty"
        );
    }

    #[test]
    fn test_settlement_bonus_zero() {
        let bonus = settlement_bonus_from_count(0);
        assert_eq!(bonus, 0, "zero settled invoices should produce zero bonus");
    }

    #[test]
    fn test_settlement_bonus_caps_at_20() {
        let bonus = settlement_bonus_from_count(10);
        assert_eq!(
            bonus, 20,
            "ten invoices (10 * 5 = 50, capped) should produce 20 bonus"
        );
    }

    #[test]
    fn test_enriched_score_active_with_two_slashes() {
        let score = compute_enriched_score(100, 2, 0, 0);
        assert_eq!(score, 80, "active (100) - 2 slashes (20) = 80");
    }

    #[test]
    fn test_enriched_score_quarantined_is_always_0() {
        let score = compute_enriched_score(0, 0, 0, 100);
        assert_eq!(
            score, 0,
            "quarantined (base=0) should always score 0, ignoring all bonuses"
        );
    }

    #[test]
    fn test_enriched_score_bonus_caps_at_100() {
        let score = compute_enriched_score(100, 0, 0, 5);
        assert_eq!(score, 100, "base (100) + bonus (20) should clamp to 100");
    }

    #[test]
    fn test_enriched_score_probation_with_slash() {
        let score = compute_enriched_score(80, 1, 0, 0);
        assert_eq!(score, 70, "probation (80) - 1 slash (10) = 70");
    }
}
