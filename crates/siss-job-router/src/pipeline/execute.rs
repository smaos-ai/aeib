use sqlx::PgPool;

use crate::executor::{Executor, TaskContext};
use crate::types::{ExecutionResult, RouterError};

/// Pipeline Step 3: Dispatch to executor, update token_cost, transition to executing.
pub async fn dispatch_and_execute(
    pool: &PgPool,
    executor: &dyn Executor,
    context: TaskContext,
) -> Result<ExecutionResult, RouterError> {
    let task_id = context.task_id;

    let result = executor.execute(context).await.map_err(|e| RouterError::ExecutionFailed {
        message: e.message,
    })?;

    siss_graph_db::repo::node_repo::update_task_token_cost(pool, task_id, result.token_cost)
        .await?;

    siss_graph_db::repo::node_repo::update_task_status(pool, task_id, "executing")
        .await?;

    Ok(result)
}
