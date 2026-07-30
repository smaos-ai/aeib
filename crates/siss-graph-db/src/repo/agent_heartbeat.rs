use chrono::Utc;
use serde_json::json;
use sha2::{Digest, Sha256};
use sqlx::PgPool;
use uuid::Uuid;

/// Record a heartbeat for an agent and append an event to the observability log.
/// Returns the heartbeat UUID.
pub async fn record_heartbeat(
    pool: &PgPool,
    agent_id: &str,
    sovereign_id: Uuid,
    latency_ms: i64,
) -> Result<Uuid, sqlx::Error> {
    let heartbeat_id = Uuid::new_v4();
    let now = Utc::now();

    // Determine status based on latency
    let status = if latency_ms < 1000 {
        "healthy"
    } else {
        "degraded"
    };

    // Compute merkle_proof_ref: SHA256('agent:' || agent_id || ':' || sovereign_id || ':' || registry_id)
    // For now, we'll use a simplified version without registry_id
    let proof_input = format!("agent:{}:{}:{}", agent_id, sovereign_id, heartbeat_id);
    let mut hasher = Sha256::new();
    hasher.update(proof_input.as_bytes());
    let merkle_proof_ref = format!("{:x}", hasher.finalize());

    // Insert into agent_heartbeats
    sqlx::query(
        "INSERT INTO agent_heartbeats (id, agent_id, sovereign_id, heartbeat_ts, latency_ms, status, merkle_proof_ref, created_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8)"
    )
    .bind(heartbeat_id)
    .bind(agent_id)
    .bind(sovereign_id)
    .bind(now)
    .bind(latency_ms)
    .bind(status)
    .bind(merkle_proof_ref)
    .bind(now)
    .execute(pool)
    .await?;

    // Also append event to observability log
    let event_type = if latency_ms < 1000 {
        "heartbeat_received"
    } else {
        "heartbeat_degraded"
    };

    let event_payload = json!({
        "latency_ms": latency_ms,
        "status": status
    });

    // Get previous event hash if exists
    let prev_hash_result: Option<(String,)> = sqlx::query_as(
        "SELECT curr_hash FROM observability_event_log WHERE sovereign_id = $1 ORDER BY sequence DESC LIMIT 1"
    )
    .bind(sovereign_id)
    .fetch_optional(pool)
    .await?;

    let prev_hash = prev_hash_result.map(|(h,)| h);

    // Compute current hash: SHA256(prev_hash || event_type || agent_id || payload || timestamp)
    let hash_input = format!(
        "{}{}{}{}{}",
        prev_hash.as_deref().unwrap_or(""),
        event_type,
        agent_id,
        event_payload,
        now.to_rfc3339()
    );
    let mut hasher = Sha256::new();
    hasher.update(hash_input.as_bytes());
    let curr_hash = format!("{:x}", hasher.finalize());

    sqlx::query(
        "INSERT INTO observability_event_log (event_id, sovereign_id, event_type, agent_id, event_payload, prev_hash, curr_hash, created_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8)"
    )
    .bind(Uuid::new_v4())
    .bind(sovereign_id)
    .bind(event_type)
    .bind(agent_id)
    .bind(&event_payload)
    .bind(prev_hash)
    .bind(curr_hash)
    .bind(now)
    .execute(pool)
    .await?;

    Ok(heartbeat_id)
}

/// Compute agent health score based on last 10 heartbeats.
/// Healthy heartbeats (latency < 1000ms) = 100 points
/// Degraded heartbeats (latency >= 1000ms) = 50 points
/// Returns weighted average.
pub async fn compute_agent_health_score(
    pool: &PgPool,
    agent_id: &str,
    sovereign_id: Uuid,
) -> Result<f64, sqlx::Error> {
    // Get last 10 heartbeats
    let heartbeats: Vec<(String,)> = sqlx::query_as(
        "SELECT status FROM agent_heartbeats WHERE agent_id = $1 AND sovereign_id = $2 ORDER BY created_at DESC LIMIT 10"
    )
    .bind(agent_id)
    .bind(sovereign_id)
    .fetch_all(pool)
    .await?;

    if heartbeats.is_empty() {
        return Ok(0.0);
    }

    let total_points: f64 = heartbeats
        .iter()
        .map(|(status,)| if status == "healthy" { 100.0 } else { 50.0 })
        .sum();

    let health_score = total_points / heartbeats.len() as f64;
    Ok(health_score)
}
