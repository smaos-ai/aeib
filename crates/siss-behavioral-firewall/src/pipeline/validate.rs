use sqlx::PgPool;
use uuid::Uuid;

use siss_graph_core::node::execution::TaskStatus;

use crate::types::FirewallError;

pub async fn validate_and_transition(
    pool: &PgPool,
    task_id: Uuid,
    tenant_id: Uuid,
) -> Result<(), FirewallError> {
    let task_row = siss_graph_db::repo::node_repo::fetch_task(pool, task_id)
        .await?
        .ok_or(FirewallError::TaskNotFound { task_id })?;

    let (_id, task_tenant, status, _intent) = task_row;

    if status != "executing" {
        return Err(FirewallError::InvalidTaskStatus {
            current: parse_task_status(&status),
            expected: TaskStatus::Executing,
        });
    }

    if task_tenant != tenant_id {
        return Err(FirewallError::TenantViolation {
            source_tenant: task_tenant,
            target_tenant: tenant_id,
        });
    }

    siss_graph_db::repo::node_repo::update_task_status(pool, task_id, "guarding")
        .await?;

    Ok(())
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
