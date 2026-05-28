use uuid::Uuid;

pub struct ContradictionCandidate {
    pub fact_a_id: Uuid,
    pub fact_a_did: String,
    pub fact_a_trust: f64,
    pub fact_b_id: Uuid,
    pub fact_b_did: String,
    pub fact_b_trust: f64,
}

pub enum Resolution {
    FactAWins { loser_id: Uuid },
    FactBWins { loser_id: Uuid },
}

pub struct TrustResolver;

impl TrustResolver {
    /// Resolves contradiction: higher trust score wins
    /// In case of tie, fact_a wins (deterministic)
    pub fn resolve(candidate: &ContradictionCandidate) -> Resolution {
        if candidate.fact_a_trust > candidate.fact_b_trust {
            Resolution::FactAWins {
                loser_id: candidate.fact_b_id,
            }
        } else if candidate.fact_b_trust > candidate.fact_a_trust {
            Resolution::FactBWins {
                loser_id: candidate.fact_a_id,
            }
        } else {
            // Deterministic tie-breaking: fact_a wins
            Resolution::FactAWins {
                loser_id: candidate.fact_b_id,
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_higher_trust_wins() {
        let candidate = ContradictionCandidate {
            fact_a_id: Uuid::new_v4(),
            fact_a_did: "did:smaos:tenant:a".to_string(),
            fact_a_trust: 0.9,
            fact_b_id: Uuid::new_v4(),
            fact_b_did: "did:smaos:tenant:b".to_string(),
            fact_b_trust: 0.5,
        };

        match TrustResolver::resolve(&candidate) {
            Resolution::FactAWins { loser_id } => {
                assert_eq!(loser_id, candidate.fact_b_id);
            }
            _ => panic!("Expected FactAWins"),
        }
    }

    #[test]
    fn test_tie_favors_fact_a() {
        let fact_b_id = Uuid::new_v4();
        let candidate = ContradictionCandidate {
            fact_a_id: Uuid::new_v4(),
            fact_a_did: "did:smaos:tenant:a".to_string(),
            fact_a_trust: 0.75,
            fact_b_id,
            fact_b_did: "did:smaos:tenant:b".to_string(),
            fact_b_trust: 0.75,
        };

        match TrustResolver::resolve(&candidate) {
            Resolution::FactAWins { loser_id } => {
                assert_eq!(loser_id, fact_b_id);
            }
            _ => panic!("Expected FactAWins on tie"),
        }
    }
}
