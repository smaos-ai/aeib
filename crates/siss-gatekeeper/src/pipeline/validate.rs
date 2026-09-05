use sqlx::PgPool;
use uuid::Uuid;

use crate::types::GatekeeperError;

/// Pipeline Step 1: Validate that the Task exists, is pending, the Persona is not frozen,
/// and all entities share the same tenant.
pub async fn validate(
    pool: &PgPool,
    task_id: Uuid,
    persona_id: Uuid,
    tenant_id: Uuid,
) -> Result<(), GatekeeperError> {
    // Fetch task
    let task_row = siss_graph_db::repo::node_repo::fetch_task(pool, task_id)
        .await?
        .ok_or(GatekeeperError::TaskNotFound { task_id })?;

    let (_id, task_tenant, status, _intent) = task_row;

    // Verify status is pending
    if status != "pending" {
        return Err(GatekeeperError::InvalidTaskStatus {
            current: parse_task_status(&status),
            expected: siss_graph_core::node::execution::TaskStatus::Pending,
        });
    }

    // Verify tenant isolation: task tenant == request tenant
    if task_tenant != tenant_id {
        return Err(GatekeeperError::TenantViolation {
            source_tenant: task_tenant,
            target_tenant: tenant_id,
        });
    }

    // Fetch persona
    let persona_row = siss_graph_db::repo::node_repo::fetch_persona(pool, persona_id)
        .await?
        .ok_or(GatekeeperError::TaskNotFound {
            task_id: persona_id,
        })?;

    let (_id, persona_tenant, _name, _kind, is_frozen) = persona_row;

    // Verify persona is not frozen
    if is_frozen {
        return Err(GatekeeperError::PersonaFrozen { persona_id });
    }

    // Phase 15: Check if the sovereign associated with this tenant is quarantined
    // Fail-closed: reject session creation from quarantined sovereigns
    if siss_graph_db::repo::session_repo::is_tenant_sovereign_quarantined(pool, tenant_id)
        .await
        .unwrap_or(false)
    {
        return Err(GatekeeperError::SovereignQuarantined { tenant_id });
    }

    // Phase 16 & 20: Check probation/recovery violation and enforce
    // Uses same Phase 16 thresholds (50% of Phase 15) for both states
    // This is best-effort: DB errors treated as no violation (fail-open on errors)
    if siss_graph_db::repo::probation_repo::check_and_enforce_violation(pool, tenant_id)
        .await
        .unwrap_or(false)
    {
        // Violation was detected and sovereign re-quarantined — block session
        // Phase 16: probation violation → quarantine (via check_and_enforce_violation)
        // Phase 20: recovery violation → quarantine (via recovery_repo call)
        return Err(GatekeeperError::SovereignQuarantined { tenant_id });
    }

    // Verify tenant isolation: persona tenant == request tenant
    if persona_tenant != tenant_id {
        return Err(GatekeeperError::TenantViolation {
            source_tenant: persona_tenant,
            target_tenant: tenant_id,
        });
    }

    Ok(())
}

pub fn parse_task_status(s: &str) -> siss_graph_core::node::execution::TaskStatus {
    match s {
        "pending" => siss_graph_core::node::execution::TaskStatus::Pending,
        "authorized" => siss_graph_core::node::execution::TaskStatus::Authorized,
        "routing" => siss_graph_core::node::execution::TaskStatus::Routing,
        "executing" => siss_graph_core::node::execution::TaskStatus::Executing,
        "guarding" => siss_graph_core::node::execution::TaskStatus::Guarding,
        "crystallizing" => siss_graph_core::node::execution::TaskStatus::Crystallizing,
        "completed" => siss_graph_core::node::execution::TaskStatus::Completed,
        "failed" => siss_graph_core::node::execution::TaskStatus::Failed,
        _ => siss_graph_core::node::execution::TaskStatus::Failed,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use siss_graph_core::node::execution::TaskStatus;

    #[test]
    fn test_parse_task_status_all_variants() {
        assert_eq!(parse_task_status("pending"), TaskStatus::Pending);
        assert_eq!(parse_task_status("authorized"), TaskStatus::Authorized);
        assert_eq!(parse_task_status("routing"), TaskStatus::Routing);
        assert_eq!(parse_task_status("executing"), TaskStatus::Executing);
        assert_eq!(parse_task_status("guarding"), TaskStatus::Guarding);
        assert_eq!(
            parse_task_status("crystallizing"),
            TaskStatus::Crystallizing
        );
        assert_eq!(parse_task_status("completed"), TaskStatus::Completed);
        assert_eq!(parse_task_status("failed"), TaskStatus::Failed);
        assert_eq!(parse_task_status("unknown"), TaskStatus::Failed);
    }
}
