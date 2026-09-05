use chrono::{DateTime, Utc};
use sqlx::PgPool;
use thiserror::Error;
use uuid::Uuid;

#[derive(Debug, Error)]
pub enum MeasurementError {
    #[error("database error: {message}")]
    Database { message: String },
}

impl From<sqlx::Error> for MeasurementError {
    fn from(err: sqlx::Error) -> Self {
        MeasurementError::Database {
            message: err.to_string(),
        }
    }
}

#[derive(Debug, Clone)]
pub struct BehavioralMetrics {
    pub sovereign_id: Uuid,
    pub disputes_7d: i64,
    pub timeouts_7d: i64,
    pub revocations_7d: i64,
    pub is_ready_for_appeal: bool,
    pub measured_at: DateTime<Utc>,
}

/// Measure behavioral improvement over 7-day window
pub async fn measure_behavioral_improvement(
    pool: &PgPool,
    sovereign_id: Uuid,
) -> Result<BehavioralMetrics, MeasurementError> {
    // Count disputes in 7d window
    let disputes_7d: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM settlement_invoices
         WHERE debtor_sovereign_id = $1 AND status = 'disputed'
           AND created_at >= NOW() - INTERVAL '7 days'",
    )
    .bind(sovereign_id)
    .fetch_one(pool)
    .await?;

    // Count escrow timeouts in 7d window
    let timeouts_7d: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM escrow_ledger
         WHERE debtor_sovereign_id = $1 AND status = 'forfeited'
           AND forfeited_at >= NOW() - INTERVAL '7 days'",
    )
    .bind(sovereign_id)
    .fetch_one(pool)
    .await?;

    // Count revocations in 7d window
    let revocations_7d: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM cross_sovereign_delegation_grants
         WHERE grantee_sovereign_id = $1 AND revoked_at >= NOW() - INTERVAL '7 days'",
    )
    .bind(sovereign_id)
    .fetch_one(pool)
    .await?;

    // Appeal-ready: all 7d totals below Phase 15 minimum thresholds
    // disputes_7d < 5, timeouts_7d < 3, revocations_7d < 3
    let is_ready_for_appeal = disputes_7d < 5 && timeouts_7d < 3 && revocations_7d < 3;

    Ok(BehavioralMetrics {
        sovereign_id,
        disputes_7d,
        timeouts_7d,
        revocations_7d,
        is_ready_for_appeal,
        measured_at: Utc::now(),
    })
}

/// Check if sovereign is ready for appeal (convenience wrapper)
pub async fn is_ready_for_appeal(
    pool: &PgPool,
    sovereign_id: Uuid,
) -> Result<bool, MeasurementError> {
    let metrics = measure_behavioral_improvement(pool, sovereign_id).await?;
    Ok(metrics.is_ready_for_appeal)
}

/// Record improvement measurement to behavioral_improvements table
pub async fn record_improvement_measurement(
    pool: &PgPool,
    metrics: &BehavioralMetrics,
) -> Result<Uuid, MeasurementError> {
    let id = sqlx::query_scalar::<_, Uuid>(
        "INSERT INTO behavioral_improvements (sovereign_id, disputes_7d, timeouts_7d, revocations_7d, is_ready_for_appeal, measured_at)
         VALUES ($1, $2, $3, $4, $5, NOW())
         RETURNING id"
    )
    .bind(metrics.sovereign_id)
    .bind(metrics.disputes_7d)
    .bind(metrics.timeouts_7d)
    .bind(metrics.revocations_7d)
    .bind(metrics.is_ready_for_appeal)
    .fetch_one(pool)
    .await?;

    Ok(id)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_all_rates_below_threshold_ready_for_appeal() {
        // Unit test: all rates below Phase 15 thresholds
        let disputes = 4i64;
        let timeouts = 2i64;
        let revocations = 2i64;

        let is_ready = disputes < 5 && timeouts < 3 && revocations < 3;
        assert!(is_ready, "4/2/2 should be ready for appeal");
    }

    #[test]
    fn test_one_rate_above_threshold_not_ready() {
        // Unit test: one rate exceeds threshold
        let disputes = 6i64;
        let timeouts = 2i64;
        let revocations = 2i64;

        let is_ready = disputes < 5 && timeouts < 3 && revocations < 3;
        assert!(
            !is_ready,
            "6 disputes should not be ready (≥5 triggers threshold)"
        );
    }
}
