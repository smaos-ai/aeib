pub mod ap2;
pub mod authorization;
pub mod commit;
pub mod covenant;
pub mod governance;
pub mod mandate;
pub mod rebac;
pub mod research;
pub mod validate;

pub use authorization::{AuthorizationPipeline, AuthorizationProof, TaskAuthorizationRequest};

use sqlx::PgPool;

use crate::signer::Signer;
use crate::types::{AuthorizationRequest, AuthorizationResult, GatekeeperError};
use siss_event_log::{EventLog, SystemEvent};

/// The sole entry point for task authorization.
/// Runs the full pipeline: validate → ReBAC → AP2 → governance → covenant → sign+commit.
/// Logs AccessDecision event to audit trail after successful commit.
///
/// The entire operation should be called within a database transaction by the caller.
/// If any step fails, the caller should roll back.
pub async fn authorize_task(
    pool: &PgPool,
    signer: &dyn Signer,
    request: &AuthorizationRequest,
    event_log: Option<&EventLog>,
) -> Result<AuthorizationResult, GatekeeperError> {
    let task_id = request.task_id.0;
    let persona_id = request.persona_id.0;
    let intent_mandate_id = request.intent_mandate_id.0;
    let tenant_id = request.tenant_id.0;
    let tool_ids: Vec<uuid::Uuid> = request.requested_tools.iter().map(|n| n.0).collect();

    // Step 1: Validate
    validate::validate(pool, task_id, persona_id, tenant_id).await?;

    // Step 2: ReBAC
    rebac::check_tool_access(pool, persona_id, &tool_ids, tenant_id).await?;

    // Step 3: AP2
    let (risk_class, budget_remaining) =
        ap2::check_and_debit(pool, intent_mandate_id, &tool_ids, request.estimated_cost).await?;

    // Step 4: Governance
    governance::evaluate_rules(
        pool,
        tenant_id,
        task_id,
        persona_id,
        tenant_id, // task_tenant_id (validated to match in step 1)
        tenant_id, // persona_tenant_id (validated to match in step 1)
        budget_remaining,
        request.estimated_cost,
    )
    .await?;

    // Step 5: Covenant (Economic Intent Validation)
    covenant::check_covenant(pool, intent_mandate_id).await?;

    // Step 6: Sign + Commit
    let result = commit::sign_and_commit(
        pool,
        signer,
        task_id,
        persona_id,
        intent_mandate_id,
        request.estimated_cost,
        &risk_class,
        tenant_id,
    )
    .await?;

    // Step 6: Audit Trail (post-commit)
    if let Some(log) = event_log {
        let decision_event = SystemEvent::AccessDecision {
            actor: persona_id,
            decision: format!("authorized task {} with risk_class {}", task_id, risk_class),
        };
        let _ = log.append_event(task_id, decision_event).await;
        // If logging fails, don't fail the authorization - log is optional
    }

    Ok(result)
}
