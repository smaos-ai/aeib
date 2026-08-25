/// Phase 40: 5G Slicing Engine — Network Slice Lifecycle & QoS Management
/// 4 TDD tests covering:
/// - Slice provisioning with profile selection
/// - QoS constraint enforcement
/// - Resource allocation within slice bounds
/// - Slice conflict detection
use siss_job_router::slicing_engine::{
    SlicingEngine, SliceProfile, SliceStatus, QosConstraints, SlicingError,
};

// ============================================================================
// TEST 1: Provision eMBB slice with high bandwidth QoS
// ============================================================================

#[test]
fn test_provision_slice_embbb() {
    let engine = SlicingEngine::new();
    let qos = QosConstraints {
        min_bandwidth_mbps: 500,
        max_latency_ms: 50,
        min_reliability_percent: 95,
    };

    let result = engine.provision_slice(SliceProfile::eMBB, &qos);

    assert!(result.is_ok(), "eMBB slice provisioning must succeed");
    let slice = result.unwrap();
    assert_eq!(slice.profile, SliceProfile::eMBB);
    assert_eq!(slice.status, SliceStatus::Active);
    assert_eq!(slice.qos_constraints.min_bandwidth_mbps, 500);
}

// ============================================================================
// TEST 2: Provision URLLC slice with ultra-low latency budget
// ============================================================================

#[test]
fn test_provision_slice_urllc() {
    let engine = SlicingEngine::new();
    let qos = QosConstraints {
        min_bandwidth_mbps: 50,
        max_latency_ms: 5,
        min_reliability_percent: 99,
    };

    let result = engine.provision_slice(SliceProfile::URLLC, &qos);

    assert!(result.is_ok(), "URLLC slice provisioning must succeed");
    let slice = result.unwrap();
    assert_eq!(slice.profile, SliceProfile::URLLC);
    assert!(
        slice.qos_constraints.max_latency_ms <= 5,
        "URLLC must have ultra-low latency"
    );
}

// ============================================================================
// TEST 3: Detect conflicting slice configurations
// ============================================================================

#[test]
fn test_detect_slice_conflicts() {
    let engine = SlicingEngine::new();

    // First slice provisioned
    let qos1 = QosConstraints {
        min_bandwidth_mbps: 300,
        max_latency_ms: 20,
        min_reliability_percent: 98,
    };
    let result1 = engine.provision_slice(SliceProfile::URLLC, &qos1);
    assert!(result1.is_ok());
    let _slice1 = result1.unwrap();

    // Second conflicting slice (URLLC profile already provisioned)
    let qos2 = QosConstraints {
        min_bandwidth_mbps: 200,
        max_latency_ms: 10,
        min_reliability_percent: 99,
    };

    // Attempting to provision another URLLC should detect conflict
    let result2 = engine.validate_slice_conflicts(SliceProfile::URLLC, &qos2);

    assert!(
        matches!(result2, Err(SlicingError::ConflictingSlices)),
        "Must detect conflicting slice profiles"
    );
}

// ============================================================================
// TEST 4: Allocate resources within slice bounds
// ============================================================================

#[test]
fn test_allocate_resources_within_slice() {
    let engine = SlicingEngine::new();

    let qos = QosConstraints {
        min_bandwidth_mbps: 1000,
        max_latency_ms: 100,
        min_reliability_percent: 95,
    };

    let result = engine.provision_slice(SliceProfile::eMBB, &qos);
    assert!(result.is_ok());
    let slice = result.unwrap();

    // Allocate within bounds (600 < 1000)
    let alloc_result = engine.allocate_resources(
        slice.slice_id,
        600,  // bandwidth_mbps
        50,   // latency_budget_ms
    );

    assert!(alloc_result.is_ok(), "Allocation within bounds must succeed");
    let allocation = alloc_result.unwrap();
    assert_eq!(allocation.allocated_bandwidth_mbps, 600);
    assert_eq!(allocation.allocated_latency_budget_ms, 50);

    // Allocate exceeding bounds (2000 > 1000)
    let exceed_result = engine.allocate_resources(
        slice.slice_id,
        2000,
        50,
    );

    assert!(
        matches!(exceed_result, Err(SlicingError::ResourceConstraintViolation)),
        "Allocation exceeding bounds must fail"
    );
}
