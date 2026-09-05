use super::{ExecutionContext, HookResult, LifecycleHook};

/// Checks that the Persona is not frozen before each execution.
/// This is a pre-flight check — the actual Gatekeeper pipeline also checks,
/// but this hook catches it early before a Task is even created.
pub struct GatekeeperHook {
    pub persona_frozen: bool, // Set during session start, updated if frozen during session
}

impl GatekeeperHook {
    pub fn new(persona_frozen: bool) -> Self {
        Self { persona_frozen }
    }
}

impl LifecycleHook for GatekeeperHook {
    fn name(&self) -> &str {
        "gatekeeper_hook"
    }

    fn on_pre_execution(&self, _ctx: &ExecutionContext) -> HookResult {
        if self.persona_frozen {
            HookResult::Deny {
                reason: "Persona is frozen — cannot execute".into(),
            }
        } else {
            HookResult::Continue
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_ctx() -> ExecutionContext {
        ExecutionContext {
            task_id: None,
            intent: "test".into(),
            estimated_cost: 100,
            verdict: None,
            quality_score: None,
        }
    }

    #[test]
    fn test_not_frozen_continues() {
        let hook = GatekeeperHook::new(false);
        assert_eq!(hook.on_pre_execution(&make_ctx()), HookResult::Continue);
    }

    #[test]
    fn test_frozen_denies() {
        let hook = GatekeeperHook::new(true);
        assert!(matches!(
            hook.on_pre_execution(&make_ctx()),
            HookResult::Deny { .. }
        ));
    }
}
