/// Phase 38: RCE Checkpoint Repository
///
/// Persistent storage layer for paused RCE workflow state with ACID guarantees.
/// All functions are free functions taking &PgPool, following session_repo pattern.
use chrono::{DateTime, Utc};
use serde_json::Value as JsonValue;
use sqlx::PgPool;
use uuid::Uuid;

// =====================================================================
// CHECKPOINT OPERATIONS
// =====================================================================

/// Save or upsert a workflow checkpoint (upsert via INSERT ... ON CONFLICT)
pub async fn save_checkpoint(
    pool: &PgPool,
    workflow_id: Uuid,
    step_index: i32,
    state: &JsonValue,
    checksum: &str,
    version: i32,
    reason: &str,
    severity: &str,
) -> Result<Uuid, sqlx::Error> {
    let result: (Uuid,) = sqlx::query_as(
        "INSERT INTO rce_checkpoints (workflow_id, step_index, state, checksum, version, reason, severity)
         VALUES ($1, $2, $3, $4, $5, $6, $7)
         ON CONFLICT (workflow_id) DO UPDATE SET
           step_index = $2,
           state = $3,
           checksum = $4,
           version = $5,
           reason = $6,
           severity = $7,
           created_at = now()
         RETURNING id",
    )
    .bind(workflow_id)
    .bind(step_index)
    .bind(state)
    .bind(checksum)
    .bind(version)
    .bind(reason)
    .bind(severity)
    .fetch_one(pool)
    .await?;

    Ok(result.0)
}

/// Load the latest checkpoint for a workflow (returns None if not found)
pub async fn load_checkpoint(
    pool: &PgPool,
    workflow_id: Uuid,
) -> Result<Option<(Uuid, i32, JsonValue, String, i32, String)>, sqlx::Error> {
    sqlx::query_as::<_, (Uuid, i32, JsonValue, String, i32, String)>(
        "SELECT id, step_index, state, checksum, version, reason
         FROM rce_checkpoints
         WHERE workflow_id = $1",
    )
    .bind(workflow_id)
    .fetch_optional(pool)
    .await
}

/// Delete the checkpoint for a workflow (returns true if deleted)
pub async fn delete_checkpoint(pool: &PgPool, workflow_id: Uuid) -> Result<bool, sqlx::Error> {
    let result = sqlx::query("DELETE FROM rce_checkpoints WHERE workflow_id = $1")
        .bind(workflow_id)
        .execute(pool)
        .await?;

    Ok(result.rows_affected() > 0)
}

/// Check if a checkpoint exists for a workflow
pub async fn checkpoint_exists(pool: &PgPool, workflow_id: Uuid) -> Result<bool, sqlx::Error> {
    let result: (bool,) = sqlx::query_as::<_, (bool,)>(
        "SELECT EXISTS(SELECT 1 FROM rce_checkpoints WHERE workflow_id = $1)",
    )
    .bind(workflow_id)
    .fetch_one(pool)
    .await?;

    Ok(result.0)
}

// =====================================================================
// AUDIT TRAIL OPERATIONS (APPEND-ONLY)
// =====================================================================

/// Append an event to the audit trail (immutable, append-only)
pub async fn append_audit_event(
    pool: &PgPool,
    workflow_id: Uuid,
    event_type: &str,
    decision: Option<&str>,
    decided_by: Option<&str>,
    reason: Option<&str>,
    details: &JsonValue,
) -> Result<Uuid, sqlx::Error> {
    let result: (Uuid,) = sqlx::query_as(
        "INSERT INTO rce_audit_trail (workflow_id, event_type, decision, decided_by, reason, details)
         VALUES ($1, $2, $3, $4, $5, $6)
         RETURNING id",
    )
    .bind(workflow_id)
    .bind(event_type)
    .bind(decision)
    .bind(decided_by)
    .bind(reason)
    .bind(details)
    .fetch_one(pool)
    .await?;

    Ok(result.0)
}

/// Fetch the entire audit trail for a workflow (chronological order)
pub async fn fetch_audit_trail(
    pool: &PgPool,
    workflow_id: Uuid,
) -> Result<
    Vec<(
        Uuid,
        String,
        Option<String>,
        Option<String>,
        Option<String>,
        JsonValue,
        DateTime<Utc>,
    )>,
    sqlx::Error,
> {
    sqlx::query_as::<
        _,
        (
            Uuid,
            String,
            Option<String>,
            Option<String>,
            Option<String>,
            JsonValue,
            DateTime<Utc>,
        ),
    >(
        "SELECT id, event_type, decision, decided_by, reason, details, occurred_at
         FROM rce_audit_trail
         WHERE workflow_id = $1
         ORDER BY occurred_at ASC",
    )
    .bind(workflow_id)
    .fetch_all(pool)
    .await
}

// =====================================================================
// OPTIMISTIC CONCURRENCY CONTROL (OCC)
// =====================================================================

/// OCC update: only succeeds if current version == expected_version.
/// Returns true on success, false on optimistic lock failure (version mismatch).
/// Caller must increment new_version = expected_version + 1.
pub async fn update_checkpoint_occ(
    pool: &PgPool,
    workflow_id: Uuid,
    expected_version: i32,
    step_index: i32,
    state: &JsonValue,
    checksum: &str,
    new_version: i32,
    reason: &str,
    severity: &str,
) -> Result<bool, sqlx::Error> {
    let result = sqlx::query(
        "UPDATE rce_checkpoints
         SET step_index=$3, state=$4, checksum=$5, version=$6,
             reason=$7, severity=$8, created_at=now()
         WHERE workflow_id=$1 AND version=$2",
    )
    .bind(workflow_id)
    .bind(expected_version)
    .bind(step_index)
    .bind(state)
    .bind(checksum)
    .bind(new_version)
    .bind(reason)
    .bind(severity)
    .execute(pool)
    .await?;

    Ok(result.rows_affected() == 1)
}
