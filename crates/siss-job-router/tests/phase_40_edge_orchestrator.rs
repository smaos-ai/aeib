/// Phase 40: Edge Orchestrator — 5G-Aware Edge Scheduling
/// 6 TDD tests covering:
/// - Latency constraint enforcement (RTT budgets)
/// - Network slice affinity routing
/// - Geo-distributed edge node selection
/// - Failover and redundancy
use siss_job_router::edge_orchestrator::{
    EdgeNode, EdgeOrchestrator, OrchestratorConfig, EdgeScheduleResult, EdgeScheduleError,
};
use uuid::Uuid;

// ============================================================================
// TEST 1: Edge node selection respects latency RTT budget
// ============================================================================

#[test]
fn test_latency_rtt_budget_enforcement() {
    let config = OrchestratorConfig {
        max_rtt_ms: 50,
        enable_failover: true,
        geo_zone: "us-west-2".to_string(),
    };

    let nodes = vec![
        EdgeNode {
            id: Uuid::new_v4(),
            name: "edge-1".to_string(),
            rtt_ms: 20,
            available_cpu_cores: 16,
            available_memory_mb: 32768,
            network_slice: "eMBB".to_string(),
            geo_zone: "us-west-2".to_string(),
        },
        EdgeNode {
            id: Uuid::new_v4(),
            name: "edge-2".to_string(),
            rtt_ms: 100, // exceeds budget
            available_cpu_cores: 32,
            available_memory_mb: 65536,
            network_slice: "eMBB".to_string(),
            geo_zone: "us-west-1".to_string(),
        },
    ];

    let orchestrator = EdgeOrchestrator::new(config);
    let result = orchestrator.select_edge_node(&nodes, 4, 8192);

    assert!(result.is_ok());
    let selected = result.unwrap();
    assert_eq!(selected.node.rtt_ms, 20, "Must select node within RTT budget");
}

// ============================================================================
// TEST 2: Slice affinity routing ensures task placement on correct slice
// ============================================================================

#[test]
fn test_slice_affinity_routing() {
    let config = OrchestratorConfig {
        max_rtt_ms: 100,
        enable_failover: true,
        geo_zone: "eu-central-1".to_string(),
    };

    let nodes = vec![
        EdgeNode {
            id: Uuid::new_v4(),
            name: "edge-urllc".to_string(),
            rtt_ms: 5, // Ultra-reliable
            available_cpu_cores: 8,
            available_memory_mb: 16384,
            network_slice: "URLLC".to_string(),
            geo_zone: "eu-central-1".to_string(),
        },
        EdgeNode {
            id: Uuid::new_v4(),
            name: "edge-mmtc".to_string(),
            rtt_ms: 50,
            available_cpu_cores: 32,
            available_memory_mb: 65536,
            network_slice: "mMTC".to_string(),
            geo_zone: "eu-central-1".to_string(),
        },
    ];

    let orchestrator = EdgeOrchestrator::new(config);

    // URLLC task should go to URLLC slice
    let result = orchestrator.select_edge_node_for_slice(&nodes, "URLLC", 2, 4096);
    assert!(result.is_ok());
    let selected = result.unwrap();
    assert_eq!(
        selected.node.network_slice, "URLLC",
        "URLLC task must route to URLLC slice"
    );
}

// ============================================================================
// TEST 3: Geo-distributed failover to secondary zone
// ============================================================================

