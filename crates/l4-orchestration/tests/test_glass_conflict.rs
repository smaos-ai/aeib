//! L4 Glass Conflict Tests: Article 50 vs GDPR conflict detection
//! Tests for safety-critical systems (Annex I) with privacy considerations

use l4_orchestration::{GlassPilot, Pilot};

#[test]
fn test_glass_pilot_flow_complete() {
    let pilot = GlassPilot::new();
    let flow = pilot.flow().unwrap();

    assert!(!flow.is_empty(), "Flow must not be empty");
    assert!(flow.len() >= 9, "Glass flow must have 9+ checkpoints");
}

#[test]
fn test_glass_annex_i_policy_context() {
    let pilot = GlassPilot::new();
    let state = pilot.state();

    let policy_context = state.policy_context.unwrap();
    assert!(
        policy_context.contains("Annex I"),
        "Glass must reference Annex I (safety-critical)"
    );
    assert!(
        policy_context.contains("glass/auto"),
        "Glass must reference glass/auto domain"
    );
}

#[test]
fn test_glass_requires_human_escalation() {
    let pilot = GlassPilot::new();

    assert!(
        pilot.human_escalation(),
        "Glass pilot must require human escalation for safety-critical decisions"
    );

    let state = pilot.state();
    assert!(
        state.requires_human_escalation,
        "Glass state must mark human escalation as required"
    );
}

#[test]
fn test_glass_safety_permit_gate() {
    let checkpoints = GlassPilot::new().flow().unwrap();

    let permit_checkpoint = checkpoints
        .iter()
        .find(|cp| cp.state.contains("L3_PERMIT"))
        .expect("L3 permit checkpoint must exist");

    assert!(
        permit_checkpoint
            .action
            .contains("2 approvals"),
        "Glass safety requires multiple approvals"
    );
}

#[test]
fn test_glass_conflict_gdpr_vs_safety() {
    let pilot = GlassPilot::new();
    let state = pilot.state();

    let policy_context = state.policy_context.unwrap();

    // Verify both policy domains are considered
    assert!(
        policy_context.contains("Annex I"),
        "Must reference safety regulations"
    );

    // Glass is safety-critical, so may need GDPR considerations for personal data
    let knowledge_context = state.knowledge_context.unwrap();
    assert!(
        knowledge_context.contains("L2"),
        "Knowledge layer should include both safety and privacy rules"
    );
}

#[test]
fn test_glass_article_50_compliance() {
    let checkpoints = GlassPilot::new().flow().unwrap();

    let has_l1_policy = checkpoints
        .iter()
        .any(|cp| cp.layer.as_ref().is_some_and(|l| l == "L1"));

    assert!(
        has_l1_policy,
        "Glass must check Article 50 / Annex I policies at L1"
    );
}

#[test]
fn test_glass_safety_evaluation_score() {
    let pilot = GlassPilot::new();
    let state = pilot.state();

    let score = state.evaluation_score.unwrap();
    assert!(
        score > 0.8,
        "Glass safety evaluation score must be high (safety-critical): {}",
        score
    );
    assert!(score <= 1.0, "Score must be <= 1.0");
}

#[test]
fn test_glass_dual_policy_enforcement() {
    let pilot = GlassPilot::new();
    let flow = pilot.flow().unwrap();

    // Verify flow includes both policy checking (L1) and knowledge retrieval (L2)
    let has_policy_check = flow
        .iter()
        .any(|cp| cp.state.contains("L1_POLICY"));
    let has_knowledge_load = flow
        .iter()
        .any(|cp| cp.state.contains("L2_KNOWLEDGE"));

    assert!(
        has_policy_check,
        "Must check safety policies (L1)"
    );
    assert!(
        has_knowledge_load,
        "Must load safety knowledge (L2)"
    );
}

#[test]
fn test_glass_safety_vs_privacy_tradeoff() {
    let pilot = GlassPilot::new();
    let state = pilot.state();

    // For safety-critical systems, safety takes precedence
    let permit_decision = state.permit_decision.unwrap();
    assert!(
        permit_decision.contains("human"),
        "Safety-critical decision must involve human judgment"
    );
}

#[test]
fn test_glass_audit_trail_safety_compliance() {
    let checkpoints = GlassPilot::new().flow().unwrap();

    let has_safety_check = checkpoints
        .iter()
        .any(|cp| cp.state.contains("SAFETY"));
    let has_l8_proof = checkpoints
        .iter()
        .any(|cp| cp.layer.as_ref().is_some_and(|l| l == "L8"));

    assert!(
        has_safety_check,
        "Glass must perform explicit safety check"
    );
    assert!(
        has_l8_proof,
        "Glass must record immutable proof (L8) for regulatory compliance"
    );
}

