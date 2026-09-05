use siss_graph_core::node::governance::Severity;

use super::FirewallChecker;
use crate::context::InspectionContext;
use crate::types::Violation;

pub struct BudgetComplianceChecker;

impl FirewallChecker for BudgetComplianceChecker {
    fn name(&self) -> &str {
        "budget_compliance"
    }

    fn check(&self, context: &InspectionContext) -> Vec<Violation> {
        if context.token_cost > context.budget_remaining {
            vec![Violation {
                checker: self.name().into(),
                severity: Severity::Critical,
                message: format!(
                    "Execution cost {} exceeded remaining budget {}",
                    context.token_cost, context.budget_remaining
                ),
            }]
        } else {
            vec![]
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_context(token_cost: i64, budget_remaining: i64) -> InspectionContext {
        InspectionContext {
            task_id: uuid::Uuid::nil(),
            token_cost,
            output: serde_json::json!({}),
            authorized_tools: vec![],
            budget_remaining,
        }
    }

    #[test]
    fn test_within_budget_no_violation() {
        let checker = BudgetComplianceChecker;
        assert!(checker.check(&make_context(100, 500)).is_empty());
    }

    #[test]
    fn test_exact_budget_no_violation() {
        let checker = BudgetComplianceChecker;
        assert!(checker.check(&make_context(500, 500)).is_empty());
    }

    #[test]
    fn test_over_budget_critical_violation() {
        let checker = BudgetComplianceChecker;
        let violations = checker.check(&make_context(501, 500));
        assert_eq!(violations.len(), 1);
        assert_eq!(violations[0].severity, Severity::Critical);
        assert_eq!(violations[0].checker, "budget_compliance");
    }
}
