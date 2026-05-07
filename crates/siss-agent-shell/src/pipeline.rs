use sqlx::PgPool;
use uuid::Uuid;

use siss_graph_core::node::NodeId;
use siss_behavioral_firewall::types::Verdict;
use siss_gatekeeper::signer::Signer;
use siss_gatekeeper::types::AuthorizationRequest;
use siss_job_router::strategy::RoutingStrategy;
use siss_job_router::executor::Executor;
use siss_job_router::types::RoutingRequest;
use siss_behavioral_firewall::checker::FirewallChecker;
use siss_behavioral_firewall::types::InspectionRequest;
use siss_feedback_router::scorer::Scorer;
use siss_feedback_router::crystallizer::Crystallizer;
use siss_feedback_router::types::CompletionRequest;

use crate::types::{AgentShellError, IntentResult};

/// Run the full value loop for a single intent.
/// Gatekeeper → Router → Firewall → Feedback
#[allow(clippy::too_many_arguments)]
pub async fn run_intent_pipeline(
    pool: &PgPool,
    // Identity
    persona_id: NodeId,
    tenant_id: NodeId,
    intent_mandate_id: NodeId,
    // Intent
    intent: &str,
    requested_tools: &[NodeId],
    estimated_cost: i64,
    // Traits
    signer: &dyn Signer,
    strategy: &dyn RoutingStrategy,
    executor: &dyn Executor,
    checkers: &[&dyn FirewallChecker],
    scorer: &dyn Scorer,
    crystallizer: &dyn Crystallizer,
) -> Result<IntentResult, AgentShellError> {
    // 1. Create Task
    let task_id_uuid = Uuid::new_v4();
    sqlx::query(
        "INSERT INTO tasks (id, tenant_id, intent, complexity_class, status, hardware_target) \
         VALUES ($1, $2, $3, 'simple'::complexity_class, 'pending'::task_status, 'local_mlx'::hardware_target)"
    )
    .bind(task_id_uuid)
    .bind(tenant_id.0)
    .bind(intent)
    .execute(pool)
    .await?;

    let task_id = NodeId(task_id_uuid);
    let tool_uuids: Vec<Uuid> = requested_tools.iter().map(|n| n.0).collect();

    // 2. Gatekeeper: authorize
    let auth_request = AuthorizationRequest {
        task_id,
        persona_id,
        intent_mandate_id,
        requested_tools: requested_tools.to_vec(),
        estimated_cost,
        tenant_id,
    };
    let _auth_result = siss_gatekeeper::pipeline::authorize_task(pool, signer, &auth_request).await?;

    // 3. Router: route + execute
    let routing_request = RoutingRequest {
        task_id,
        persona_id,
        tenant_id,
    };
    let routing_result = siss_job_router::pipeline::route_task(
        pool, strategy, executor, &routing_request,
    ).await?;

    // 4. Firewall: inspect
    let inspection_request = InspectionRequest {
        task_id,
        persona_id,
        intent_mandate_id,
        tenant_id,
        execution_output: routing_result.execution.output.clone(),
        token_cost: routing_result.execution.token_cost,
        authorized_tools: tool_uuids,
    };
    let inspection_result = siss_behavioral_firewall::pipeline::inspect_output(
        pool, checkers, &inspection_request,
    ).await.map_err(|e| AgentShellError::DatabaseError { message: e.to_string() })?;

    // Check if firewall blocked
    if matches!(inspection_result.verdict, Verdict::CriticalBlocked | Verdict::Blocked) {
        return Err(AgentShellError::FirewallBlocked {
            verdict: inspection_result.verdict,
            violations: inspection_result.violations,
        });
    }

    // 5. Feedback: complete
    let completion_request = CompletionRequest {
        task_id,
        persona_id,
        intent_mandate_id,
        tenant_id,
        verdict: inspection_result.verdict,
        execution_output: routing_result.execution.output.clone(),
        token_cost: routing_result.execution.token_cost,
        estimated_cost,
    };
    let completion_result = siss_feedback_router::pipeline::complete_task(
        pool, scorer, crystallizer, &completion_request,
    ).await?;

    Ok(IntentResult {
        task_id,
        output: routing_result.execution.output,
        verdict: inspection_result.verdict,
        quality_score: completion_result.quality_score,
        crystallized_memories: completion_result.crystallized_memories,
    })
}
