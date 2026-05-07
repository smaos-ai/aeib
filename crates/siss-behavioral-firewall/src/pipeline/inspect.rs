use sqlx::PgPool;
use uuid::Uuid;

use crate::checker::FirewallChecker;
use crate::context::InspectionContext;
use crate::types::{FirewallError, Violation};

pub async fn run_checkers(
    pool: &PgPool,
    task_id: Uuid,
    intent_mandate_id: Uuid,
    token_cost: i64,
    output: serde_json::Value,
    authorized_tools: Vec<Uuid>,
    checkers: &[&dyn FirewallChecker],
) -> Result<Vec<Violation>, FirewallError> {
    let mandate_row = siss_graph_db::repo::node_repo::fetch_intent_mandate(pool, intent_mandate_id)
        .await?
        .ok_or(FirewallError::TaskNotFound { task_id: intent_mandate_id })?;

    let (_id, _tenant, budget_limit, budget_spent, _risk_class, _allowed_tools) = mandate_row;
    let budget_remaining = budget_limit - budget_spent;

    let context = InspectionContext {
        task_id,
        token_cost,
        output,
        authorized_tools,
        budget_remaining,
    };

    let mut all_violations = Vec::new();
    for checker in checkers {
        all_violations.extend(checker.check(&context));
    }

    Ok(all_violations)
}
