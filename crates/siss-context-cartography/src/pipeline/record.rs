use sqlx::PgPool;
use uuid::Uuid;

use crate::types::{CartographyError, MemoryEntry, VisibleField};

pub async fn record_visible_field(
    pool: &PgPool,
    session_id: Uuid,
    tenant_id: Uuid,
    field: &VisibleField,
) -> Result<(), CartographyError> {
    let all_entries: Vec<&MemoryEntry> = field
        .procedural
        .iter()
        .chain(field.semantic.iter())
        .chain(field.episodic.iter())
        .collect();

    // Batch insert all edges at once (no N+1)
    if !all_entries.is_empty() {
        let edge_ids: Vec<Uuid> = all_entries.iter().map(|_| Uuid::new_v4()).collect();
        let source_ids: Vec<Uuid> = all_entries.iter().map(|_| session_id).collect();
        let target_ids: Vec<Uuid> = all_entries.iter().map(|e| e.memory_id).collect();
        let edge_types: Vec<&str> = all_entries.iter().map(|_| "loaded").collect();
        let tenant_ids: Vec<Uuid> = all_entries.iter().map(|_| tenant_id).collect();
        let metadatas: Vec<serde_json::Value> = all_entries
            .iter()
            .map(|e| serde_json::json!({"tier": format!("{:?}", e.tier)}))
            .collect();

        // Batch insert via UNNEST (single round-trip instead of N)
        sqlx::query(
            "INSERT INTO edges (id, source_id, target_id, edge_type, tenant_id, metadata) \
             SELECT * FROM UNNEST($1::uuid[], $2::uuid[], $3::uuid[], $4::edge_type[], $5::uuid[], $6::jsonb[]) \
             AS t(id, source_id, target_id, edge_type, tenant_id, metadata)",
        )
        .bind(&edge_ids[..])
        .bind(&source_ids[..])
        .bind(&target_ids[..])
        .bind(&edge_types[..])
        .bind(&tenant_ids[..])
        .bind(&metadatas[..])
        .execute(pool)
        .await
        .map_err(|e| CartographyError::DatabaseError {
            message: e.to_string(),
        })?;
    }

    let snapshot = serde_json::to_value(field).unwrap_or(serde_json::Value::Null);

    siss_graph_db::repo::node_repo::update_session_snapshot(pool, session_id, snapshot).await?;

    Ok(())
}
