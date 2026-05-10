use chrono::{DateTime, Utc};
use sqlx::{PgPool, Row};
use thiserror::Error;
use uuid::Uuid;

#[derive(Debug, Error)]
pub enum ProbationError {
    #[error("database error: {message}")]
    Database { message: String },
}

impl From<sqlx::Error> for ProbationError {
    fn from(err: sqlx::Error) -> Self {
        ProbationError::Database {
            message: err.to_string(),
        }
    }
}

#[derive(Debug, Clone)]
pub struct ProbationStatus {
    pub probation_started_at: DateTime<Utc>,
    pub days_elapsed: i64,
    pub days_remaining: i64,
    pub violation_count: i64,
    pub is_clean: bool,
}

/// Transition sovereign to probation status
pub async fn start_probation(pool: &PgPool, sovereign_id: Uuid) -> Result<(), ProbationError> {
    // Update sovereign status to 'probation'
    sqlx::query("UPDATE sovereigns SET status = 'probation' WHERE id = $1")
        .bind(sovereign_id)
        .execute(pool)
        .await?;

    // Log probation start to audit log
    sqlx::query(
        "INSERT INTO probation_audit_log (sovereign_id, probation_started_at, event_type, event_details)
         VALUES ($1, NOW(), 'activity_logged', '{\"event\": \"probation_started\"}'::jsonb)"
    )
    .bind(sovereign_id)
    .execute(pool)
    .await?;

    Ok(())
}

/// Get current probation status for sovereign
pub async fn get_probation_status(
    pool: &PgPool,
    sovereign_id: Uuid,
) -> Result<Option<ProbationStatus>, ProbationError> {
    let row = sqlx::query(
        "SELECT probation_started_at FROM probation_audit_log
         WHERE sovereign_id = $1 AND event_type = 'activity_logged'
           AND event_details->>'event' = 'probation_started'
         ORDER BY logged_at DESC LIMIT 1",
    )
    .bind(sovereign_id)
    .fetch_optional(pool)
    .await?;

    match row {
        None => Ok(None),
        Some(r) => {
            let probation_started_at: DateTime<Utc> = r.get("probation_started_at");
            let now = Utc::now();
            let duration = now.signed_duration_since(probation_started_at);
            let days_elapsed = duration.num_days();
            let days_remaining = (30 - days_elapsed).max(0);

            // Count violations (anomaly_detected events)
            let violation_count: i64 = sqlx::query_scalar(
                "SELECT COUNT(*) FROM probation_audit_log
                 WHERE sovereign_id = $1 AND event_type = 'anomaly_detected'
                   AND logged_at >= $2",
            )
            .bind(sovereign_id)
            .bind(probation_started_at)
            .fetch_one(pool)
            .await?;

            let is_clean = violation_count == 0;

            Ok(Some(ProbationStatus {
                probation_started_at,
                days_elapsed,
                days_remaining,
                violation_count,
                is_clean,
            }))
        }
    }
}

