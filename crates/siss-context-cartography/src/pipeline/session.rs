use sqlx::PgPool;
use uuid::Uuid;

use crate::types::CartographyError;

pub async fn create_session(
    pool: &PgPool,
    task_id: Uuid,
    persona_id: Uuid,
    tenant_id: Uuid,
    token_budget: i64,
) -> Result<Uuid, CartographyError> {
    let session_id = siss_graph_db::repo::node_repo::insert_session(
        pool, token_budget, persona_id, tenant_id,
    )
    .await?;

    // SCOPED_TO: Session → Persona
    siss_graph_db::repo::edge_repo::insert_edge(
        pool, session_id, persona_id, "scoped_to", tenant_id, serde_json::json!({}),
    )
    .await?;

    // CONTAINS: Session → Task
    siss_graph_db::repo::edge_repo::insert_edge(
        pool, session_id, task_id, "contains", tenant_id, serde_json::json!({}),
    )
    .await?;

    Ok(session_id)
}
