use chrono::Utc;
use siss_ai_factory::{
    DeterministicReplayer, ExecutionTrace, ToolCall, ToolResult, StateSnapshot,
};
use std::collections::HashMap;
use uuid::Uuid;

/// Test 1: StateSnapshot captures all agent states
#[tokio::test]
async fn test_replayer_creates_snapshot_all_agents() {
    use siss_ai_factory::AgentState;

    let agent1 = Uuid::new_v4();
    let agent2 = Uuid::new_v4();

    let mut agents = HashMap::new();
    agents.insert(
        agent1,
        AgentState {
            agent_id: agent1,
            state_hash: [0u8; 32],
            message_count: 10,
            last_execution: Utc::now(),
        },
    );
    agents.insert(
        agent2,
        AgentState {
            agent_id: agent2,
            state_hash: [1u8; 32],
            message_count: 20,
            last_execution: Utc::now(),
        },
    );

    let snapshot = StateSnapshot::new(agents);
    assert_eq!(snapshot.agent_count(), 2);
    assert!(!snapshot.is_empty());
}

/// Test 2: Snapshot merkle root is deterministic (same state → same root)
#[tokio::test]
async fn test_replayer_snapshot_merkle_root_deterministic() {
    use siss_ai_factory::AgentState;

    let agent_id = Uuid::new_v4();
    let mut agents = HashMap::new();
    agents.insert(
        agent_id,
        AgentState {
            agent_id,
            state_hash: [42u8; 32],
            message_count: 100,
            last_execution: Utc::now(),
        },
    );

    let snap1 = StateSnapshot::new(agents.clone());
    let snap2 = StateSnapshot::new(agents);

    assert_eq!(snap1.merkle_root, snap2.merkle_root);
}

/// Test 3: Replay from snapshot produces execution result
#[tokio::test]
async fn test_replayer_replays_from_snapshot() {
    use siss_ai_factory::AgentState;

    let agent_id = Uuid::new_v4();
    let mut agents = HashMap::new();
    agents.insert(
        agent_id,
        AgentState {
            agent_id,
            state_hash: [0u8; 32],
            message_count: 5,
            last_execution: Utc::now(),
        },
    );

    let snapshot = StateSnapshot::new(agents);

    let tool_call = ToolCall {
        name: "test_tool".to_string(),
        args: "{}".to_string(),
    };
    let result = ToolResult {
        success: true,
        output: "ok".to_string(),
        error: None,
    };
    let trace = ExecutionTrace::new(agent_id, tool_call, result);

    let exec_result = DeterministicReplayer::replay_from_snapshot(&snapshot, &[trace])
        .await
        .unwrap();

    assert_eq!(exec_result.traces.len(), 1);
    assert_eq!(exec_result.final_snapshot.agent_count(), 1);
}

/// Test 4: Determinism verification detects trace differences
#[tokio::test]
async fn test_replayer_verify_determinism() {
    let agent_id = Uuid::new_v4();

    let tool_call1 = ToolCall {
        name: "tool1".to_string(),
        args: "{}".to_string(),
    };
    let result1 = ToolResult {
        success: true,
        output: "output1".to_string(),
        error: None,
    };

    let tool_call2 = ToolCall {
        name: "tool2".to_string(),
        args: "{}".to_string(),
    };
    let result2 = ToolResult {
        success: true,
        output: "output2".to_string(),
        error: None,
    };

    let trace1 = ExecutionTrace::new(agent_id, tool_call1, result1);
    let trace2 = ExecutionTrace::new(agent_id, tool_call2, result2);

    // Different tool calls should fail determinism check
    assert!(!DeterministicReplayer::verify_determinism(&trace1, &trace2));

    // Same trace should pass
    let trace3 = ExecutionTrace::new(agent_id, trace1.tool_call.clone(), trace1.result.clone());
    assert!(DeterministicReplayer::verify_determinism(&trace1, &trace3));
}

/// Test 5: Empty snapshot is handled correctly
#[tokio::test]
async fn test_replayer_empty_snapshot_no_agents() {
    let snapshot = StateSnapshot::new(HashMap::new());
    assert!(snapshot.is_empty());
    assert_eq!(snapshot.agent_count(), 0);

    let result = DeterministicReplayer::replay_from_snapshot(&snapshot, &[]).await;
    assert!(result.is_ok());
}
