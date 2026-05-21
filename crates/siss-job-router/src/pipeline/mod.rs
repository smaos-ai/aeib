pub mod execute;
pub mod route;
pub mod validate;

use sqlx::PgPool;

use crate::executor::{Executor, TaskContext};
use crate::strategy::RoutingStrategy;
use crate::types::{RouterError, RoutingRequest, RoutingResult};
use siss_graph_core::node::NodeId;
use siss_event_log::{EventLog, SystemEvent};

/// The sole entry point for task routing and dispatch.
/// Runs the full pipeline: validate → check dependencies → route → execute.
pub async fn route_task(
    pool: &PgPool,
    strategy: &dyn RoutingStrategy,
    executor: &dyn Executor,
    event_log: Option<&EventLog>,
    request: &RoutingRequest,
) -> Result<RoutingResult, RouterError> {
    let task_id = request.task_id.0;
    let tenant_id = request.tenant_id.0;

    // Step 1: Validate
    let validated = validate::validate(pool, task_id, tenant_id).await?;

    // Step 2: Check Dependencies
    if !request.depends_on.is_empty() {
        validate_dependencies(event_log, &request.depends_on).await?;
    }

    // Step 3: Route
    let hardware_target = strategy.decide(validated.complexity_class);
    route::apply_routing_decision(pool, task_id, hardware_target).await?;

    // Step 4: Execute
    let context = TaskContext {
        task_id,
        intent: validated.intent,
        complexity_class: validated.complexity_class,
        hardware_target,
        tenant_id,
        visible_field: None, // Populated by caller when Context Cartography is integrated
    };
    let execution = execute::dispatch_and_execute(pool, executor, context).await?;

    Ok(RoutingResult {
        task_id: NodeId(task_id),
        hardware_target,
        execution,
    })
}

/// Validate that all dependent jobs have completed before allowing this job to proceed.
/// Returns error if any dependency is not yet completed (task stays in Pending state).
async fn validate_dependencies(
    event_log: Option<&EventLog>,
    depends_on: &[uuid::Uuid],
) -> Result<(), RouterError> {
    if let Some(log) = event_log {
        for dep_id in depends_on {
            let events = log
                .get_events(*dep_id)
                .await
                .map_err(|e| RouterError::DatabaseError {
                    message: format!("Failed to check dependency {}: {}", dep_id, e),
                })?;

            let is_completed = events.iter().any(|event| {
                matches!(event, SystemEvent::JobCompleted { .. })
            });

            if !is_completed {
                return Err(RouterError::ExecutionFailed {
                    message: format!("Dependency {} not yet completed", dep_id),
                });
            }
        }
    }
    Ok(())
}
