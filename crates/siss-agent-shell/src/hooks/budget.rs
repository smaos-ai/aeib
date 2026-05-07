use super::{ExecutionContext, HookResult, LifecycleHook};

/// Checks remaining AP2 budget before each intent.
pub struct BudgetGuardHook {
    pub budget_remaining: i64,
}

impl BudgetGuardHook {
    pub fn new(budget_remaining: i64) -> Self {
        Self { budget_remaining }
    }
}

impl LifecycleHook for BudgetGuardHook {
    fn name(&self) -> &str {
        "budget_guard_hook"
    }

    fn on_pre_execution(&self, ctx: &ExecutionContext) -> HookResult {
        if ctx.estimated_cost > self.budget_remaining {
            HookResult::Deny {
                reason: format!(
                    "Insufficient budget: estimated {} > remaining {}",
                    ctx.estimated_cost, self.budget_remaining
                ),
            }
        } else {
            HookResult::Continue
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_ctx(cost: i64) -> ExecutionContext {
        ExecutionContext {
            task_id: None,
            intent: "test".into(),
            estimated_cost: cost,
            verdict: None,
            quality_score: None,
        }
    }

    #[test]
    fn test_within_budget_continues() {
        let hook = BudgetGuardHook::new(1000);
        assert_eq!(hook.on_pre_execution(&make_ctx(500)), HookResult::Continue);
    }

    #[test]
    fn test_exact_budget_continues() {
        let hook = BudgetGuardHook::new(500);
        assert_eq!(hook.on_pre_execution(&make_ctx(500)), HookResult::Continue);
    }

    #[test]
    fn test_over_budget_denies() {
        let hook = BudgetGuardHook::new(500);
        assert!(matches!(hook.on_pre_execution(&make_ctx(501)), HookResult::Deny { .. }));
    }
}
