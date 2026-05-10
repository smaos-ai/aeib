pub mod persist;
pub mod validate;

use sqlx::PgPool;

use siss_graph_core::node::NodeId;

use crate::crystallizer::{CrystallizationContext, Crystallizer};
use crate::scorer::{Scorer, ScoringContext};
use crate::types::{CompletionRequest, CompletionResult, FeedbackError};

/// The sole entry point for task completion.
/// Validates → scores → crystallizes → persists → completes.
pub async fn complete_task(
    pool: &PgPool,
    scorer: &dyn Scorer,
    crystallizer: &dyn Crystallizer,
    request: &CompletionRequest,
) -> Result<CompletionResult, FeedbackError> {
    let task_id = request.task_id.0;
    let tenant_id = request.tenant_id.0;

    // Step 1+2: Validate and transition to crystallizing
    let intent = validate::validate_and_transition(pool, task_id, tenant_id).await?;

    // Step 3: Score
    let scoring_ctx = ScoringContext {
        verdict: request.verdict,
        token_cost: request.token_cost,
        estimated_cost: request.estimated_cost,
    };
    let quality_score = scorer.score(&scoring_ctx);

    // Step 4: Crystallize
    let crystal_ctx = CrystallizationContext {
        task_id,
        intent,
        execution_output: request.execution_output.clone(),
        quality_score,
    };
    let memories = crystallizer.crystallize(&crystal_ctx);

    // Steps 5+6: Persist and complete
    persist::persist_and_complete(pool, task_id, tenant_id, quality_score, &memories).await?;

    Ok(CompletionResult {
        task_id: NodeId(task_id),
        quality_score,
        crystallized_memories: memories,
    })
}
