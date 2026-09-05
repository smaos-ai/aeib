use chrono::{DateTime, Utc};
use sqlx::PgPool;
use uuid::Uuid;

#[derive(Debug, Clone)]
pub struct CapabilityRequest {
    pub id: Uuid,
    pub requester_id: Uuid,
    pub requester_sovereign: Uuid,
    pub target_resource: String,
    pub requested_capability: String,
    pub ceiling_tier_limit: String,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone)]
pub struct CapabilityGrant {
    pub id: Uuid,
    pub request_id: Uuid,
    pub granted_capability: String,
    pub ceiling_tier: String,
    pub expires_at: DateTime<Utc>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CapabilityRequestStatus {
    Pending,
    Proposed,
    Accepted,
    Rejected,
    Expired,
}

#[derive(Debug, Clone)]
pub enum NegotiationError {
    RequestNotFound,
    InvalidRequest,
    ConsensusRequired,
    Timeout,
    InvalidGrant,
    DatabaseError(String),
}

pub async fn submit_capability_request(
    pool: &PgPool,
    requester_id: Uuid,
    requester_sovereign: Uuid,
    target_resource: String,
    requested_capability: String,
    ceiling_tier_limit: String,
) -> Result<Uuid, NegotiationError> {
    let request_id = Uuid::new_v4();
    let now = Utc::now();

    // Insert into database
    sqlx::query(
        r#"
        INSERT INTO capability_requests (id, requester_id, requester_sovereign, target_resource, requested_capability, ceiling_tier_limit, status, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        "#,
    )
    .bind(request_id)
    .bind(requester_id)
    .bind(requester_sovereign)
    .bind(&target_resource)
    .bind(&requested_capability)
    .bind(&ceiling_tier_limit)
    .bind("pending")
    .bind(now)
    .execute(pool)
    .await
    .map_err(|e| NegotiationError::DatabaseError(e.to_string()))?;

    Ok(request_id)
}

pub async fn propose_grant(
    pool: &PgPool,
    request_id: Uuid,
    granted_capability: String,
    ceiling_tier: String,
    expires_at: DateTime<Utc>,
    _proposer_sovereign: Uuid,
) -> Result<(), NegotiationError> {
    let grant_id = Uuid::new_v4();
    let now = Utc::now();

    // Update request status to "proposed"
    sqlx::query(
        r#"
        UPDATE capability_requests SET status = $1, updated_at = $2 WHERE id = $3
        "#,
    )
    .bind("proposed")
    .bind(now)
    .bind(request_id)
    .execute(pool)
    .await
    .map_err(|e| NegotiationError::DatabaseError(e.to_string()))?;

    // Insert grant record
    sqlx::query(
        r#"
        INSERT INTO capability_grants (id, request_id, granted_capability, ceiling_tier, expires_at, created_at)
        VALUES ($1, $2, $3, $4, $5, $6)
        "#,
    )
    .bind(grant_id)
    .bind(request_id)
    .bind(&granted_capability)
    .bind(&ceiling_tier)
    .bind(expires_at)
    .bind(now)
    .execute(pool)
    .await
    .map_err(|e| NegotiationError::DatabaseError(e.to_string()))?;

    Ok(())
}

pub async fn accept_grant(
    pool: &PgPool,
    request_id: Uuid,
    _accepting_agent: Uuid,
) -> Result<CapabilityGrant, NegotiationError> {
    let now = Utc::now();

    // Update request status to "accepted"
    sqlx::query(
        r#"
        UPDATE capability_requests SET status = $1, updated_at = $2 WHERE id = $3
        "#,
    )
    .bind("accepted")
    .bind(now)
    .bind(request_id)
    .execute(pool)
    .await
    .map_err(|e| NegotiationError::DatabaseError(e.to_string()))?;

    // Fetch the grant
    let grant = sqlx::query_as::<_, (Uuid, Uuid, String, String, DateTime<Utc>, DateTime<Utc>)>(
        r#"
        SELECT id, request_id, granted_capability, ceiling_tier, expires_at, created_at
        FROM capability_grants WHERE request_id = $1 LIMIT 1
        "#,
    )
    .bind(request_id)
    .fetch_one(pool)
    .await
    .map_err(|e| NegotiationError::DatabaseError(e.to_string()))?;

    Ok(CapabilityGrant {
        id: grant.0,
        request_id: grant.1,
        granted_capability: grant.2,
        ceiling_tier: grant.3,
        expires_at: grant.4,
        created_at: grant.5,
    })
}

pub async fn get_request_status(
    pool: &PgPool,
    request_id: Uuid,
) -> Result<CapabilityRequestStatus, NegotiationError> {
    let status: String = sqlx::query_scalar(
        r#"
        SELECT status FROM capability_requests WHERE id = $1
        "#,
    )
    .bind(request_id)
    .fetch_one(pool)
    .await
    .map_err(|_| NegotiationError::RequestNotFound)?;

    Ok(match status.as_str() {
        "pending" => CapabilityRequestStatus::Pending,
        "proposed" => CapabilityRequestStatus::Proposed,
        "accepted" => CapabilityRequestStatus::Accepted,
        "rejected" => CapabilityRequestStatus::Rejected,
        "expired" => CapabilityRequestStatus::Expired,
        _ => CapabilityRequestStatus::Pending,
    })
}
