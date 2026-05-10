pub mod execute;
pub mod route;
pub mod validate;

use sqlx::PgPool;

use crate::executor::{Executor, TaskContext};
use crate::strategy::RoutingStrategy;
use crate::types::{RouterError, RoutingRequest, RoutingResult};
use siss_graph_core::node::NodeId;

/// The sole entry point for task routing and dispatch.
/// Runs the full pipeline: validate → route → execute.
pub async fn route_task(
    pool: &PgPool,
    strategy: &dyn RoutingStrategy,
    executor: &dyn Executor,
    request: &RoutingRequest,
) -> Result<RoutingResult, RouterError> {
    let task_id = request.task_id.0;
    let tenant_id = request.tenant_id.0;

    // Step 1: Validate
    let validated = validate::validate(pool, task_id, tenant_id).await?;

    // Step 2: Route
    let hardware_target = strategy.decide(validated.complexity_class);
    route::apply_routing_decision(pool, task_id, hardware_target).await?;

    // Step 3: Execute
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