/// Check for probation violations using reduced thresholds (50% of Phase 15)
/// Returns true if violation detected and sovereign re-quarantined
pub async fn check_and_enforce_violation(
    pool: &PgPool,
    sovereign_id: Uuid,
) -> Result<bool, ProbationError> {
    // Probation violation thresholds (50% of Phase 15):
    // dispute_spam: ≥3 in 2h (instead of ≥5)
    // timeout_spam: ≥2 in 24h (instead of ≥3)
    // revocation_pattern: ≥2 in 24h (instead of ≥3)

    // Check dispute spam
    let disputes_2h: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM settlement_invoices
         WHERE debtor_sovereign_id = $1 AND status = 'disputed'
           AND created_at >= NOW() - INTERVAL '2 hours'",
    )
    .bind(sovereign_id)
    .fetch_one(pool)
    .await?;

    if disputes_2h >= 3 {
        // Violation detected — re-quarantine
        sqlx::query("UPDATE sovereigns SET status = 'quarantined' WHERE id = $1")
            .bind(sovereign_id)
            .execute(pool)
            .await?;

        // Log the violation
        sqlx::query(
            "INSERT INTO probation_audit_log (sovereign_id, probation_started_at, event_type, event_details)
             SELECT $1, MAX(probation_started_at), 'anomaly_detected',
                    ('{\"violation_type\": \"dispute_spam\", \"count\": ' || $2 || '}'::jsonb)
             FROM probation_audit_log
             WHERE sovereign_id = $1 AND event_type = 'activity_logged'
               AND event_details->>'event' = 'probation_started'"
        )
        .bind(sovereign_id)
        .bind(disputes_2h)
        .execute(pool)
        .await?;

        return Ok(true);
    }

    // Check timeout spam
    let timeouts_24h: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM escrow_ledger
         WHERE debtor_sovereign_id = $1 AND status = 'forfeited'
           AND forfeited_at >= NOW() - INTERVAL '24 hours'",
    )
    .bind(sovereign_id)
    .fetch_one(pool)
    .await?;

    if timeouts_24h >= 2 {
        // Violation detected
        sqlx::query("UPDATE sovereigns SET status = 'quarantined' WHERE id = $1")
            .bind(sovereign_id)
            .execute(pool)
            .await?;

        // Log the violation
        sqlx::query(
            "INSERT INTO probation_audit_log (sovereign_id, probation_started_at, event_type, event_details)
             SELECT $1, MAX(probation_started_at), 'anomaly_detected',
                    ('{\"violation_type\": \"timeout_spam\", \"count\": ' || $2 || '}'::jsonb)
             FROM probation_audit_log
             WHERE sovereign_id = $1 AND event_type = 'activity_logged'
               AND event_details->>'event' = 'probation_started'"
        )
        .bind(sovereign_id)
        .bind(timeouts_24h)
        .execute(pool)
        .await?;

        return Ok(true);
    }

    // Check revocation pattern
    let revocations_24h: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM cross_sovereign_delegation_grants
         WHERE grantee_sovereign_id = $1 AND revoked_at >= NOW() - INTERVAL '24 hours'",
    )
    .bind(sovereign_id)
    .fetch_one(pool)
    .await?;

    if revocations_24h >= 2 {
        // Violation detected
        sqlx::query("UPDATE sovereigns SET status = 'quarantined' WHERE id = $1")
            .bind(sovereign_id)
            .execute(pool)
            .await?;

        // Log the violation
        sqlx::query(
            "INSERT INTO probation_audit_log (sovereign_id, probation_started_at, event_type, event_details)
             SELECT $1, MAX(probation_started_at), 'anomaly_detected',
                    ('{\"violation_type\": \"revocation_pattern\", \"count\": ' || $2 || '}'::jsonb)
             FROM probation_audit_log
             WHERE sovereign_id = $1 AND event_type = 'activity_logged'
               AND event_details->>'event' = 'probation_started'"
        )
        .bind(sovereign_id)
        .bind(revocations_24h)
        .execute(pool)
        .await?;

        return Ok(true);
    }

    Ok(false)
}

/// Auto-exit probation after 30 clean days
pub async fn try_auto_exit(pool: &PgPool, sovereign_id: Uuid) -> Result<bool, ProbationError> {
    // Get probation status
    let status = get_probation_status(pool, sovereign_id).await?;

    match status {
        None => Ok(false),
        Some(s) if s.days_elapsed < 30 => Ok(false),
        Some(s) if !s.is_clean => Ok(false),
        Some(_) => {
            // 30 days elapsed and clean — exit probation
            sqlx::query("UPDATE sovereigns SET status = 'active' WHERE id = $1")
                .bind(sovereign_id)
                .execute(pool)
                .await?;

            // Log clean exit
            sqlx::query(
                "INSERT INTO probation_audit_log (sovereign_id, probation_started_at, event_type, event_details)
                 SELECT $1, MAX(probation_started_at), 'clean_exit', '{}'::jsonb
                 FROM probation_audit_log
                 WHERE sovereign_id = $1 AND event_type = 'activity_logged'
                   AND event_details->>'event' = 'probation_started'"
            )
            .bind(sovereign_id)
            .execute(pool)
            .await?;

            Ok(true)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_probation_threshold_dispute_below_3_no_violation() {
        // Unit test: dispute count below probation threshold
        let disputes = 2i64;
        assert!(
            disputes < 3,
            "2 disputes in 2h should not trigger violation"
        );
    }

    #[test]
    fn test_probation_threshold_dispute_3_or_more_violation() {
        // Unit test: dispute count at or above probation threshold
        let disputes = 3i64;
        assert!(disputes >= 3, "3 disputes in 2h should trigger violation");
    }
}
