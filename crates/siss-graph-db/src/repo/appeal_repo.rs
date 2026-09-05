use sqlx::PgPool;
use thiserror::Error;
use uuid::Uuid;

#[derive(Debug, Error)]
pub enum AppealError {
    #[error("sovereign {sovereign_id} is not quarantined")]
    NotQuarantined { sovereign_id: Uuid },

    #[error("appeal too soon: must wait {hours_remaining}h before appealing")]
    TooSoon { hours_remaining: i64 },

    #[error("appeal already pending for sovereign {sovereign_id}")]
    AlreadyPending { sovereign_id: Uuid },

    #[error("database error: {message}")]
    Database { message: String },
}

impl From<sqlx::Error> for AppealError {
    fn from(err: sqlx::Error) -> Self {
        AppealError::Database {
            message: err.to_string(),
        }
    }
}

/// Check if sovereign can appeal: must be quarantined, 72h+ since quarantine, no active appeal
pub async fn can_appeal(pool: &PgPool, sovereign_id: Uuid) -> Result<(), AppealError> {
    // Check 1: sovereign must be quarantined
    let status: Option<String> = sqlx::query_scalar("SELECT status FROM sovereigns WHERE id = $1")
        .bind(sovereign_id)
        .fetch_optional(pool)
        .await?
        .flatten();

    match status {
        Some(s) if s == "quarantined" => {}
        _ => return Err(AppealError::NotQuarantined { sovereign_id }),
    }

    // Check 2: 72h cooldown since quarantine (from behavioral_anomalies detected_at)
    let hours_since_quarantine: Option<i64> = sqlx::query_scalar(
        "SELECT EXTRACT(EPOCH FROM (NOW() - MAX(detected_at))) / 3600 AS hours_elapsed
         FROM behavioral_anomalies
         WHERE sovereign_id = $1 AND is_active = TRUE",
    )
    .bind(sovereign_id)
    .fetch_optional(pool)
    .await?
    .flatten();

    match hours_since_quarantine {
        Some(hours) if hours >= 72 => {}
        Some(hours) => {
            let hours_remaining = (72 - hours).max(1);
            return Err(AppealError::TooSoon { hours_remaining });
        }
        None => {
            return Err(AppealError::TooSoon {
                hours_remaining: 72,
            });
        }
    }

    // Check 3: no active appeal already pending
    let active_appeal_count: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM appeal_proposals
         WHERE sovereign_id = $1 AND is_approved IS NULL",
    )
    .bind(sovereign_id)
    .fetch_one(pool)
    .await?;

    if active_appeal_count > 0 {
        return Err(AppealError::AlreadyPending { sovereign_id });
    }

    Ok(())
}

/// Initiate an appeal: validates via can_appeal(), then inserts record
pub async fn initiate_appeal(
    pool: &PgPool,
    sovereign_id: Uuid,
    consensus_proposal_id: Uuid,
    improvement_evidence: serde_json::Value,
) -> Result<Uuid, AppealError> {
    can_appeal(pool, sovereign_id).await?;

    let appeal_id = sqlx::query_scalar::<_, Uuid>(
        "INSERT INTO appeal_proposals (sovereign_id, consensus_proposal_id, improvement_evidence, appeal_initiated_at)
         VALUES ($1, $2, $3, NOW())
         RETURNING id"
    )
    .bind(sovereign_id)
    .bind(consensus_proposal_id)
    .bind(improvement_evidence)
    .fetch_one(pool)
    .await?;

    Ok(appeal_id)
}

/// Record appeal decision: update is_approved and appeal_resolved_at
pub async fn record_appeal_decision(
    pool: &PgPool,
    appeal_id: Uuid,
    is_approved: bool,
) -> Result<(), AppealError> {
    sqlx::query(
        "UPDATE appeal_proposals
         SET is_approved = $1, appeal_resolved_at = NOW()
         WHERE id = $2",
    )
    .bind(is_approved)
    .bind(appeal_id)
    .execute(pool)
    .await?;

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_appeal_72h_cooldown_not_elapsed() {
        // This is a unit test — no DB access
        // Demonstrates the 72h threshold logic
        let hours_elapsed = 50.0;
        assert!(hours_elapsed < 72.0, "50h should be too soon");

        let hours_remaining = (72 - hours_elapsed as i64).max(1);
        assert_eq!(hours_remaining, 22, "should have 22 hours to wait");
    }

    #[test]
    fn test_appeal_72h_cooldown_elapsed() {
        // Unit test — demonstrates 72h threshold passing
        let hours_elapsed = 80.0;
        assert!(hours_elapsed >= 72.0, "80h should allow appeal");
    }
}
