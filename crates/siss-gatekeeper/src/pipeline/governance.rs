use sqlx::PgPool;
use uuid::Uuid;

use crate::evaluator::{EvaluationContext, RuleEvaluator};
use crate::types::GatekeeperError;

/// Pipeline Step 4: Evaluate all active GovernanceRules for the "Task" node type.
#[allow(clippy::too_many_arguments)]
pub async fn evaluate_rules(
    pool: &PgPool,
    tenant_id: Uuid,
    task_id: Uuid,
    persona_id: Uuid,
    task_tenant_id: Uuid,
    persona_tenant_id: Uuid,
    budget_remaining: i64,
    estimated_cost: i64,
) -> Result<(), GatekeeperError> {
    let rules =
        siss_graph_db::repo::governance_repo::find_active_rules(pool, "Task", tenant_id).await?;

    let evaluator = RuleEvaluator::default();
    let ctx = EvaluationContext {
        task_tenant_id,
        persona_tenant_id,
        budget_remaining,
        estimated_cost,
    };

    for rule in &rules {
        let passes = evaluator.evaluate(&rule.name, &ctx).unwrap_or(false);

        if !passes {
            match rule.severity.as_str() {
                "advisory" => {
                    // Log but don't block
                    let _ = siss_graph_db::repo::governance_repo::log_violation(
                        pool, rule.id, task_id, tenant_id,
                    )
                    .await;
                }
                "enforced" => {
                    let _ = siss_graph_db::repo::governance_repo::log_violation(
                        pool, rule.id, task_id, tenant_id,
                    )
                    .await;
                    return Err(GatekeeperError::EnforcedRuleViolation {
                        rule_name: rule.name.clone(),
                    });
                }
                "critical" => {
                    let _ = siss_graph_db::repo::governance_repo::log_violation(
                        pool, rule.id, task_id, tenant_id,
                    )
                    .await;
                    // Freeze persona
                    let _ = siss_graph_db::repo::node_repo::freeze_persona(pool, persona_id).await;
                    return Err(GatekeeperError::CriticalRuleViolation {
                        rule_name: rule.name.clone(),
                        persona_frozen: true,
                    });
                }
                _ => {
                    // Unknown severity — treat as advisory
                    let _ = siss_graph_db::repo::governance_repo::log_violation(
                        pool, rule.id, task_id, tenant_id,
                    )
                    .await;
                }
            }
        }
    }

    Ok(())
}
