use crate::llm_wiki_v2::{EpistemicStatus, SemanticFact};
use siss_ontology_proofs::{GraphTransformation, PiPlusPlusEngine, ProjectionResult};
use uuid::Uuid;

pub enum GateResult {
    Allow,
    Defer {
        reason: String,
        proof_hash: Option<String>,
    },
}

pub struct EpistemicGateHook;

impl EpistemicGateHook {
    /// Check gate with π++ formal verification integration.
    /// Generates cryptographic proofs for Uncertain facts.
    pub fn check_gate_with_proof(fact: &SemanticFact, engine: &PiPlusPlusEngine) -> GateResult {
        match &fact.epistemic_status {
            EpistemicStatus::Verified { .. } => GateResult::Allow,
            EpistemicStatus::HumanApproved { .. } => GateResult::Allow,
            EpistemicStatus::Uncertain {
                divergence_score, ..
            } => {
                // Generate cryptographic proof for uncertain fact
                let transformation = GraphTransformation {
                    source_entity: fact.id,
                    target_entity: fact.id,
                    edge_type: "uncertainfact".to_string(),
                    timestamp_utc: chrono::Utc::now().to_rfc3339(),
                    metadata: Default::default(),
                };

                let justification = ProjectionResult {
                    projection_id: Uuid::new_v4(),
                    confidence: 1.0 - divergence_score,
                    outcome: "defer".to_string(),
                    justification: format!(
                        "epistemic uncertainty at divergence={}",
                        divergence_score
                    ),
                };

                let attestation = format!(
                    "Fact '{}' flagged Uncertain (divergence={:.3}) pending human review",
                    fact.fact, divergence_score
                );

                match engine.generate_proof(transformation, justification, attestation) {
                    Ok(proof) => GateResult::Defer {
                        reason: format!(
                            "epistemic uncertainty at divergence={:.3}",
                            divergence_score
                        ),
                        proof_hash: Some(proof.cryptography.proof_hash),
                    },
                    Err(_) => {
                        // Fallback if proof generation fails
                        GateResult::Defer {
                            reason: format!(
                                "epistemic uncertainty at divergence={:.3}",
                                divergence_score
                            ),
                            proof_hash: None,
                        }
                    }
                }
            }
            EpistemicStatus::Unverified => GateResult::Defer {
                reason: "unverified fact, no proof available".to_string(),
                proof_hash: None,
            },
        }
    }

    /// Check gate without proof generation (backward compatible).
    pub fn check_gate(fact: &SemanticFact) -> GateResult {
        match &fact.epistemic_status {
            EpistemicStatus::Verified { .. } => GateResult::Allow,
            EpistemicStatus::HumanApproved { .. } => GateResult::Allow,
            EpistemicStatus::Uncertain {
                divergence_score, ..
            } => GateResult::Defer {
                reason: format!(
                    "Fact '{}' flagged Uncertain (divergence={:.3}) pending human review",
                    fact.fact, divergence_score
                ),
                proof_hash: None,
            },
            EpistemicStatus::Unverified => GateResult::Defer {
                reason: format!(
                    "Fact '{}' is Unverified, requires validation before use",
                    fact.fact
                ),
                proof_hash: None,
            },
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;
    use uuid::Uuid;

    fn make_fact(status: EpistemicStatus) -> SemanticFact {
        let now = Utc::now();
        SemanticFact {
            id: Uuid::new_v4(),
            fact: "test fact".to_string(),
            confidence_score: 0.8,
            created_at: now,
            last_accessed_at: now,
            access_count: 1,
            superseded_by: None,
            is_stale: false,
            sources: vec![],
            epistemic_status: status,
        }
    }

    #[test]
    fn test_verified_status_allows() {
        let fact = make_fact(EpistemicStatus::Verified {
            divergence_score: 0.3,
        });
        match EpistemicGateHook::check_gate(&fact) {
            GateResult::Allow => {}
            _ => panic!("Expected Allow"),
        }
    }

    #[test]
    fn test_unverified_status_defers() {
        let fact = make_fact(EpistemicStatus::Unverified);
        match EpistemicGateHook::check_gate(&fact) {
            GateResult::Defer { reason, proof_hash } => {
                assert!(reason.contains("Unverified"));
                assert!(proof_hash.is_none());
            }
            _ => panic!("Expected Defer"),
        }
    }

    #[test]
    fn test_uncertain_status_defers() {
        let now = Utc::now();
        let fact = make_fact(EpistemicStatus::Uncertain {
            divergence_score: 0.6,
            flagged_at: now,
        });
        match EpistemicGateHook::check_gate(&fact) {
            GateResult::Defer { reason, proof_hash } => {
                assert!(reason.contains("Uncertain"));
                assert!(proof_hash.is_none());
            }
            _ => panic!("Expected Defer"),
        }
    }

    #[test]
    fn test_human_approved_allows() {
        let fact = make_fact(EpistemicStatus::HumanApproved {
            approved_by: "alice".to_string(),
            at: Utc::now(),
        });
        match EpistemicGateHook::check_gate(&fact) {
            GateResult::Allow => {}
            _ => panic!("Expected Allow"),
        }
    }

    #[test]
    fn test_uncertain_fact_defers_with_proof_hash() {
        use siss_ontology_proofs::create_signing_key;
        let now = Utc::now();
        let fact = make_fact(EpistemicStatus::Uncertain {
            divergence_score: 0.6,
            flagged_at: now,
        });

        let signing_key = create_signing_key();
        let engine = siss_ontology_proofs::PiPlusPlusEngine::new(signing_key, Uuid::new_v4());

        match EpistemicGateHook::check_gate_with_proof(&fact, &engine) {
            GateResult::Defer { reason, proof_hash } => {
                assert!(reason.contains("divergence=0.6"));
                assert!(
                    proof_hash.is_some(),
                    "Expected proof_hash to be Some for Uncertain fact"
                );
                // Verify proof_hash is a valid SHA256 hex string (64 chars)
                let hash = proof_hash.unwrap();
                assert_eq!(hash.len(), 64, "proof_hash should be 64-char SHA256 hex");
            }
            _ => panic!("Expected Defer with proof_hash"),
        }
    }

    #[test]
    fn test_unverified_defers_without_hash() {
        use siss_ontology_proofs::create_signing_key;
        let fact = make_fact(EpistemicStatus::Unverified);

        let signing_key = create_signing_key();
        let engine = siss_ontology_proofs::PiPlusPlusEngine::new(signing_key, Uuid::new_v4());

        match EpistemicGateHook::check_gate_with_proof(&fact, &engine) {
            GateResult::Defer { reason, proof_hash } => {
                assert!(reason.contains("unverified"));
                assert!(
                    proof_hash.is_none(),
                    "Expected proof_hash to be None for Unverified fact"
                );
            }
            _ => panic!("Expected Defer without proof_hash"),
        }
    }

    #[test]
    fn test_verified_allows_unchanged() {
        use siss_ontology_proofs::create_signing_key;
        let fact = make_fact(EpistemicStatus::Verified {
            divergence_score: 0.3,
        });

        let signing_key = create_signing_key();
        let engine = siss_ontology_proofs::PiPlusPlusEngine::new(signing_key, Uuid::new_v4());

        match EpistemicGateHook::check_gate_with_proof(&fact, &engine) {
            GateResult::Allow => {}
            _ => panic!("Expected Allow for Verified fact (no proof generation)"),
        }
    }
}
