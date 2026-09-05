use chrono::Utc;
use siss_context_cartography::epistemic_gate::{EpistemicGateHook, GateResult};
use siss_context_cartography::gamma_operator::GammaOperator;
use siss_context_cartography::llm_wiki_v2::{EpistemicStatus, SemanticFact};
use uuid::Uuid;

#[test]
fn test_gamma_flags_divergent_paths() {
    let gamma = GammaOperator::new(0.4);
    let primary_path = vec!["fact A", "fact B", "fact C"];
    let adversarial_path = vec!["opposite X", "opposite Y", "opposite Z"];

    let status = gamma.check(
        &primary_path.iter().map(|s| *s).collect::<Vec<_>>(),
        &adversarial_path.iter().map(|s| *s).collect::<Vec<_>>(),
        Utc::now(),
    );

    match status {
        EpistemicStatus::Uncertain {
            divergence_score, ..
        } => {
            assert!(
                divergence_score > 0.4,
                "Divergent paths should have divergence > 0.4"
            );
        }
        _ => panic!("Expected Uncertain status for highly divergent paths"),
    }
}

#[test]
fn test_gamma_passes_convergent_paths() {
    let gamma = GammaOperator::new(0.4);
    let primary_path = vec![
        "machine learning requires data",
        "deep learning needs datasets",
    ];
    let adversarial_path = vec![
        "machine learning requires data",
        "deep learning needs datasets",
    ];

    let status = gamma.check(
        &primary_path.iter().map(|s| *s).collect::<Vec<_>>(),
        &adversarial_path.iter().map(|s| *s).collect::<Vec<_>>(),
        Utc::now(),
    );

    match status {
        EpistemicStatus::Verified { divergence_score } => {
            assert!(
                divergence_score < 0.1,
                "Convergent identical paths should have very low divergence"
            );
        }
        _ => panic!("Expected Verified status for convergent paths"),
    }
}

#[test]
fn test_gate_hook_defers_uncertain_fact() {
    let now = Utc::now();
    let fact = SemanticFact {
        id: Uuid::new_v4(),
        fact: "the sky is blue".to_string(),
        confidence_score: 0.8,
        created_at: now,
        last_accessed_at: now,
        access_count: 1,
        superseded_by: None,
        is_stale: false,
        sources: vec!["observation".to_string()],
        epistemic_status: EpistemicStatus::Uncertain {
            divergence_score: 0.6,
            flagged_at: now,
        },
    };

    let result = EpistemicGateHook::check_gate(&fact);

    match result {
        GateResult::Defer { reason } => {
            assert!(!reason.is_empty(), "Deferral reason should not be empty");
        }
        _ => panic!("Expected Defer result for Uncertain status"),
    }
}

#[test]
fn test_human_approved_bypasses_gate() {
    let now = Utc::now();
    let fact = SemanticFact {
        id: Uuid::new_v4(),
        fact: "the earth is round".to_string(),
        confidence_score: 0.95,
        created_at: now,
        last_accessed_at: now,
        access_count: 100,
        superseded_by: None,
        is_stale: false,
        sources: vec!["scientific consensus".to_string()],
        epistemic_status: EpistemicStatus::HumanApproved {
            approved_by: "domain_expert".to_string(),
            at: now,
        },
    };

    let result = EpistemicGateHook::check_gate(&fact);

    match result {
        GateResult::Allow => {}
        _ => panic!("Expected Allow result for HumanApproved status"),
    }
}

#[test]
fn test_epistemic_status_persists_serialization() {
    let now = Utc::now();

    let unverified = EpistemicStatus::Unverified;
    let verified = EpistemicStatus::Verified {
        divergence_score: 0.35,
    };
    let uncertain = EpistemicStatus::Uncertain {
        divergence_score: 0.55,
        flagged_at: now,
    };
    let approved = EpistemicStatus::HumanApproved {
        approved_by: "alice".to_string(),
        at: now,
    };

    // Test serialization and deserialization
    let unverified_json = serde_json::to_string(&unverified).unwrap();
    let unverified_back: EpistemicStatus = serde_json::from_str(&unverified_json).unwrap();
    assert_eq!(unverified, unverified_back);

    let verified_json = serde_json::to_string(&verified).unwrap();
    let verified_back: EpistemicStatus = serde_json::from_str(&verified_json).unwrap();
    assert_eq!(verified, verified_back);

    let uncertain_json = serde_json::to_string(&uncertain).unwrap();
    let uncertain_back: EpistemicStatus = serde_json::from_str(&uncertain_json).unwrap();
    assert_eq!(uncertain, uncertain_back);

    let approved_json = serde_json::to_string(&approved).unwrap();
    let approved_back: EpistemicStatus = serde_json::from_str(&approved_json).unwrap();
    assert_eq!(approved, approved_back);
}
