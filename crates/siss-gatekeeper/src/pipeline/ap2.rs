use sqlx::PgPool;
use uuid::Uuid;

use crate::types::GatekeeperError;

/// Pipeline Step 3: Verify AP2 budget and tool authorization, then debit.
/// Returns (risk_class, budget_remaining_before_debit) for use in later steps.
pub async fn check_and_debit(
    pool: &PgPool,
    intent_mandate_id: Uuid,
    requested_tools: &[Uuid],
    estimated_cost: i64,
) -> Result<(String, i64), GatekeeperError> {
    // Fetch mandate
    let mandate_row = siss_graph_db::repo::node_repo::fetch_intent_mandate(pool, intent_mandate_id)
        .await?
        .ok_or(GatekeeperError::TaskNotFound {
            task_id: intent_mandate_id,
        })?;

    let (_id, _tenant_id, budget_limit, budget_spent, risk_class, allowed_tools) = mandate_row;
    let remaining = budget_limit - budget_spent;

    // Check each tool is in allowed_tools
    for &tool_id in requested_tools {
        if !allowed_tools.contains(&tool_id) {
            return Err(GatekeeperError::ToolNotAuthorized {
                tool_id,
                mandate_id: intent_mandate_id,
            });
        }
    }

    // Check budget
    if remaining < estimated_cost {
        return Err(GatekeeperError::BudgetExceeded {
            requested: estimated_cost,
            remaining,
        });
    }

    // Atomically debit
    siss_graph_db::repo::ap2_repo::debit_mandate(pool, intent_mandate_id, estimated_cost).await?;

    Ok((risk_class, remaining))
}
