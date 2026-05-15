use siss_enclave::{
    model::modality::Modality,
    orchestrator::evolution_gate::Verdict,
    routing::omni_router::{OmniRoute, RouteTarget, RoutingDecision},
};

#[test]
fn test_all_modalities_approved_routes_all_to_shadow() {
    let omni = OmniRoute::new();
    let verdict = Verdict {
        pass: true,
        reason: "All approved".to_string(),
        approved_for_modalities: vec![Modality::Text, Modality::Vision, Modality::Audio],
    };

    let decisions = omni.route(&verdict);

    assert_eq!(decisions.len(), 3, "Should have 3 modality decisions");
    assert_eq!(
        decisions.get(&Modality::Text),
        Some(&RouteTarget::Shadow),
        "Text should route to Shadow"
    );
    assert_eq!(
        decisions.get(&Modality::Vision),
        Some(&RouteTarget::Shadow),
        "Vision should route to Shadow"
    );
    assert_eq!(
        decisions.get(&Modality::Audio),
        Some(&RouteTarget::Shadow),
        "Audio should route to Shadow"
    );
}

#[test]
fn test_no_modalities_approved_routes_all_to_baseline() {
    let omni = OmniRoute::new();
    let verdict = Verdict {
        pass: false,
        reason: "None approved".to_string(),
        approved_for_modalities: vec![],
    };

    let decisions = omni.route(&verdict);

    assert_eq!(decisions.len(), 3, "Should have 3 modality decisions");
    assert_eq!(
        decisions.get(&Modality::Text),
        Some(&RouteTarget::Baseline),
        "Text should route to Baseline"
    );
    assert_eq!(
        decisions.get(&Modality::Vision),
        Some(&RouteTarget::Baseline),
        "Vision should route to Baseline"
    );
    assert_eq!(
        decisions.get(&Modality::Audio),
        Some(&RouteTarget::Baseline),
        "Audio should route to Baseline"
    );
}

#[test]
fn test_partial_approval_mixes_targets() {
    let omni = OmniRoute::new();
    let verdict = Verdict {
        pass: true,
        reason: "Partial approval".to_string(),
        approved_for_modalities: vec![Modality::Text],
    };

    let decisions = omni.route(&verdict);

    assert_eq!(decisions.len(), 3, "Should have 3 modality decisions");
    assert_eq!(
        decisions.get(&Modality::Text),
        Some(&RouteTarget::Shadow),
        "Text should route to Shadow (approved)"
    );
    assert_eq!(
        decisions.get(&Modality::Vision),
        Some(&RouteTarget::Baseline),
        "Vision should route to Baseline (not approved)"
    );
    assert_eq!(
        decisions.get(&Modality::Audio),
        Some(&RouteTarget::Baseline),
        "Audio should route to Baseline (not approved)"
    );
}

#[test]
fn test_routing_decision_always_covers_all_three_modalities() {
    let omni = OmniRoute::new();

    // Test with empty approval
    let v1 = Verdict {
        pass: false,
        reason: "".to_string(),
        approved_for_modalities: vec![],
    };
    assert_eq!(
        omni.route(&v1).len(),
        3,
        "Empty approval should have 3 decisions"
    );

    // Test with partial approval
    let v2 = Verdict {
        pass: true,
        reason: "".to_string(),
        approved_for_modalities: vec![Modality::Vision],
    };
    assert_eq!(
        omni.route(&v2).len(),
        3,
        "Partial approval should have 3 decisions"
    );

    // Test with full approval
    let v3 = Verdict {
        pass: true,
        reason: "".to_string(),
        approved_for_modalities: vec![Modality::Text, Modality::Vision, Modality::Audio],
    };
    assert_eq!(
        omni.route(&v3).len(),
        3,
        "Full approval should have 3 decisions"
    );
}

#[test]
fn test_routing_is_deterministic() {
    let omni = OmniRoute::new();
    let verdict = Verdict {
        pass: true,
        reason: "Test".to_string(),
        approved_for_modalities: vec![Modality::Audio, Modality::Text],
    };

    let d1 = omni.route(&verdict);
    let d2 = omni.route(&verdict);

    assert_eq!(
        d1, d2,
        "Same verdict should produce identical routing decisions"
    );
}
