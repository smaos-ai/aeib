pub mod procedural;
pub mod semantic;
pub mod episodic;

use sqlx::PgPool;
use uuid::Uuid;

use crate::config::RetrievalConfig;
use crate::types::{CartographyError, MemoryEntry};

/// Retrieve all three tiers of memories for a Persona within a tenant.
pub async fn retrieve_all_tiers(
    pool: &PgPool,
    persona_id: Uuid,
    tenant_id: Uuid,
    config: &RetrievalConfig,
) -> Result<(Vec<MemoryEntry>, Vec<MemoryEntry>, Vec<MemoryEntry>), CartographyError> {
    let accessible_ids = siss_graph_db::repo::memory_repo::fetch_accessible_memory_ids(
        pool, persona_id, tenant_id,
    )
    .await?;

    let proc = procedural::fetch(pool, tenant_id, &accessible_ids, config).await?;
    let sem = semantic::fetch(pool, tenant_id, &accessible_ids, config).await?;
    let epi = episodic::fetch(pool, tenant_id, &accessible_ids, config).await?;

    Ok((proc, sem, epi))
}
