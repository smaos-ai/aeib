use siss_trust_mesh::did_registry::{DidRegistry, DidDocument};
use siss_trust_mesh::proof_of_sapience::ProofOfSapience;
use siss_trust_mesh::trust_resolver::{TrustResolver, ContradictionCandidate, Resolution};
use chrono::Utc;
use uuid::Uuid;

#[test]
fn test_did_registration_and_verification() {
    let mut registry = DidRegistry::new();
    let tenant_id = Uuid::new_v4();
    let agent_id = Uuid::new_v4();
    let key = [1u8; 32];
    let domains = vec!["consensus".to_string(), "cryptography".to_string()];

    let did = registry.register(tenant_id, agent_id, key, domains.clone(), Utc::now());

    assert!(did.starts_with("did:smaos:"));
    let resolved = registry.resolve(&did);
    assert!(resolved.is_some());
    let doc = resolved.unwrap();
    assert_eq!(doc.verifying_key_bytes, key);
    assert_eq!(doc.specialty_domains, domains);
}

#[test]
fn test_trust_score_domain_expert_wins() {
    let expert_accuracy = 0.95;
    let novice_accuracy = 0.60;
    let base_authority = 0.8;
    let recency = 0.9;

    let expert_score = ProofOfSapience::compute_trust_score(base_authority, expert_accuracy, recency);
    let novice_score = ProofOfSapience::compute_trust_score(base_authority, novice_accuracy, recency);

    assert!(expert_score > novice_score, "Domain expert should have higher trust score");
}

#[test]
fn test_proof_of_sapience_resolves_contradiction() {
    let fact_a_id = Uuid::new_v4();
    let fact_b_id = Uuid::new_v4();
    let high_trust_did = "did:smaos:tenant:high_trust".to_string();
    let low_trust_did = "did:smaos:tenant:low_trust".to_string();

    let candidate = ContradictionCandidate {
        fact_a_id,
        fact_a_did: high_trust_did,
        fact_a_trust: 0.85,
        fact_b_id,
        fact_b_did: low_trust_did,
        fact_b_trust: 0.45,
    };

    let resolution = TrustResolver::resolve(&candidate);

    match resolution {
        Resolution::FactAWins { loser_id } => {
            assert_eq!(loser_id, fact_b_id, "Lower-trust fact should lose");
        }
        _ => panic!("Expected FactAWins"),
    }
}

#[test]
fn test_sybil_resistance_caps_score() {
    let max_uncapped_score = 1.5;  // Impossible in theory, but test the cap
    let capped = ProofOfSapience::cap_score(max_uncapped_score);

    assert!(capped <= 0.95, "Score should be capped at 0.95");
    assert!(capped >= 0.0, "Score should not be negative");

    let normal_score = 0.5;
    let normal_capped = ProofOfSapience::cap_score(normal_score);
    assert_eq!(normal_capped, normal_score, "Normal scores should not be modified");
}

#[test]
fn test_historical_accuracy_decay() {
    let initial_accuracy = 0.9;
    let half_life_days = 30.0;

    let after_0_days = ProofOfSapience::decay_accuracy(initial_accuracy, 0.0, half_life_days);
    let after_30_days = ProofOfSapience::decay_accuracy(initial_accuracy, 30.0, half_life_days);
    let after_60_days = ProofOfSapience::decay_accuracy(initial_accuracy, 60.0, half_life_days);

    assert_eq!(after_0_days, initial_accuracy, "No decay at day 0");
    assert!(after_30_days < initial_accuracy, "Decay at half-life");
    assert!(after_60_days < after_30_days, "More decay after 2 half-lives");
    assert!((after_30_days - initial_accuracy * 0.5).abs() < 0.01, "Ebbinghaus half-life at 30 days");
}
