pub mod runner;
pub mod gatekeeper;
pub mod budget;
pub mod audit;

use serde::{Deserialize, Serialize};
use uuid::Uuid;

use siss_graph_core::node::NodeId;
use siss_behavioral_firewall::types::Verdict;

/// Result of a lifecycle hook invocation.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum HookResult {
    Continue,
    Halt { reason: String },
    Deny { reason: String },
}

/// Context for SessionStart and Stop hooks.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionContext {
    pub session_id: NodeId,
    pub persona_id: NodeId,
    pub tenant_id: NodeId,
}

/// Context for PreExecution and PostExecution hooks.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionContext {
    pub task_id: Option<NodeId>,
    pub intent: String,
    pub estimated_cost: i64,
    pub verdict: Option<Verdict>,
    pub quality_score: Option<f64>,
}

/// Context for PreToolUse and PostToolUse hooks.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolUseContext {
    pub task_id: NodeId,
    pub tool_id: Uuid,
    pub tool_name: String,
}

/// Trait for deterministic lifecycle hooks.
/// All methods have default implementations that return Continue.
pub trait LifecycleHook: Send + Sync {
    fn name(&self) -> &str;
    fn on_session_start(&self, _ctx: &SessionContext) -> HookResult { HookResult::Continue }
    fn on_pre_execution(&self, _ctx: &ExecutionContext) -> HookResult { HookResult::Continue }
    fn on_post_execution(&self, _ctx: &ExecutionContext) -> HookResult { HookResult::Continue }
    fn on_pre_tool_use(&self, _ctx: &ToolUseContext) -> HookResult { HookResult::Continue }
    fn on_post_tool_use(&self, _ctx: &ToolUseContext) -> HookResult { HookResult::Continue }
    fn on_stop(&self, _ctx: &SessionContext) -> HookResult { HookResult::Continue }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hook_result_equality() {
        assert_eq!(HookResult::Continue, HookResult::Continue);
        assert_ne!(HookResult::Continue, HookResult::Halt { reason: "x".into() });
        assert_ne!(
            HookResult::Halt { reason: "x".into() },
            HookResult::Deny { reason: "x".into() }
        );
    }
}
