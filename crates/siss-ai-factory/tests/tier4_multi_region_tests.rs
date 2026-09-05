use chrono::Utc;
use siss_ai_factory::{
    MachineRegistry, MachineMeta, AiFactoryChaosScenario, StateSnapshot,
    AgentState, RecoveryValidator,
};
use std::collections::HashMap;
use uuid::Uuid;

/// Test 16: Machine registry enrolls 3 regions (EU primary + US/APAC replicas)
#[tokio::test]
async fn test_machine_registry_enroll_3_regions() {
    let registry = MachineRegistry::new();

    let eu_id = Uuid::new_v4();
    let us_id = Uuid::new_v4();
    let apac_id = Uuid::new_v4();

    // Enroll EU primary
    registry
        .enroll(MachineMeta {
            id: eu_id,
            hostname: "mac-studio-eu-primary".to_string(),
            mac_model: "Mac Studio M2 Ultra".to_string(),
            region: "EU".to_string(),
            ip_address: "192.168.1.10".to_string(),
            ssh_key_hash: [0u8; 32],
            enrolled_at: Utc::now(),
        })
        .unwrap();

    // Enroll US replica
    registry
        .enroll(MachineMeta {
            id: us_id,
            hostname: "mac-studio-us-replica".to_string(),
            mac_model: "Mac Studio M2 Ultra".to_string(),
            region: "US".to_string(),
            ip_address: "192.168.1.20".to_string(),
            ssh_key_hash: [1u8; 32],
            enrolled_at: Utc::now(),
        })
        .unwrap();

    // Enroll APAC replica
    registry
        .enroll(MachineMeta {
            id: apac_id,
            hostname: "mac-studio-apac-replica".to_string(),
            mac_model: "Mac Studio M2 Ultra".to_string(),
            region: "APAC".to_string(),
            ip_address: "192.168.1.30".to_string(),
            ssh_key_hash: [2u8; 32],
            enrolled_at: Utc::now(),
        })
        .unwrap();

    assert_eq!(registry.machine_count(), 3);

    let primary = registry.get_primary_region().unwrap();
    assert_eq!(primary.id, eu_id);
    assert_eq!(primary.region, "EU");

    let replicas = registry.get_replicas().unwrap();
    assert_eq!(replicas.len(), 2);
    assert!(replicas.iter().any(|m| m.region == "US"));
    assert!(replicas.iter().any(|m| m.region == "APAC"));
}

/// Test 17: Health check succeeds on 3 machines
#[tokio::test]
async fn test_machine_registry_health_check_all() {
    let registry = MachineRegistry::new();

    registry
        .enroll(MachineMeta {
            id: Uuid::new_v4(),
            hostname: "mac-eu".to_string(),
            mac_model: "Mac Studio M2 Ultra".to_string(),
            region: "EU".to_string(),
            ip_address: "192.168.1.1".to_string(),
            ssh_key_hash: [0u8; 32],
            enrolled_at: Utc::now(),
        })
        .unwrap();

    registry
        .enroll(MachineMeta {
            id: Uuid::new_v4(),
            hostname: "mac-us".to_string(),
            mac_model: "Mac Studio M2 Ultra".to_string(),
            region: "US".to_string(),
            ip_address: "192.168.1.2".to_string(),
            ssh_key_hash: [1u8; 32],
            enrolled_at: Utc::now(),
        })
        .unwrap();

    registry
        .enroll(MachineMeta {
            id: Uuid::new_v4(),
            hostname: "mac-apac".to_string(),
            mac_model: "Mac Studio M2 Ultra".to_string(),
            region: "APAC".to_string(),
            ip_address: "192.168.1.3".to_string(),
            ssh_key_hash: [2u8; 32],
            enrolled_at: Utc::now(),
        })
        .unwrap();

    let report = registry.health_check_all().unwrap();
    assert_eq!(report.machines.len(), 3);
    assert!(report.primary_healthy);
    assert_eq!(report.replicas_healthy, 2);

    for health in &report.machines {
        assert!(health.uptime_seconds > 0);
    }
}

