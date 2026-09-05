use serde::{Deserialize, Serialize};
use siss_agent_shell::hooks::{HookResult, LifecycleHook, SessionContext, ToolUseContext};
use siss_context_cartography::zones::ZonalContextMap;
use siss_memory_plane::operators::CartographicOperatorSet;
use uuid::Uuid;

/// Output from skill execution that needs routing to memory plane
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HookOutput {
    pub routed_memory_ids: Vec<Uuid>,
}

/// Memory routing hook for skill execution lifecycle
pub struct MemoryRoutingHook {
    ops: CartographicOperatorSet,
    guard: String,
    threshold: f64,
}

impl MemoryRoutingHook {
    pub fn new(ops: CartographicOperatorSet, guard: String, threshold: f64) -> Self {
        Self {
            ops,
            guard,
            threshold,
        }
    }

    /// Route tool use output to memory plane
    pub fn process_post_tool_use(&self, map: &ZonalContextMap) -> HookOutput {
        let ids = self.ops.rho_reconnaissance(map, map.gray_fog.len());
        HookOutput {
            routed_memory_ids: ids,
        }
    }

    /// Drain session state via rho reconnaissance on session end
    pub fn process_session_end(&self, map: &ZonalContextMap) -> HookOutput {
        let ids = self.ops.rho_reconnaissance(map, map.gray_fog.len());
        HookOutput {
            routed_memory_ids: ids,
        }
    }
}

impl LifecycleHook for MemoryRoutingHook {
    fn name(&self) -> &str {
        "memory-routing-hook"
    }

    fn on_pre_tool_use(&self, ctx: &ToolUseContext) -> HookResult {
        // Check if tool input contains zone field with BlackFog value
        if let Some(zone) = ctx.tool_input.get("zone") {
            if zone == "BlackFog" {
                return HookResult::Deny {
                    reason: "BlackFog injection blocked".to_string(),
                };
            }
        }
        HookResult::Continue
    }

    fn on_post_tool_use(&self, _ctx: &ToolUseContext) -> HookResult {
        HookResult::Continue
    }

    fn on_stop(&self, _ctx: &SessionContext) -> HookResult {
        HookResult::Continue
    }
}
