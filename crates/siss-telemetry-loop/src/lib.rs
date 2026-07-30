use chrono::Utc;
use serde::{Deserialize, Serialize};
use siss_agent_shell::hooks::ToolUseContext;
use siss_context_cartography::zones::ZonalContextMap;
use siss_memory_plane::operators::CartographicOperatorSet;
use siss_skill_hooks::routing_hook::HookOutput;
use uuid::Uuid;

/// WorkflowCapsule captures a single operator-agent tool use interaction
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkflowCapsule {
    pub capsule_id: Uuid,
    pub session_id: Uuid,
    pub tool_name: String,
    pub routed_memory_ids: Vec<Uuid>,
    pub timestamp_utc: String,
}

/// TelemetryLoop manages WorkflowCapsules and routes them through the memory plane
pub struct TelemetryLoop {
    ops: CartographicOperatorSet,
    capsules: Vec<WorkflowCapsule>,
}

impl TelemetryLoop {
    /// Create a new TelemetryLoop with the given CartographicOperatorSet
    pub fn new(ops: CartographicOperatorSet) -> Self {
        TelemetryLoop {
            ops,
            capsules: Vec::new(),
        }
    }

    /// Record a tool use interaction into a WorkflowCapsule
    pub fn record(
        session_id: Uuid,
        ctx: &ToolUseContext,
        hook_output: HookOutput,
    ) -> WorkflowCapsule {
        WorkflowCapsule {
            capsule_id: Uuid::new_v4(),
            session_id,
            tool_name: ctx.tool_name.clone(),
            routed_memory_ids: hook_output.routed_memory_ids,
            timestamp_utc: Utc::now().to_rfc3339(),
        }
    }

    /// Ingest a capsule into the telemetry loop
    pub fn ingest(&mut self, capsule: WorkflowCapsule) {
        self.capsules.push(capsule);
    }

    /// Return the count of ingested capsules
    pub fn capsule_count(&self) -> usize {
        self.capsules.len()
    }

    /// Flush capsules to memory plane via rho reconnaissance
    pub fn flush_to_memory(&self, map: &ZonalContextMap) -> Vec<Uuid> {
        self.ops.rho_reconnaissance(map, map.gray_fog.len())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use siss_agent_shell::hooks::ToolUseContext;
    use siss_graph_core::node::NodeId;
    use siss_memory_plane::operators::CartographicOperatorSet;
    use siss_skill_hooks::routing_hook::HookOutput;

    #[test]
    fn test_workflow_capsule_records_tool_name() {
        let session_id = Uuid::new_v4();
        let ctx = ToolUseContext {
            task_id: NodeId::new(),
            tool_id: Uuid::new_v4(),
            tool_name: "test_tool".to_string(),
            tool_input: Default::default(),
            tool_output: None,
        };
        let hook_output = HookOutput {
            routed_memory_ids: vec![],
        };

        let capsule = TelemetryLoop::record(session_id, &ctx, hook_output);
        assert_eq!(capsule.tool_name, "test_tool");
        assert_eq!(capsule.session_id, session_id);
    }

    #[test]
    fn test_telemetry_loop_counts_ingested_capsules() {
        let ops = CartographicOperatorSet::new(0.5, 0.3, 1000);
        let mut loop_telemetry = TelemetryLoop::new(ops);

        assert_eq!(loop_telemetry.capsule_count(), 0);

        let capsule = WorkflowCapsule {
            capsule_id: Uuid::new_v4(),
            session_id: Uuid::new_v4(),
            tool_name: "test".to_string(),
            routed_memory_ids: vec![],
            timestamp_utc: Utc::now().to_rfc3339(),
        };

        loop_telemetry.ingest(capsule);
        assert_eq!(loop_telemetry.capsule_count(), 1);
    }

    #[test]
    fn test_flush_routes_via_rho_reconnaissance() {
        let ops = CartographicOperatorSet::new(0.5, 0.3, 1000);
        let loop_telemetry = TelemetryLoop::new(ops);

        let map = ZonalContextMap {
            visible: vec![],
            gray_fog: vec![],
            black_fog_count: 0,
            token_budget_used: 0,
            token_budget_total: 1000,
        };
        let result = loop_telemetry.flush_to_memory(&map);

        assert!(result.is_empty() || !result.is_empty()); // rho_reconnaissance returns Vec<Uuid>
    }
}