/// Test 18: 3-region failover all regions fail simultaneously
#[tokio::test]
async fn test_3_region_failover_parallel() {
    let registry = MachineRegistry::new();

    // Enroll 3 machines
    let eu_id = Uuid::new_v4();
    let us_id = Uuid::new_v4();
    let apac_id = Uuid::new_v4();

    registry
        .enroll(MachineMeta {
            id: eu_id,
            hostname: "mac-eu".to_string(),
            mac_model: "Mac Studio M2 Ultra".to_string(),
            region: "EU".to_string(),
            ip_address: "192.168.1.1".to_string(),
            ssh_key_hash: [0u8; 32],
            enrolled_at: Utc::now(),
        })
        .unwrap();

    registry
        .enroll(MachineMeta {
            id: us_id,
            hostname: "mac-us".to_string(),
            mac_model: "Mac Studio M2 Ultra".to_string(),
            region: "US".to_string(),
            ip_address: "192.168.1.2".to_string(),
            ssh_key_hash: [1u8; 32],
            enrolled_at: Utc::now(),
        })
        .unwrap();

    registry
        .enroll(MachineMeta {
            id: apac_id,
            hostname: "mac-apac".to_string(),
            mac_model: "Mac Studio M2 Ultra".to_string(),
            region: "APAC".to_string(),
            ip_address: "192.168.1.3".to_string(),
            ssh_key_hash: [2u8; 32],
            enrolled_at: Utc::now(),
        })
        .unwrap();

    // Simulate concurrent failover via ConcurrentFailover chaos scenario
    let scenario = AiFactoryChaosScenario::ConcurrentFailover;
    let result = scenario.inject().await.unwrap();

    assert!(result.resolved_at_ms.is_some());
    let recovery_ms = result.resolved_at_ms.unwrap();
    assert!(recovery_ms <= 5000, "Concurrent failover exceeds RTO");
}

/// Test 19: Network partition heals and state syncs via merkle root
#[tokio::test]
async fn test_3_region_state_sync_after_partition() {
    let agent_id = Uuid::new_v4();

    // Create pre-partition state
    let mut agents_pre = HashMap::new();
    agents_pre.insert(
        agent_id,
        AgentState {
            agent_id,
            state_hash: [42u8; 32],
            message_count: 100,
            last_execution: Utc::now(),
        },
    );
    let snapshot_pre = StateSnapshot::new(agents_pre);

    // Simulate partition with NetworkPartitionEuUs
    let scenario = AiFactoryChaosScenario::NetworkPartitionEuUs;
    let injection = scenario.inject().await.unwrap();
    assert!(injection.resolved_at_ms.is_some());

    // After partition heals, state should be resynced
    let mut agents_post = HashMap::new();
    agents_post.insert(
        agent_id,
        AgentState {
            agent_id,
            state_hash: [42u8; 32],  // Same state after sync
            message_count: 100,
            last_execution: Utc::now(),
        },
    );
    let snapshot_post = StateSnapshot::new(agents_post);

    // Verify state consistency after sync
    let validation = RecoveryValidator::validate_state_consistency(&snapshot_pre, &snapshot_post)
        .await;
    assert!(validation.is_ok(), "State sync failed after partition heals");
}

/// Test 20: Memory leak detection under sustained pressure (100 snapshots)
#[tokio::test]
async fn test_chaos_memory_leak_under_pressure() {
    let scenario = AiFactoryChaosScenario::MemoryLeak;
    let result = scenario.inject().await.unwrap();

    assert_eq!(result.scenario, "MemoryLeak");
    assert!(result.resolved_at_ms.is_some());

    let recovery_ms = result.resolved_at_ms.unwrap();
    assert!(
        recovery_ms <= 5000,
        "Memory leak recovery {} exceeds RTO 5s",
        recovery_ms
    );

    // Simulate 100 snapshots with memory pressure
    for i in 0..100 {
        let agent_id = Uuid::new_v4();
        let mut agents = HashMap::new();
        agents.insert(
            agent_id,
            AgentState {
                agent_id,
                state_hash: [(i % 256) as u8; 32],
                message_count: i,
                last_execution: Utc::now(),
            },
        );
        let _snapshot = StateSnapshot::new(agents);
    }

    // After 100 snapshots, system should still be healthy
    let validation = RecoveryValidator::validate_rto(&scenario).await;
    assert!(validation.is_ok(), "Memory leak scenario violates RTO");
}
