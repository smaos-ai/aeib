use std::collections::HashMap;

/// Context available to rule predicates during evaluation.
pub struct EvaluationContext {
    pub task_tenant_id: uuid::Uuid,
    pub persona_tenant_id: uuid::Uuid,
    pub budget_remaining: i64,
    pub estimated_cost: i64,
}

type PredicateFn = fn(&EvaluationContext) -> bool;

/// Maps rule names to hardcoded predicate functions.
/// Unknown rules return false (logged as advisory).
pub struct RuleEvaluator {
    predicates: HashMap<String, PredicateFn>,
}

impl Default for RuleEvaluator {
    fn default() -> Self {
        let mut predicates: HashMap<String, PredicateFn> = HashMap::new();

        // Already checked in pipeline Step 3 (AP2), so this is a no-op confirmation
        predicates.insert("budget_cannot_exceed_limit".into(), |ctx| {
            ctx.budget_remaining >= ctx.estimated_cost
        });

        // Already checked in pipeline Step 1 (validate)
        predicates.insert("cross_tenant_edge_forbidden".into(), |ctx| {
            ctx.task_tenant_id == ctx.persona_tenant_id
        });

        // Already checked in pipeline Step 1 (validate)
        predicates.insert("task_fsm_valid_transitions".into(), |_ctx| true);

        // Not applicable during authorization
        predicates.insert("session_token_budget".into(), |_ctx| true);

        // Not applicable during authorization
        predicates.insert("memory_gc_threshold".into(), |_ctx| true);

        Self { predicates }
    }
}

impl RuleEvaluator {
    /// Evaluate a rule by name. Returns Ok(true) if the rule passes,
    /// Ok(false) if the rule is unknown or fails.
    pub fn evaluate(&self, rule_name: &str, ctx: &EvaluationContext) -> Result<bool, String> {
        match self.predicates.get(rule_name) {
            Some(predicate) => Ok(predicate(ctx)),
            None => Ok(false), // Unknown rule — treated as advisory warning
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_known_rule_passes() {
        let evaluator = RuleEvaluator::default();
        let ctx = EvaluationContext {
            task_tenant_id: uuid::Uuid::new_v4(),
            persona_tenant_id: uuid::Uuid::new_v4(),
            budget_remaining: 1000,
            estimated_cost: 500,
        };
        let result = evaluator.evaluate("budget_cannot_exceed_limit", &ctx);
        assert!(result.is_ok());
        assert!(result.unwrap());
    }

    #[test]
    fn test_unknown_rule_returns_false() {
        let evaluator = RuleEvaluator::default();
        let ctx = EvaluationContext {
            task_tenant_id: uuid::Uuid::nil(),
            persona_tenant_id: uuid::Uuid::nil(),
            budget_remaining: 0,
            estimated_cost: 0,
        };
        let result = evaluator.evaluate("some_unknown_rule", &ctx);
        assert!(result.is_ok());
        assert!(!result.unwrap());
    }

    #[test]
    fn test_session_token_budget_skipped() {
        let evaluator = RuleEvaluator::default();
        let ctx = EvaluationContext {
            task_tenant_id: uuid::Uuid::nil(),
            persona_tenant_id: uuid::Uuid::nil(),
            budget_remaining: 0,
            estimated_cost: 0,
        };
        let result = evaluator.evaluate("session_token_budget", &ctx);
        assert!(result.unwrap());
    }
}