#[test]
fn test_geo_distributed_failover() {
    let config = OrchestratorConfig {
        max_rtt_ms: 100,
        enable_failover: true,
        geo_zone: "us-east-1".to_string(),
    };

    let nodes = vec![
        EdgeNode {
            id: Uuid::new_v4(),
            name: "edge-primary".to_string(),
            rtt_ms: 30,
            available_cpu_cores: 0, // Out of capacity
            available_memory_mb: 0,
            network_slice: "eMBB".to_string(),
            geo_zone: "us-east-1".to_string(),
        },
        EdgeNode {
            id: Uuid::new_v4(),
            name: "edge-secondary".to_string(),
            rtt_ms: 60, // Higher latency but available
            available_cpu_cores: 16,
            available_memory_mb: 32768,
            network_slice: "eMBB".to_string(),
            geo_zone: "us-east-2".to_string(),
        },
    ];

    let orchestrator = EdgeOrchestrator::new(config);
    let result = orchestrator.select_edge_node(&nodes, 8, 16384);

    assert!(result.is_ok());
    let selected = result.unwrap();
    assert_eq!(
        selected.node.name, "edge-secondary",
        "Must failover to secondary zone when primary is full"
    );
}

// ============================================================================
// TEST 4: Resource constraint validation (CPU/memory)
// ============================================================================

#[test]
fn test_resource_constraint_validation() {
    let config = OrchestratorConfig {
        max_rtt_ms: 50,
        enable_failover: false,
        geo_zone: "ap-southeast-1".to_string(),
    };

    let nodes = vec![
        EdgeNode {
            id: Uuid::new_v4(),
            name: "edge-1".to_string(),
            rtt_ms: 20,
            available_cpu_cores: 4,
            available_memory_mb: 8192,
            network_slice: "mMTC".to_string(),
            geo_zone: "ap-southeast-1".to_string(),
        },
    ];

    let orchestrator = EdgeOrchestrator::new(config);

    // Request exceeds available resources
    let result = orchestrator.select_edge_node(&nodes, 16, 32768);
    assert!(
        matches!(result, Err(EdgeScheduleError::InsufficientResources)),
        "Must reject request exceeding available resources"
    );
}

// ============================================================================
// TEST 5: Cost optimization among candidate nodes
// ============================================================================

#[test]
fn test_cost_optimized_node_selection() {
    let config = OrchestratorConfig {
        max_rtt_ms: 100,
        enable_failover: true,
        geo_zone: "eu-west-1".to_string(),
    };

    let nodes = vec![
        EdgeNode {
            id: Uuid::new_v4(),
            name: "edge-expensive".to_string(),
            rtt_ms: 10,
            available_cpu_cores: 32,
            available_memory_mb: 65536,
            network_slice: "eMBB".to_string(),
            geo_zone: "eu-west-1".to_string(),
        },
        EdgeNode {
            id: Uuid::new_v4(),
            name: "edge-cheap".to_string(),
            rtt_ms: 40,
            available_cpu_cores: 16,
            available_memory_mb: 32768,
            network_slice: "eMBB".to_string(),
            geo_zone: "eu-west-1".to_string(),
        },
    ];

    let orchestrator = EdgeOrchestrator::new(config);
    let result = orchestrator.select_edge_node_optimized(&nodes, 4, 8192);

    assert!(result.is_ok());
    let selected = result.unwrap();
    assert!(selected.optimization_score > 0.0);
}

// ============================================================================
// TEST 6: Latency constraint violation rejection
// ============================================================================

#[test]
fn test_latency_constraint_violation_rejection() {
    let config = OrchestratorConfig {
        max_rtt_ms: 30,
        enable_failover: false,
        geo_zone: "ap-northeast-1".to_string(),
    };

    let nodes = vec![
        EdgeNode {
            id: Uuid::new_v4(),
            name: "edge-slow".to_string(),
            rtt_ms: 50, // exceeds budget
            available_cpu_cores: 16,
            available_memory_mb: 32768,
            network_slice: "eMBB".to_string(),
            geo_zone: "ap-northeast-1".to_string(),
        },
    ];

    let orchestrator = EdgeOrchestrator::new(config);
    let result = orchestrator.select_edge_node(&nodes, 4, 8192);

    assert!(
        matches!(result, Err(EdgeScheduleError::LatencyConstraintViolation)),
        "Must reject nodes exceeding RTT budget"
    );
}
