use chrono::{DateTime, Utc};
use sqlx::PgPool;
use uuid::Uuid;

use crate::repo::capability_negotiation::CapabilityGrant;

pub type GrantHash = String;
pub type TransactionHash = String;

pub async fn record_grant(
    pool: &PgPool,
    grant: &CapabilityGrant,
    _consensus_proof: &TransactionHash,
) -> Result<GrantHash, sqlx::Error> {
    let hash = format!("grant_{}", grant.id);
    let now = Utc::now();

    sqlx::query(
        r#"
        INSERT INTO grant_ledger (grant_id, request_id, granted_capability, ceiling_tier, expires_at, recorded_at, status)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        "#,
    )
    .bind(grant.id)
    .bind(grant.request_id)
    .bind(&grant.granted_capability)
    .bind(&grant.ceiling_tier)
    .bind(grant.expires_at)
    .bind(now)
    .bind("active")
    .execute(pool)
    .await?;

    Ok(hash)
}

pub async fn revoke_grant(pool: &PgPool, grant_id: Uuid, _reason: &str) -> Result<(), sqlx::Error> {
    sqlx::query(
        r#"
        UPDATE grant_ledger SET status = $1 WHERE grant_id = $2
        "#,
    )
    .bind("revoked")
    .bind(grant_id)
    .execute(pool)
    .await?;

    Ok(())
}

pub async fn verify_grant_active(pool: &PgPool, grant_id: Uuid) -> Result<bool, sqlx::Error> {
    let result: Option<(String, DateTime<Utc>)> = sqlx::query_as(
        r#"
        SELECT status, expires_at FROM grant_ledger WHERE grant_id = $1
        "#,
    )
    .bind(grant_id)
    .fetch_optional(pool)
    .await?;

    if let Some((status, expires_at)) = result {
        let is_active = status == "active" && expires_at > Utc::now();
        Ok(is_active)
    } else {
        Ok(false)
    }
}

pub async fn get_grant_history(
    pool: &PgPool,
    requester_id: Uuid,
    limit: usize,
) -> Result<Vec<CapabilityGrant>, sqlx::Error> {
    let grants: Vec<(Uuid, Uuid, String, String, DateTime<Utc>, DateTime<Utc>)> =
        sqlx::query_as(
            r#"
            SELECT g.grant_id, g.request_id, g.granted_capability, g.ceiling_tier, g.expires_at, g.recorded_at
            FROM grant_ledger g
            JOIN capability_requests r ON g.request_id = r.id
            WHERE r.requester_id = $1
            ORDER BY g.recorded_at DESC
            LIMIT $2
            "#,
        )
        .bind(requester_id)
        .bind(limit as i64)
        .fetch_all(pool)
        .await?;

    Ok(grants
        .into_iter()
        .map(|g| CapabilityGrant {
            id: g.0,
            request_id: g.1,
            granted_capability: g.2,
            ceiling_tier: g.3,
            expires_at: g.4,
            created_at: g.5,
        })
        .collect())
}
