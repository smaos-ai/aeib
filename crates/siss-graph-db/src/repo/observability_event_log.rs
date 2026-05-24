use chrono::{DateTime, Utc};
use sha2::{Sha256, Digest};
use sqlx::PgPool;
use uuid::Uuid;
use serde_json::{json, Value as JsonValue};

/// Append an event to the observability log with hash chain verification.
/// Returns the event UUID.
pub async fn append_event(
    pool: &PgPool,
    sovereign_id: Uuid,
    event_type: &str,
    agent_id: &str,
    payload_json: &str,
) -> Result<Uuid, sqlx::Error> {
    let event_id = Uuid::new_v4();
    let now = Utc::now();

    // Parse payload as JSON
    let payload_value: JsonValue = serde_json::from_str(payload_json)
        .unwrap_or(json!({"raw": payload_json}));

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
        payload_json,
        now.to_rfc3339()
    );
    let mut hasher = Sha256::new();
    hasher.update(hash_input.as_bytes());
    let curr_hash = format!("{:x}", hasher.finalize());

    sqlx::query(
        "INSERT INTO observability_event_log (event_id, sovereign_id, event_type, agent_id, event_payload, prev_hash, curr_hash, created_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8)"
    )
    .bind(event_id)
    .bind(sovereign_id)
    .bind(event_type)
    .bind(agent_id)
    .bind(payload_value)
    .bind(prev_hash)
    .bind(curr_hash)
    .bind(now)
    .execute(pool)
    .await?;

    Ok(event_id)
}

/// Verify the integrity of the event log for a sovereign.
/// Walks forward through all events, recomputes hashes, and detects tampering.
/// Returns (is_valid, error_message).
pub async fn verify_event_log_integrity(
    pool: &PgPool,
    sovereign_id: Uuid,
) -> Result<(bool, Option<String>), sqlx::Error> {
    // Fetch all events for this sovereign in order
    // Note: event_payload is JSONB, so we cast it to text for hashing
    let events: Vec<(i64, String, String, String, Option<String>, String, DateTime<Utc>)> = sqlx::query_as(
        "SELECT sequence, event_type, agent_id, event_payload::text, prev_hash, curr_hash, created_at FROM observability_event_log WHERE sovereign_id = $1 ORDER BY sequence ASC"
    )
    .bind(sovereign_id)
    .fetch_all(pool)
    .await?;

    if events.is_empty() {
        return Ok((true, None));
    }

    let mut expected_prev_hash: Option<String> = None;

    for (seq, event_type, agent_id, payload, stored_prev_hash, stored_curr_hash, created_at) in events {
        // Check that prev_hash matches expected
        if stored_prev_hash != expected_prev_hash {
            let msg = format!(
                "Sequence {}: prev_hash mismatch. Expected: {:?}, Got: {:?}",
                seq, expected_prev_hash, stored_prev_hash
            );
            return Ok((false, Some(msg)));
        }

        // Recompute current hash using the same format as append_event
        // Format: prev_hash || event_type || agent_id || payload || timestamp (RFC3339)
        let timestamp_str = created_at.to_rfc3339();
        let hash_input = format!(
            "{}{}{}{}{}",
            stored_prev_hash.as_deref().unwrap_or(""),
            event_type,
            agent_id,
            payload,
            timestamp_str
        );
        let mut hasher = Sha256::new();
        hasher.update(hash_input.as_bytes());
        let computed_hash = format!("{:x}", hasher.finalize());

        // Check if computed hash matches stored hash
        if computed_hash != stored_curr_hash {
            let msg = format!(
                "Sequence {}: hash mismatch. Expected: {}, Got: {}",
                seq, computed_hash, stored_curr_hash
            );
            return Ok((false, Some(msg)));
        }

        expected_prev_hash = Some(stored_curr_hash);
    }

    Ok((true, None))
}

/// Start a distributed trace across multiple sovereigns.
/// Returns the trace UUID.
pub async fn start_distributed_trace(
    pool: &PgPool,
    root_sovereign: Uuid,
    participants: Vec<Uuid>,
    request_id: &str,
) -> Result<Uuid, sqlx::Error> {
    let trace_id = Uuid::new_v4();
    let now = Utc::now();

    sqlx::query(
        "INSERT INTO distributed_traces (trace_id, root_sovereign_id, participating_sovereigns, request_id, start_ts, status, created_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7)"
    )
    .bind(trace_id)
    .bind(root_sovereign)
    .bind(participants)
    .bind(request_id)
    .bind(now)
    .bind("active")
    .bind(now)
    .execute(pool)
    .await?;

    Ok(trace_id)
}

/// Fire an alert based on a rule.
/// Returns the alert UUID.
pub async fn fire_alert(
    pool: &PgPool,
    rule_id: Uuid,
    sovereign_id: Uuid,
    agent_id: &str,
    _context: &str,
) -> Result<Uuid, sqlx::Error> {
    let alert_id = Uuid::new_v4();
    let now = Utc::now();

    sqlx::query(
        "INSERT INTO agents_alerts (alert_id, rule_id, sovereign_id, agent_id, fired_at, status, created_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7)"
    )
    .bind(alert_id)
    .bind(rule_id)
    .bind(sovereign_id)
    .bind(agent_id)
    .bind(now)
    .bind("open")
    .bind(now)
    .execute(pool)
    .await?;

    Ok(alert_id)
}
