use super::{ExecutionContext, HookResult, LifecycleHook, SessionContext};

/// Run a session-context hook across all registered hooks.
/// First Deny wins. Halt stops execution but isn't a violation.
pub fn run_session_hooks<F>(
    hooks: &[Box<dyn LifecycleHook>],
    ctx: &SessionContext,
    method: F,
) -> HookResult
where
    F: Fn(&dyn LifecycleHook, &SessionContext) -> HookResult,
{
    for hook in hooks {
        match method(&**hook, ctx) {
            HookResult::Continue => continue,
            result @ HookResult::Deny { .. } => return result,
            result @ HookResult::Halt { .. } => return result,
        }
    }
    HookResult::Continue
}

/// Run an execution-context hook across all registered hooks.
pub fn run_execution_hooks<F>(
    hooks: &[Box<dyn LifecycleHook>],
    ctx: &ExecutionContext,
    method: F,
) -> HookResult
where
    F: Fn(&dyn LifecycleHook, &ExecutionContext) -> HookResult,
{
    for hook in hooks {
        match method(&**hook, ctx) {
            HookResult::Continue => continue,
            result @ HookResult::Deny { .. } => return result,
            result @ HookResult::Halt { .. } => return result,
        }
    }
    HookResult::Continue
}

#[cfg(test)]
mod tests {
    use super::*;

    struct AlwaysContinue;
    impl LifecycleHook for AlwaysContinue {
        fn name(&self) -> &str {
            "always_continue"
        }
    }

    struct AlwaysDeny;
    impl LifecycleHook for AlwaysDeny {
        fn name(&self) -> &str {
            "always_deny"
        }
        fn on_session_start(&self, _ctx: &SessionContext) -> HookResult {
            HookResult::Deny {
                reason: "denied".into(),
            }
        }
        fn on_pre_execution(&self, _ctx: &ExecutionContext) -> HookResult {
            HookResult::Deny {
                reason: "denied".into(),
            }
        }
    }

    struct AlwaysHalt;
    impl LifecycleHook for AlwaysHalt {
        fn name(&self) -> &str {
            "always_halt"
        }
        fn on_pre_execution(&self, _ctx: &ExecutionContext) -> HookResult {
            HookResult::Halt {
                reason: "halted".into(),
            }
        }
    }

    fn make_session_ctx() -> SessionContext {
        SessionContext {
            session_id: siss_graph_core::node::NodeId::new(),
            persona_id: siss_graph_core::node::NodeId::new(),
            tenant_id: siss_graph_core::node::NodeId::new(),
        }
    }

    fn make_execution_ctx() -> ExecutionContext {
        ExecutionContext {
            task_id: None,
            intent: "test".into(),
            estimated_cost: 100,
            verdict: None,
            quality_score: None,
        }
    }

    #[test]
    fn test_all_continue() {
        let hooks: Vec<Box<dyn LifecycleHook>> =
            vec![Box::new(AlwaysContinue), Box::new(AlwaysContinue)];
        let result = run_session_hooks(&hooks, &make_session_ctx(), |h, c| h.on_session_start(c));
        assert_eq!(result, HookResult::Continue);
    }

    #[test]
    fn test_first_deny_wins() {
        let hooks: Vec<Box<dyn LifecycleHook>> = vec![
            Box::new(AlwaysContinue),
            Box::new(AlwaysDeny),
            Box::new(AlwaysContinue),
        ];
        let result = run_session_hooks(&hooks, &make_session_ctx(), |h, c| h.on_session_start(c));
        assert!(matches!(result, HookResult::Deny { .. }));
    }

    #[test]
    fn test_halt_stops_execution() {
        let hooks: Vec<Box<dyn LifecycleHook>> = vec![Box::new(AlwaysHalt), Box::new(AlwaysDeny)];
        let result =
            run_execution_hooks(&hooks, &make_execution_ctx(), |h, c| h.on_pre_execution(c));
        assert!(matches!(result, HookResult::Halt { .. }));
    }

    #[test]
    fn test_empty_hooks_continue() {
        let hooks: Vec<Box<dyn LifecycleHook>> = vec![];
        let result = run_session_hooks(&hooks, &make_session_ctx(), |h, c| h.on_session_start(c));
        assert_eq!(result, HookResult::Continue);
    }

    #[test]
    fn test_deny_before_continue() {
        let hooks: Vec<Box<dyn LifecycleHook>> =
            vec![Box::new(AlwaysDeny), Box::new(AlwaysContinue)];
        let result =
            run_execution_hooks(&hooks, &make_execution_ctx(), |h, c| h.on_pre_execution(c));
        assert!(matches!(result, HookResult::Deny { .. }));
    }
}
