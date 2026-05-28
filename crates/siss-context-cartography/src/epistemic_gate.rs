use crate::llm_wiki_v2::{SemanticFact, EpistemicStatus};

pub enum GateResult {
    Allow,
    Defer { reason: String },
}

pub struct EpistemicGateHook;

impl EpistemicGateHook {
    pub fn check_gate(fact: &SemanticFact) -> GateResult {
        match &fact.epistemic_status {
            EpistemicStatus::Verified { .. } => GateResult::Allow,
            EpistemicStatus::HumanApproved { .. } => GateResult::Allow,
            EpistemicStatus::Uncertain { divergence_score, .. } => {
                GateResult::Defer {
                    reason: format!(
                        "Fact '{}' flagged Uncertain (divergence={:.3}) pending human review",
                        fact.fact, divergence_score
                    ),
                }
            }
            EpistemicStatus::Unverified => {
                GateResult::Defer {
                    reason: format!(
                        "Fact '{}' is Unverified, requires validation before use",
                        fact.fact
                    ),
                }
            }
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
            GateResult::Defer { reason } => {
                assert!(reason.contains("Unverified"));
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
            GateResult::Defer { reason } => {
                assert!(reason.contains("Uncertain"));
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
}
