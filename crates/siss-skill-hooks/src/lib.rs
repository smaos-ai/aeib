pub mod routing_hook;

pub use routing_hook::{HookOutput, MemoryRoutingHook};

#[cfg(test)]
mod tests {
    use super::*;
    use siss_agent_shell::hooks::{HookResult, LifecycleHook, ToolUseContext};
    use siss_context_cartography::types::MemoryEntry;
    use siss_context_cartography::zones::ZonalContextMap;
    use siss_graph_core::node::NodeId;
    use siss_graph_core::node::memory::ConsolidationTier;
    use siss_memory_plane::operators::CartographicOperatorSet;
    use uuid::Uuid;

    fn make_memory_entry(content: &str, confidence: f64) -> MemoryEntry {
        MemoryEntry {
            memory_id: Uuid::new_v4(),
            content: content.into(),
            confidence_score: confidence,
            tier: ConsolidationTier::Semantic,
            affective_signature: None,
        }
    }

    #[test]
    fn test_post_tool_use_routes_output_to_memory_plane() {
        let ops = CartographicOperatorSet::new(0.5, 0.8, 128);
        let hook = MemoryRoutingHook::new(ops, "standard".into(), 0.5);

        let gray_fog = vec![
            make_memory_entry("memory 1", 0.8),
            make_memory_entry("memory 2", 0.9),
        ];

        let map = ZonalContextMap {
            visible: vec![],
            gray_fog: gray_fog.clone(),
            black_fog_count: 0,
            token_budget_used: 500,
            token_budget_total: 1000,
        };

        let output = hook.process_post_tool_use(&map);

        // Verify that routed_memory_ids is not empty when gray_fog has entries
        assert!(
            !output.routed_memory_ids.is_empty(),
            "routed_memory_ids should not be empty"
        );
        assert_eq!(
            output.routed_memory_ids.len(),
            2,
            "should route all gray_fog entries"
        );
    }

    #[test]
    fn test_session_end_drains_via_rho_reconnaissance() {
        let ops = CartographicOperatorSet::new(0.5, 0.8, 128);
        let hook = MemoryRoutingHook::new(ops, "standard".into(), 0.5);

        let gray_fog = vec![
            make_memory_entry("memory a", 0.75),
            make_memory_entry("memory b", 0.82),
            make_memory_entry("memory c", 0.95),
        ];

        let map = ZonalContextMap {
            visible: vec![],
            gray_fog: gray_fog.clone(),
            black_fog_count: 5,
            token_budget_used: 800,
            token_budget_total: 1000,
        };

        let output = hook.process_session_end(&map);

        // Verify that all 3 gray_fog entries are drained
        assert_eq!(
            output.routed_memory_ids.len(),
            3,
            "should route all 3 gray_fog entries"
        );
    }

    #[test]
    fn test_pre_tool_use_blocks_black_fog_input() {
        let ops = CartographicOperatorSet::new(0.5, 0.8, 128);
        let hook = MemoryRoutingHook::new(ops, "standard".into(), 0.5);

        // Create a ToolUseContext with BlackFog zone
        let ctx_blocked = ToolUseContext {
            task_id: NodeId(Uuid::new_v4()),
            tool_id: Uuid::new_v4(),
            tool_name: "test_tool".into(),
            tool_input: serde_json::json!({"zone": "BlackFog", "content": "dangerous"}),
            tool_output: None,
        };

        let result = hook.on_pre_tool_use(&ctx_blocked);

        // Verify that BlackFog input is denied
        match result {
            HookResult::Deny { reason } => {
                assert_eq!(reason, "BlackFog injection blocked");
            }
            _ => panic!("Expected Deny result for BlackFog input"),
        }

        // Also test that non-BlackFog input is allowed
        let ctx_allowed = ToolUseContext {
            task_id: NodeId(Uuid::new_v4()),
            tool_id: Uuid::new_v4(),
            tool_name: "test_tool".into(),
            tool_input: serde_json::json!({"zone": "VisibleField", "content": "safe"}),
            tool_output: None,
        };

        let result_allowed = hook.on_pre_tool_use(&ctx_allowed);
        assert_eq!(result_allowed, HookResult::Continue);
    }
}
