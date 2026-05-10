pub mod act;
pub mod inspect;
pub mod validate;

use sqlx::PgPool;

use siss_graph_core::node::NodeId;

use crate::checker::FirewallChecker;
use crate::types::{FirewallError, InspectionRequest, InspectionResult};
use crate::verdict::render_verdict;

pub async fn inspect_output(
    pool: &PgPool,
    checkers: &[&dyn FirewallChecker],
    request: &InspectionRequest,
) -> Result<InspectionResult, FirewallError> {
    let task_id = request.task_id.0;
    let persona_id = request.persona_id.0;
    let intent_mandate_id = request.intent_mandate_id.0;
    let tenant_id = request.tenant_id.0;

    validate::validate_and_transition(pool, task_id, tenant_id).await?;

    let violations = inspect::run_checkers(
        pool,
        task_id,
        intent_mandate_id,
        request.token_cost,
        request.execution_output.clone(),
        request.authorized_tools.clone(),
        checkers,
    )
    .await?;

    let verdict = render_verdict(&violations);

    act::act_on_verdict(pool, task_id, persona_id, tenant_id, &verdict, &violations).await?;

    Ok(InspectionResult {
        task_id: NodeId(task_id),
        verdict,
        violations,
    })
}
