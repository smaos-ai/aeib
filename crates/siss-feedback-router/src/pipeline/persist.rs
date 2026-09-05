use sqlx::PgPool;
use uuid::Uuid;

use crate::types::{CrystallizedMemory, FeedbackError};

/// Persist crystallized memories: insert memory nodes, create PRODUCED edges, complete the task.
pub async fn persist_and_complete(
    pool: &PgPool,
    task_id: Uuid,
    tenant_id: Uuid,
    quality_score: f64,
    memories: &[CrystallizedMemory],
) -> Result<(), FeedbackError> {
    // Insert each memory and create PRODUCED edge
    for mem in memories {
        let memory_id = siss_graph_db::repo::memory_repo::insert_memory(
            pool,
            &mem.content,
            &format!("{:?}", mem.tier).to_lowercase(),
            quality_score, // confidence starts at quality score
            quality_score,
            tenant_id,
        )
        .await?;

        // PRODUCED: Task → Memory
        siss_graph_db::repo::edge_repo::insert_edge(
            pool,
            task_id,
            memory_id,
            "produced",
            tenant_id,
            serde_json::json!({"quality_score": quality_score}),
        )
        .await?;
    }

    // Transition: crystallizing → completed
    siss_graph_db::repo::node_repo::update_task_status(pool, task_id, "completed").await?;

    Ok(())
}
