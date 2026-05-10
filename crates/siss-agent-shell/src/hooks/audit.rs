use super::{ExecutionContext, HookResult, LifecycleHook, SessionContext, ToolUseContext};

/// Logs all lifecycle events. In the future this will write to the knowledge graph.
/// For now it collects events in memory for testing/debugging.
pub struct AuditLogHook {
    // In a real implementation, this would write to the DB.
    // For Phase 1, it's a no-op that always continues.
}

impl AuditLogHook {
    pub fn new() -> Self {
        Self {}
    }
}

impl Default for AuditLogHook {
    fn default() -> Self {
        Self::new()
    }
}

impl LifecycleHook for AuditLogHook {
    fn name(&self) -> &str {
        "audit_log_hook"
    }

    fn on_session_start(&self, _ctx: &SessionContext) -> HookResult {
        // Future: log to knowledge graph
        HookResult::Continue
    }

    fn on_pre_execution(&self, _ctx: &ExecutionContext) -> HookResult {
        HookResult::Continue
    }

    fn on_post_execution(&self, _ctx: &ExecutionContext) -> HookResult {
        HookResult::Continue
    }

    fn on_pre_tool_use(&self, _ctx: &ToolUseContext) -> HookResult {
        HookResult::Continue
    }

    fn on_post_tool_use(&self, _ctx: &ToolUseContext) -> HookResult {
        HookResult::Continue
    }

    fn on_stop(&self, _ctx: &SessionContext) -> HookResult {
        HookResult::Continue
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use siss_graph_core::node::NodeId;

    #[test]
    fn test_audit_hook_always_continues() {
        let hook = AuditLogHook::new();
        let ctx = SessionContext {
            session_id: NodeId::new(),
            persona_id: NodeId::new(),
            tenant_id: NodeId::new(),
        };
        assert_eq!(hook.on_session_start(&ctx), HookResult::Continue);
        assert_eq!(hook.on_stop(&ctx), HookResult::Continue);
    }
}
