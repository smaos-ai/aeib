use l4_orchestration::{HotelPilot, Pilot};

#[test]
fn test_hotel_pilot_flow_completes() {
    let pilot = HotelPilot::new();
    let result = pilot.flow();

    assert!(result.is_ok());
    let checkpoints = result.unwrap();
    assert!(checkpoints.len() >= 5);

    for (i, cp) in checkpoints.iter().enumerate() {
        assert!(!cp.id.is_empty());
        assert!(!cp.action.is_empty());
        if i > 0 {
            assert!(cp.timestamp >= checkpoints[i - 1].timestamp);
        }
    }
}

#[test]
fn test_pilot_state_transitions() {
    let pilot = HotelPilot::new();
    let state = pilot.state();

    assert_eq!(state.current_state, "APPROVED");
    assert!(!state.request_id.is_empty());
}

#[test]
fn test_parallel_pilot_execution() {
    let pilots: Vec<HotelPilot> = (0..3).map(|_| HotelPilot::new()).collect();

    for pilot in pilots.iter() {
        let result = pilot.flow();
        assert!(result.is_ok());
    }
}

#[test]
fn test_pilot_checkpoint_audit_trail() {
    let pilot = HotelPilot::new();
    let flow = pilot.flow().unwrap();

    let mut prev_timestamp = flow[0].timestamp;
    for checkpoint in flow.iter().skip(1) {
        assert!(checkpoint.timestamp >= prev_timestamp);
        prev_timestamp = checkpoint.timestamp;
    }
}

#[test]
fn test_pilot_no_human_escalation_needed() {
    let pilot = HotelPilot::new();
    assert!(!pilot.human_escalation());
}
