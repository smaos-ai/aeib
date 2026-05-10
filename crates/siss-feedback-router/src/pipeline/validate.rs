use sqlx::PgPool;
use uuid::Uuid;

use siss_graph_core::node::execution::TaskStatus;

use crate::types::FeedbackError;

/// Validate task is in guarding status and tenant matches. Returns the task intent.
pub async fn validate_and_transition(
    pool: &PgPool,
    task_id: Uuid,
    tenant_id: Uuid,
) -> Result<String, FeedbackError> {
    let task_row = siss_graph_db::repo::node_repo::fetch_task(pool, task_id)
        .await?
        .ok_or(FeedbackError::TaskNotFound { task_id })?;

    let (_id, task_tenant, status, intent) = task_row;

    if status != "guarding" {
        return Err(FeedbackError::InvalidTaskStatus {
            current: parse_task_status(&status),
            expected: TaskStatus::Guarding,
        });
    }

    if task_tenant != tenant_id {
        return Err(FeedbackError::TenantViolation {
            source_tenant: task_tenant,
            target_tenant: tenant_id,
        });
    }

    // Transition: guarding → crystallizing
    siss_graph_db::repo::node_repo::update_task_status(pool, task_id, "crystallizing").await?;

    Ok(intent)
}

fn parse_task_status(s: &str) -> TaskStatus {
    match s {
        "pending" => TaskStatus::Pending,
        "authorized" => TaskStatus::Authorized,
        "routing" => TaskStatus::Routing,
        "executing" => TaskStatus::Executing,
        "guarding" => TaskStatus::Guarding,
        "crystallizing" => TaskStatus::Crystallizing,
        "completed" => TaskStatus::Completed,
        "failed" => TaskStatus::Failed,
        _ => TaskStatus::Failed,
    }
}
