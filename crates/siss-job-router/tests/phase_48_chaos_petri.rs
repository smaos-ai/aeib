use chrono::Utc;
/// Phase 48: Chaos Petri & The Twin Pillars of Sovereignty
/// 8 TDD tests covering three fail-closed invariants:
/// - Invariant 1: Type-State RCE Failure Machine (Chaos Petri)
/// - Invariant 2: Compile-Time Geometric Trajectory Validation (iWorld-Bench)
/// - Invariant 3: Sovereign Telemetry Sidecar + CIPO Loop Closure
use siss_job_router::chaos_petri::{ChaosInjection, RceStateMachine};
use siss_job_router::iworld_bench::{
    BoundingBox, GeometricBounds, GeometricViolation, Point3D, Trajectory, TrajectoryValidator,
    TypedTrajectory, Unvalidated,
};
use siss_job_router::telemetry_sidecar::{
    SovereignTelemetrySidecar, TelemetryEvent, TelemetryEventKind,
};
use uuid::Uuid;

// ============================================================================
// INVARIANT 1: TYPE-STATE RCE FAILURE MACHINE
// ============================================================================

// ============================================================================
// TEST 1: Network dropout pauses RCE (no crash)
// ============================================================================

#[test]
fn test_chaos_network_dropout_pauses_rce() {
    let agent_id = Uuid::new_v4();
    let rce = RceStateMachine::new(agent_id);

    let chaos = ChaosInjection::NetworkDropout { duration_ms: 100 };

    let paused = rce.inject_failure(chaos);
    // Paused type should be returned; no panic
    let (resumed, _) = paused.resume();

    // State machine should return to Running
    let _running = resumed;
}

// ============================================================================
// TEST 2: MCP socket drop pauses RCE
// ============================================================================

#[test]
fn test_chaos_mcp_socket_drop_pauses_rce() {
    let agent_id = Uuid::new_v4();
    let rce = RceStateMachine::new(agent_id);

    let chaos = ChaosInjection::McpSocketDrop {
        socket_path: "/run/mcp.sock".to_string(),
    };

    let paused = rce.inject_failure(chaos);
    let (resumed, _) = paused.resume();
    let _running = resumed;
}

// ============================================================================
// TEST 3: Malformed mandate pauses RCE
// ============================================================================

#[test]
fn test_chaos_malformed_mandate_pauses_rce() {
    let agent_id = Uuid::new_v4();
    let rce = RceStateMachine::new(agent_id);

    let chaos = ChaosInjection::MalformedMandate {
        reason: "bad signature".to_string(),
    };

    let paused = rce.inject_failure(chaos);
    let (resumed, _) = paused.resume();
    let _running = resumed;
}

// ============================================================================
// TEST 4: Queue drains FIFO on resume
// ============================================================================

#[test]
fn test_chaos_resume_drains_queue_fifo() {
    let agent_id = Uuid::new_v4();
    let mut rce = RceStateMachine::new(agent_id);

    rce.add_command("cmd1".to_string());
    rce.add_command("cmd2".to_string());
    rce.add_command("cmd3".to_string());

    let chaos = ChaosInjection::NetworkDropout { duration_ms: 100 };
    let paused = rce.inject_failure(chaos);

    let (resumed, drained) = paused.resume();
    assert_eq!(drained, vec!["cmd1", "cmd2", "cmd3"]);

    let _running = resumed;
}

// ============================================================================
// INVARIANT 2: COMPILE-TIME GEOMETRIC TRAJECTORY VALIDATION
// ============================================================================

static CHAOS_ARENA: GeometricBounds = GeometricBounds {
    x_range: (0.0, 100.0),
    y_range: (0.0, 100.0),
    z_range: (0.0, 10.0),
    obstacle_zones: &[BoundingBox {
        x_range: (40.0, 60.0),
        y_range: (40.0, 60.0),
        z_range: (0.0, 10.0),
    }],
};

// ============================================================================
// TEST 5: Valid trajectory within bounds accepted
// ============================================================================

#[test]
fn test_iworld_trajectory_within_bounds_accepted() {
    let trajectory = Trajectory {
        waypoints: vec![
            Point3D {
                x: 0.0,
                y: 0.0,
                z: 0.0,
            },
            Point3D {
                x: 30.0,
                y: 30.0,
                z: 5.0,
            },
            Point3D {
                x: 80.0,
                y: 80.0,
                z: 9.0,
            },
        ],
    };

    let unvalidated = TypedTrajectory::new(trajectory);
    let result = TrajectoryValidator::validate(unvalidated, &CHAOS_ARENA);

    assert!(result.is_ok(), "valid trajectory should be accepted");
    let _validated = result.unwrap();
}

// ============================================================================
// TEST 6: Trajectory exceeding bounds rejected
// ============================================================================

#[test]
fn test_iworld_trajectory_out_of_bounds_rejected() {
    let trajectory = Trajectory {
        waypoints: vec![Point3D {
            x: 150.0,
            y: 0.0,
            z: 0.0,
        }],
    };

    let unvalidated = TypedTrajectory::new(trajectory);
    let result = TrajectoryValidator::validate(unvalidated, &CHAOS_ARENA);

    assert!(
        matches!(
            result,
            Err(GeometricViolation::OutOfBounds { point }) if point.x == 150.0
        ),
        "out-of-bounds waypoint should be rejected"
    );
}

// ============================================================================
// TEST 7: Trajectory with obstacle collision rejected
// ============================================================================

#[test]
fn test_iworld_obstacle_collision_rejected() {
    let trajectory = Trajectory {
        waypoints: vec![Point3D {
            x: 50.0,
            y: 50.0,
            z: 5.0,
        }],
    };

    let unvalidated = TypedTrajectory::new(trajectory);
    let result = TrajectoryValidator::validate(unvalidated, &CHAOS_ARENA);

    assert!(
        matches!(
            result,
            Err(GeometricViolation::ObstacleCollision { zone_index: 0, .. })
        ),
        "obstacle collision should be rejected"
    );
}

// ============================================================================
// INVARIANT 3: SOVEREIGN TELEMETRY SIDECAR + CIPO LOOP CLOSURE
// ============================================================================

// ============================================================================
// TEST 8: Telemetry CIPO loop closes
// ============================================================================

#[test]
fn test_telemetry_cipo_loop_closes() {
    let sidecar = SovereignTelemetrySidecar::new();

    // Log 5 GateFailure events
    for i in 0..5 {
        let event = TelemetryEvent {
            event_id: Uuid::new_v4(),
            kind: TelemetryEventKind::GateFailure,
            agent_id: None,
            payload_summary: format!("gate_failure_{i}"),
            timestamp: Utc::now(),
        };
        sidecar
            .log_event(event)
            .expect("event logging should succeed");
    }

    // Export as CipoTrace
    let traces = sidecar.export_as_cipo_traces();
    assert_eq!(traces.len(), 5, "should export 5 traces");

    // Distill signals via CIPO
    let signals = sidecar.distill_signals();
    assert!(!signals.is_empty(), "should produce signals");
    assert_eq!(
        signals[0].confidence, 0.5,
        "confidence should be 0.5 for 5 traces"
    );
    assert!(!signals[0].lesson.is_empty(), "lesson should be non-empty");

    // Verify no cloud telemetry
    assert!(
        sidecar.assert_no_cloud_telemetry(),
        "no cloud endpoints should be present"
    );
}
