use siss_os_sidecar::resource_state::ResourceState;
use siss_os_sidecar::safety_gate::{AdmissionGate, Decision, SafetyGate};
use std::sync::Arc;
use tokio::sync::Mutex;

#[test]
fn test_safety_gate_denies_on_memory_pressure() {
    let state = ResourceState::mock(0.30, 0.5, 8);
    let gate = SafetyGate::for_test(state);

    let decision = gate.admit_swap();
    assert!(
        matches!(decision, Decision::Deny { .. }),
        "Should deny when memory=0.30 > 0.25"
    );

    if let Decision::Deny { reason } = decision {
        assert!(reason.contains("Memory"), "Reason should mention memory");
    }
}

#[test]
fn test_safety_gate_denies_on_thermal_spike() {
    let state = ResourceState::mock(0.15, 3.5, 8);
    let gate = SafetyGate::for_test(state);

    let decision = gate.admit_swap();
    assert!(
        matches!(decision, Decision::Deny { .. }),
        "Should deny when thermal_slope=3.5 > 2.0"
    );

    if let Decision::Deny { reason } = decision {
        assert!(reason.contains("Thermal"), "Reason should mention thermal");
    }
}

#[test]
fn test_safety_gate_denies_on_metal_queue_saturation() {
    let state = ResourceState::mock(0.15, 0.5, 64);
    let gate = SafetyGate::for_test(state);

    let decision = gate.admit_swap();
    assert!(
        matches!(decision, Decision::Deny { .. }),
        "Should deny when metal_queue_depth=64 > 32"
    );

    if let Decision::Deny { reason } = decision {
        assert!(
            reason.contains("Metal"),
            "Reason should mention Metal queue"
        );
    }
}

#[test]
fn test_safety_gate_allows_when_all_clear() {
    let state = ResourceState::mock(0.15, 0.5, 8);
    let gate = SafetyGate::for_test(state);

    let decision = gate.admit_swap();
    assert_eq!(
        decision,
        Decision::Allow,
        "Should allow when memory=0.15, thermal=0.5, queue=8"
    );
}

#[tokio::test]
async fn test_safety_gate_with_async_state() {
    let initial_state = ResourceState::mock(0.10, 0.3, 5);
    let state = Arc::new(Mutex::new(initial_state));
    let gate = SafetyGate::new(state.clone());

    let decision = gate.admit_swap();
    assert_eq!(decision, Decision::Allow, "All metrics clear");

    {
        let mut state_guard = state.lock().await;
        state_guard.unified_memory_pct = 0.30;
    }

    let decision = gate.admit_swap();
    assert!(
        matches!(decision, Decision::Deny { .. }),
        "Should deny after memory updated to 0.30"
    );
}
