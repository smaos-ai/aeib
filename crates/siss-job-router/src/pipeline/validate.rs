use sqlx::PgPool;
use uuid::Uuid;

use siss_graph_core::node::execution::{ComplexityClass, TaskStatus};

use crate::types::RouterError;

/// Validated task data extracted from the database.
pub struct ValidatedTask {
    pub task_id: Uuid,
    pub tenant_id: Uuid,
    pub intent: String,
    pub complexity_class: ComplexityClass,
}

/// Pipeline Step 1: Validate that the Task exists, is authorized, and belongs to the correct tenant.
pub async fn validate(
    pool: &PgPool,
    task_id: Uuid,
    tenant_id: Uuid,
) -> Result<ValidatedTask, RouterError> {
    let task_row = siss_graph_db::repo::node_repo::fetch_task(pool, task_id)
        .await?
        .ok_or(RouterError::TaskNotFound { task_id })?;

    let (_id, task_tenant, status, intent) = task_row;

    if status != "authorized" {
        return Err(RouterError::InvalidTaskStatus {
            current: parse_task_status(&status),
            expected: TaskStatus::Authorized,
        });
    }

    if task_tenant != tenant_id {
        return Err(RouterError::TenantViolation {
            source_tenant: task_tenant,
            target_tenant: tenant_id,
        });
    }

    let complexity = fetch_task_complexity(pool, task_id).await?;

    Ok(ValidatedTask {
        task_id,
        tenant_id,
        intent,
        complexity_class: complexity,
    })
}

async fn fetch_task_complexity(pool: &PgPool, task_id: Uuid) -> Result<ComplexityClass, RouterError> {
    let row: Option<(String,)> = sqlx::query_as(
        "SELECT complexity_class::text FROM tasks WHERE id = $1"
    )
    .bind(task_id)
    .fetch_optional(pool)
    .await?;

    let (complexity_str,) = row.ok_or(RouterError::TaskNotFound { task_id })?;
    Ok(parse_complexity_class(&complexity_str))
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

fn parse_complexity_class(s: &str) -> ComplexityClass {
    match s {
        "trivial" => ComplexityClass::Trivial,
        "simple" => ComplexityClass::Simple,
        "moderate" => ComplexityClass::Moderate,
        "complex" => ComplexityClass::Complex,
        "heavy" => ComplexityClass::Heavy,
        _ => ComplexityClass::Moderate,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_task_status_all_variants() {
        assert_eq!(parse_task_status("pending"), TaskStatus::Pending);
        assert_eq!(parse_task_status("authorized"), TaskStatus::Authorized);
        assert_eq!(parse_task_status("routing"), TaskStatus::Routing);
        assert_eq!(parse_task_status("executing"), TaskStatus::Executing);
        assert_eq!(parse_task_status("completed"), TaskStatus::Completed);
        assert_eq!(parse_task_status("failed"), TaskStatus::Failed);
        assert_eq!(parse_task_status("unknown"), TaskStatus::Failed);
    }

    #[test]
    fn test_parse_complexity_class_all_variants() {
        assert_eq!(parse_complexity_class("trivial"), ComplexityClass::Trivial);
        assert_eq!(parse_complexity_class("simple"), ComplexityClass::Simple);
        assert_eq!(parse_complexity_class("moderate"), ComplexityClass::Moderate);
        assert_eq!(parse_complexity_class("complex"), ComplexityClass::Complex);
        assert_eq!(parse_complexity_class("heavy"), ComplexityClass::Heavy);
        assert_eq!(parse_complexity_class("unknown"), ComplexityClass::Moderate);
    }
}
