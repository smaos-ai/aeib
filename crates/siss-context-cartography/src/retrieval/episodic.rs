use sqlx::PgPool;
use uuid::Uuid;

use siss_graph_core::node::memory::ConsolidationTier;

use crate::config::RetrievalConfig;
use crate::types::{CartographyError, MemoryEntry};

pub async fn fetch(
    pool: &PgPool,
    tenant_id: Uuid,
    accessible_ids: &[Uuid],
    config: &RetrievalConfig,
) -> Result<Vec<MemoryEntry>, CartographyError> {
    let rows = siss_graph_db::repo::memory_repo::fetch_memories_by_tier(
        pool,
        "episodic",
        tenant_id,
        config.confidence_threshold,
        config.max_episodic as i64,
    )
    .await?;

    let entries: Vec<MemoryEntry> = rows
        .into_iter()
        .filter(|(id, _, _, _)| accessible_ids.is_empty() || accessible_ids.contains(id))
        .map(|(id, content, confidence, _tier)| MemoryEntry {
            memory_id: id,
            content,
            confidence_score: confidence,
            tier: ConsolidationTier::Episodic,
            affective_signature: None,
        })
        .collect();

    Ok(entries)
}
