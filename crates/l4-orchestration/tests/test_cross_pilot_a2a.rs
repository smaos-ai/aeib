use l4_orchestration::{HotelPilot, GlassPilot, SchoolPilot, Pilot};

#[test]
fn test_hotel_to_glass_communication() {
    let hotel = HotelPilot::new();
    let glass = GlassPilot::new();

    let hotel_flow = hotel.flow().unwrap();
    let glass_flow = glass.flow().unwrap();

    assert!(!hotel_flow.is_empty());
    assert!(!glass_flow.is_empty());

    let hotel_id = &hotel.state().request_id;
    let glass_id = &glass.state().request_id;

    assert_ne!(hotel_id, glass_id);
}

#[test]
fn test_parallel_pilot_execution_no_conflict() {
    let pilots = vec![
        ("hotel", HotelPilot::new()),
        ("glass", GlassPilot::new()),
        ("school", SchoolPilot::new()),
    ];

    let mut results = vec![];
    for (_name, pilot) = pilots.iter() {
        let flow = pilot.flow().unwrap();
        results.push(flow);
    }

    assert_eq!(results.len(), 3);
    for result in results {
        assert!(result.len() > 0);
    }
}

#[test]
fn test_pilot_states_with_all_contexts() {
    let hotel = HotelPilot::new();
    let glass = GlassPilot::new();
    let school = SchoolPilot::new();

    let hotel_state = hotel.state();
    let glass_state = glass.state();
    let school_state = school.state();

    assert!(hotel_state.policy_context.is_some());
    assert!(glass_state.policy_context.is_some());
    assert!(school_state.policy_context.is_some());

    assert!(hotel_state.evaluation_score.is_some());
    assert!(glass_state.evaluation_score.is_some());
    assert!(school_state.evaluation_score.is_some());
}

#[test]
fn test_pilot_escalation_requirements() {
    let hotel = HotelPilot::new();
    let glass = GlassPilot::new();
    let school = SchoolPilot::new();

    assert!(!hotel.human_escalation());
    assert!(glass.human_escalation());
    assert!(!school.human_escalation());
}

#[test]
fn test_cross_pilot_audit_trail_completeness() {
    let hotel = HotelPilot::new();
    let glass = GlassPilot::new();
    let school = SchoolPilot::new();

    let hotel_flow = hotel.flow().unwrap();
    let glass_flow = glass.flow().unwrap();
    let school_flow = school.flow().unwrap();

    for flow in vec![&hotel_flow, &glass_flow, &school_flow] {
        let has_l1 = flow.iter().any(|cp| cp.layer.as_ref().map_or(false, |l| l == "L1"));
        let has_l8 = flow.iter().any(|cp| cp.layer.as_ref().map_or(false, |l| l == "L8"));
        assert!(has_l1);
        assert!(has_l8);
    }
}

#[test]
fn test_pilot_communication_context() {
    let hotel = HotelPilot::new();
    let hotel_state = hotel.state();

    assert!(hotel_state.policy_context.as_ref().unwrap().contains("Article 50"));
    assert!(hotel_state.knowledge_context.as_ref().unwrap().contains("L2"));
    assert!(hotel_state.permit_decision.as_ref().unwrap().contains("L3"));
    assert!(hotel_state.proof_trail.as_ref().unwrap().contains("ed25519"));
}

#[test]
fn test_parallel_pilot_message_routing() {
    let pilots: Vec<Box<dyn Pilot>> = vec![
        Box::new(HotelPilot::new()),
        Box::new(GlassPilot::new()),
        Box::new(SchoolPilot::new()),
    ];

    for pilot in pilots {
        let state = pilot.state();
        assert!(!state.request_id.is_empty());
        assert!(!state.current_state.is_empty());
    }
}
