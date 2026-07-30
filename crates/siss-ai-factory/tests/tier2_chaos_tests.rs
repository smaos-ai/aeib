use siss_ai_factory::AiFactoryChaosScenario;

/// Test 6: RegionPrimaryDown scenario injects chaos and recovers
#[tokio::test]
async fn test_chaos_region_primary_down() {
    let scenario = AiFactoryChaosScenario::RegionPrimaryDown;
    let result = scenario.inject().await.unwrap();

    assert_eq!(result.scenario, "RegionPrimaryDown");
    assert!(result.resolved_at_ms.is_some());
    let resolved = result.resolved_at_ms.unwrap();
    assert!(resolved <= 5000, "Recovery time {} exceeds RTO 5s", resolved);
}

/// Test 7: NetworkPartitionEuUs detected and triggers failover
#[tokio::test]
async fn test_chaos_network_partition() {
    let scenario = AiFactoryChaosScenario::NetworkPartitionEuUs;
    let result = scenario.inject().await.unwrap();

    assert_eq!(result.scenario, "NetworkPartitionEuUs");
    assert!(result.resolved_at_ms.is_some());
    let resolved = result.resolved_at_ms.unwrap();
    assert!(resolved <= 5000, "Recovery time {} exceeds RTO 5s", resolved);
}

/// Test 8: ToolCallTimeout triggers retry logic
#[tokio::test]
async fn test_chaos_tool_timeout() {
    let scenario = AiFactoryChaosScenario::ToolCallTimeout;
    let result = scenario.inject().await.unwrap();

    assert_eq!(result.scenario, "ToolCallTimeout");
    assert!(result.resolved_at_ms.is_some());
    let resolved = result.resolved_at_ms.unwrap();
    assert!(resolved <= 5000, "Recovery time {} exceeds RTO 5s", resolved);
    assert!(result.messages_lost <= 1, "Tool timeout should lose at most 1 message");
}

/// Test 9: StateChecksumMismatch flags divergence
#[tokio::test]
async fn test_chaos_state_mismatch() {
    let scenario = AiFactoryChaosScenario::StateChecksumMismatch;
    let result = scenario.inject().await.unwrap();

    assert_eq!(result.scenario, "StateChecksumMismatch");
    assert!(result.resolved_at_ms.is_some());
    let resolved = result.resolved_at_ms.unwrap();
    assert!(resolved <= 5000, "Recovery time {} exceeds RTO 5s", resolved);
}

/// Test 10: AgentPanic triggers supervisor restart
#[tokio::test]
async fn test_chaos_agent_panic() {
    let scenario = AiFactoryChaosScenario::AgentPanic;
    let result = scenario.inject().await.unwrap();

    assert_eq!(result.scenario, "AgentPanic");
    assert!(result.resolved_at_ms.is_some());
    let resolved = result.resolved_at_ms.unwrap();
    assert!(
        resolved <= 5000,
        "Agent restart time {} exceeds RTO 5s",
        resolved
    );
}