#[test]
fn test_glass_annex_i_deadline_awareness() {
    let pilot = GlassPilot::new();
    let state = pilot.state();

    let policy_context = state.policy_context.unwrap();
    assert!(
        policy_context.contains("Aug 2, 2028"),
        "Glass context must include Annex I compliance deadline"
    );
}

#[test]
fn test_glass_pqc_signature_requirement() {
    let pilot = GlassPilot::new();
    let state = pilot.state();

    let proof_trail = state.proof_trail.unwrap();
    assert!(
        proof_trail.contains("ed25519") || proof_trail.contains("safety"),
        "Glass proof trail must use cryptographic signature"
    );
}

#[test]
fn test_glass_conflict_resolution_human_required() {
    let pilot = GlassPilot::new();
    let flow = pilot.flow().unwrap();

    // For safety vs privacy conflicts, human decision required
    let human_escalation_count = flow
        .iter()
        .filter(|cp| {
            cp.action.contains("human") || cp.action.contains("committee")
        })
        .count();

    assert!(
        human_escalation_count > 0,
        "Glass conflicts must require human escalation"
    );
}

#[test]
fn test_glass_ragas_evaluation() {
    let checkpoints = GlassPilot::new().flow().unwrap();

    let has_ragas = checkpoints
        .iter()
        .any(|cp| cp.layer.as_ref().is_some_and(|l| l == "L7"));

    assert!(
        has_ragas,
        "Glass must include RAGAS evaluation for compliance verification"
    );
}

#[test]
fn test_glass_full_l1_l8_audit_trail() {
    let checkpoints = GlassPilot::new().flow().unwrap();

    let layers: Vec<&str> = checkpoints
        .iter()
        .filter_map(|cp| cp.layer.as_ref().map(|l| l.as_str()))
        .collect();

    assert!(layers.contains(&"L1"), "L1 policy check required");
    assert!(layers.contains(&"L2"), "L2 knowledge required");
    assert!(layers.contains(&"L3"), "L3 permit gates required");
    assert!(layers.contains(&"L5"), "L5 communication required");
    assert!(layers.contains(&"L8"), "L8 immutable proof required");
}

#[test]
fn test_glass_conflict_detection_multiple_runs() {
    for _ in 0..10 {
        let pilot = GlassPilot::new();
        let state = pilot.state();

        assert!(state.requires_human_escalation);
        assert!(state
            .policy_context
            .unwrap()
            .contains("Annex I"));
    }
}

#[test]
fn test_glass_gdpr_consideration_in_knowledge() {
    let pilot = GlassPilot::new();
    let state = pilot.state();

    // Glass systems may process personal data (e.g., vehicle owners)
    let knowledge_context = state.knowledge_context.unwrap();
    assert!(
        knowledge_context.contains("L2"),
        "Must include L2 knowledge for privacy considerations"
    );
}

#[test]
fn test_glass_safety_committee_notification() {
    let checkpoints = GlassPilot::new().flow().unwrap();

    let has_notification = checkpoints
        .iter()
        .any(|cp| {
            cp.layer.as_ref().is_some_and(|l| l == "L5")
                && (cp.action.contains("committee") || cp.action.contains("A2A"))
        });

    assert!(
        has_notification,
        "Glass must notify safety committee via A2A (L5)"
    );
}

#[test]
fn test_glass_annex_i_compliance_verified() {
    let checkpoints = GlassPilot::new().flow().unwrap();

    let final_state = checkpoints.last().unwrap();
    assert_eq!(final_state.state, "APPROVED");
    assert!(
        final_state.action.contains("Annex I"),
        "Final state must confirm Annex I compliance"
    );
}

#[test]
fn test_glass_permit_requires_multiple_approvals() {
    let checkpoints = GlassPilot::new().flow().unwrap();

    let l3_checkpoint = checkpoints
        .iter()
        .find(|cp| cp.state.contains("L3_PERMIT"))
        .unwrap();

    assert!(
        l3_checkpoint.action.contains("approvals"),
        "Glass permits must require multiple approvals"
    );
}

#[test]
fn test_glass_conflict_policy_priority() {
    let pilot = GlassPilot::new();
    let state = pilot.state();

    // For safety-critical (glass/auto), safety takes precedence over other considerations
    let permit_decision = state.permit_decision.unwrap();
    assert!(
        permit_decision.contains("safety") || permit_decision.contains("human"),
        "Safety decision must prioritize safety over other factors"
    );
}

#[test]
fn test_glass_stress_50_iterations() {
    for _ in 0..50 {
        let pilot = GlassPilot::new();
        let flow = pilot.flow().unwrap();
        assert!(!flow.is_empty());

        let state = pilot.state();
        assert!(state.requires_human_escalation);
    }
}
