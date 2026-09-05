/// Phase 40: MCP-A2A Bridge — Protocol Adaptation for Cross-Network Routing
/// 2 TDD tests covering:
/// - MCP marshalling round-trip preservation
/// - Hop limit enforcement and validation
use siss_job_router::mcp_a2a_bridge::{
    McpA2ABridge, BridgeError,
};
use siss_swarm_coordinator::A2AMessage;
use uuid::Uuid;

// ============================================================================
// TEST 1: MCP marshalling round-trip preserves payload integrity
// ============================================================================

#[test]
fn test_mcp_marshalling_round_trip() {
    let bridge = McpA2ABridge::new(10);

    let from_agent = Uuid::new_v4();
    let to_agent = Uuid::new_v4();
    let payload = "test_payload_data".to_string();

    let msg = A2AMessage::new(from_agent, to_agent, payload.clone());

    // Marshal to MCP envelope
    let marshal_result = bridge.marshal_to_mcp(&msg, None, 5);
    assert!(
        marshal_result.is_ok(),
        "Marshalling to MCP must succeed"
    );
    let envelope = marshal_result.unwrap();

    assert_eq!(
        envelope.routing_metadata.hop_count, 0,
        "Initial hop count must be 0"
    );
    assert_eq!(envelope.routing_metadata.priority, 5);

    // Unmarshal back to A2A message
    let unmarshal_result = bridge.unmarshal_from_mcp(&envelope);
    assert!(
        unmarshal_result.is_ok(),
        "Unmarshalling from MCP must succeed"
    );
    let restored_msg = unmarshal_result.unwrap();

    assert_eq!(
        restored_msg.from_agent_id, from_agent,
        "From agent ID must be preserved"
    );
    assert_eq!(
        restored_msg.to_agent_id, to_agent,
        "To agent ID must be preserved"
    );
    assert_eq!(
        restored_msg.payload, payload,
        "Payload must be preserved"
    );
}

// ============================================================================
// TEST 2: Hop limit enforcement prevents infinite routing loops
// ============================================================================

#[test]
fn test_hop_limit_enforcement() {
    let max_hops = 3;
    let bridge = McpA2ABridge::new(max_hops);

    let from_agent = Uuid::new_v4();
    let to_agent = Uuid::new_v4();
    let payload = "test_payload".to_string();

    let msg = A2AMessage::new(from_agent, to_agent, payload);

    // Marshal with priority
    let marshal_result = bridge.marshal_to_mcp(&msg, None, 1);
    assert!(marshal_result.is_ok());
    let mut envelope = marshal_result.unwrap();

    // Simulate hop traversals
    for hop in 0..max_hops {
        let route_result = bridge.route_with_hop_check(&mut envelope);
        assert!(
            route_result.is_ok(),
            "Routing should succeed at hop {}",
            hop
        );
        assert_eq!(
            envelope.routing_metadata.hop_count,
            (hop + 1) as u8,
            "Hop count must increment"
        );
    }

    // One more hop should exceed limit
    let exceed_result = bridge.route_with_hop_check(&mut envelope);
    assert!(
        matches!(exceed_result, Err(BridgeError::HopLimitExceeded)),
        "Must reject routing when hop limit exceeded"
    );
}
