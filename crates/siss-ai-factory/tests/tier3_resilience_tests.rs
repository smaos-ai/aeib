use chrono::Utc;
use siss_ai_factory::{
    AiFactoryChaosScenario, RecoveryValidator, StateSnapshot, AgentState,
    DeterministicReplayer, ExecutionTrace, ToolCall, ToolResult,
};
use std::collections::HashMap;
use uuid::Uuid;

/// Test 11: All scenarios recover within RTO <5 seconds
#[tokio::test]
async fn test_recovery_rto_under_5_seconds() {
    for scenario in AiFactoryChaosScenario::all_scenarios() {
        let recovery_time = scenario.expected_recovery_time();
        let is_ok = RecoveryValidator::validate_rto(&scenario).await;

        assert!(
            is_ok.is_ok(),
            "Scenario {:?} violates RTO: {:?}",
            scenario,
            recovery_time
        );
    }
}

/// Test 12: RPO compliance - zero data loss during failover
#[tokio::test]
async fn test_recovery_rpo_zero_no_data_loss() {
    let result = RecoveryValidator::validate_rpo(0).await;
    assert!(result.is_ok(), "RPO validation failed for zero loss");

    // RPO=0 means no data loss is acceptable
    let result_fail = RecoveryValidator::validate_rpo(1).await;
    assert!(
        result_fail.is_err(),
        "RPO validation should fail for any data loss"
    );
}

/// Test 13: State consistency verified via merkle root
#[tokio::test]
async fn test_recovery_state_consistency() {
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

    let snapshot1 = StateSnapshot::new(agents.clone());
    let snapshot2 = StateSnapshot::new(agents);

    let result = RecoveryValidator::validate_state_consistency(&snapshot1, &snapshot2).await;
    assert!(result.is_ok(), "State consistency validation failed");

    // Merkle roots should match
    assert_eq!(snapshot1.merkle_root, snapshot2.merkle_root);
}

/// Test 14: Cascading failure recovery
#[tokio::test]
async fn test_recovery_from_cascading_failure() {
    let scenario = AiFactoryChaosScenario::CascadingFailure;
    let result = scenario.inject().await.unwrap();

    assert_eq!(result.scenario, "CascadingFailure");
    assert!(result.resolved_at_ms.is_some());

    let resolved = result.resolved_at_ms.unwrap();
    assert!(
        resolved <= 5000,
        "Cascading failure recovery {} exceeds RTO 5s",
        resolved
    );

    // Validate it meets RTO
    let validation = RecoveryValidator::validate_rto(&scenario).await;
    assert!(validation.is_ok(), "Cascading failure violates RTO");
}

/// Test 15: Determinism after replay
#[tokio::test]
async fn test_recovery_determinism_after_replay() {
    let agent_id = Uuid::new_v4();
    let mut agents = HashMap::new();
    agents.insert(
        agent_id,
        AgentState {
            agent_id,
            state_hash: [10u8; 32],
            message_count: 42,
            last_execution: Utc::now(),
        },
    );

    let snapshot = StateSnapshot::new(agents);

    // Create two identical traces
    let tool_call = ToolCall {
        name: "deterministic_tool".to_string(),
        args: r#"{"param": "value"}"#.to_string(),
    };
    let result = ToolResult {
        success: true,
        output: "consistent_result".to_string(),
        error: None,
    };

    let trace1 = ExecutionTrace::new(agent_id, tool_call.clone(), result.clone());
    let trace2 = ExecutionTrace::new(agent_id, tool_call, result);

    // Verify determinism
    assert!(DeterministicReplayer::verify_determinism(&trace1, &trace2));

    // Replay should be deterministic
    let exec_result = DeterministicReplayer::replay_from_snapshot(&snapshot, &[trace1])
        .await
        .unwrap();
    assert_eq!(exec_result.traces.len(), 1);
}
