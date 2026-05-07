use sqlx::PgPool;
use uuid::Uuid;

use crate::types::{CartographyError, MemoryEntry, VisibleField};

pub async fn record_visible_field(
    pool: &PgPool,
    session_id: Uuid,
    tenant_id: Uuid,
    field: &VisibleField,
) -> Result<(), CartographyError> {
    let all_entries: Vec<&MemoryEntry> = field.procedural.iter()
        .chain(field.semantic.iter())
        .chain(field.episodic.iter())
        .collect();

    for entry in &all_entries {
        siss_graph_db::repo::edge_repo::insert_edge(
            pool,
            session_id,
            entry.memory_id,
            "loaded",
            tenant_id,
            serde_json::json!({"tier": format!("{:?}", entry.tier)}),
        )
        .await?;
    }

    let snapshot = serde_json::to_value(field)
        .unwrap_or(serde_json::Value::Null);

    siss_graph_db::repo::node_repo::update_session_snapshot(pool, session_id, snapshot)
        .await?;

    Ok(())
}
