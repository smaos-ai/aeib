/// Phase 40: A2A Discovery — Autonomous Service Discovery & Registry
/// 2 TDD tests covering:
/// - Local service discovery by name
/// - Cross-boundary agent lookup across regional boundaries
use siss_job_router::a2a_discovery::{
    A2ADiscoveryRegistry, AgentServiceRecord, NetworkBoundary, DiscoveryQuery,
    DiscoveryError,
};
use chrono::Utc;
use uuid::Uuid;

// ============================================================================
// TEST 1: Local discovery success — find agent by service name
// ============================================================================

#[test]
fn test_local_discovery_success() {
    let registry = A2ADiscoveryRegistry::new();

    let agent_id = Uuid::new_v4();
    let record = AgentServiceRecord {
        agent_id,
        service_name: "video_processing".to_string(),
        region: "us-west-1".to_string(),
        network_boundary: NetworkBoundary::Local,
        capabilities: vec!["transcode".to_string(), "optimize".to_string()],
        last_heartbeat: Utc::now(),
    };

    // Register agent
    let register_result = registry.register_agent(record.clone());
    assert!(register_result.is_ok(), "Registration must succeed");

    // Discover by service name
    let query = DiscoveryQuery {
        service_name: "video_processing".to_string(),
        required_region: None,
        required_boundary: Some(NetworkBoundary::Local),
        required_capabilities: vec![],
    };

    let discovery_result = registry.discover_service(&query);
    assert!(discovery_result.is_ok(), "Discovery must succeed");

    let result = discovery_result.unwrap();
    assert_eq!(result.agents.len(), 1);
    assert_eq!(result.agents[0].agent_id, agent_id);
    assert_eq!(result.agents[0].service_name, "video_processing");
}

// ============================================================================
// TEST 2: Cross-boundary lookup — find agents across regional boundaries
// ============================================================================

#[test]
fn test_cross_boundary_lookup() {
    let local_registry = A2ADiscoveryRegistry::new();
    let regional_registry = A2ADiscoveryRegistry::new();

    // Register agent in regional registry
    let regional_agent_id = Uuid::new_v4();
    let regional_record = AgentServiceRecord {
        agent_id: regional_agent_id,
        service_name: "analytics".to_string(),
        region: "eu-central-1".to_string(),
        network_boundary: NetworkBoundary::Regional,
        capabilities: vec!["aggregation".to_string(), "reporting".to_string()],
        last_heartbeat: Utc::now(),
    };

    let _ = regional_registry.register_agent(regional_record);

    // Query from local registry with cross-boundary support
    let query = DiscoveryQuery {
        service_name: "analytics".to_string(),
        required_region: Some("eu-central-1".to_string()),
        required_boundary: Some(NetworkBoundary::Regional),
        required_capabilities: vec!["aggregation".to_string()],
    };

    // Perform cross-boundary discovery
    let remote_registries = vec![std::sync::Arc::new(regional_registry)];
    let discovery_result = local_registry.discover_cross_boundary(&query, &remote_registries);

    assert!(
        discovery_result.is_ok(),
        "Cross-boundary discovery must succeed"
    );
    let result = discovery_result.unwrap();
    assert_eq!(result.agents.len(), 1);
    assert_eq!(result.agents[0].agent_id, regional_agent_id);
    assert_eq!(result.agents[0].network_boundary, NetworkBoundary::Regional);
}
