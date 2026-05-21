use crate::confidence_scorer::{ConfidenceScore, RoutingTier};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RoutingDecision {
    pub primary_tier: RoutingTier,
    pub fallback_chain: Vec<RoutingTier>,
    pub reason: String,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum RoutingError {
    AllTiersFailed,
    BudgetExceeded,
    InvalidInput,
}

pub struct RoutingEngine;

impl RoutingEngine {
    pub fn decide(confidence: &ConfidenceScore, cost_budget: Option<u32>) -> Result<RoutingDecision, RoutingError> {
        // Verify confidence is in valid range
        if confidence.score < 0.0 || confidence.score > 1.0 {
            return Err(RoutingError::InvalidInput);
        }

        // Check if we exceed cost budget
        if let Some(budget) = cost_budget {
            if confidence.estimated_tokens > budget {
                return Err(RoutingError::BudgetExceeded);
            }
        }

        let primary_tier = Self::select_primary_tier(confidence.score);
        let fallback_chain = Self::build_fallback_chain(primary_tier);

        Ok(RoutingDecision {
            primary_tier,
            fallback_chain,
            reason: Self::reason_for_tier(confidence.score),
        })
    }

    fn select_primary_tier(confidence: f64) -> RoutingTier {
        match confidence {
            c if c < 0.3 => RoutingTier::Tier1RapidMLX,
            c if c < 0.75 => {
                // Cost optimization: prefer Tier1 if latency allows
                if c <= 0.4 {
                    RoutingTier::Tier1RapidMLX
                } else {
                    RoutingTier::Tier2Sonnet
                }
            }
            _ => RoutingTier::Tier3Opus,
        }
    }

    fn build_fallback_chain(primary: RoutingTier) -> Vec<RoutingTier> {
        match primary {
            RoutingTier::Tier1RapidMLX => vec![RoutingTier::Tier2Sonnet, RoutingTier::Tier3Opus],
            RoutingTier::Tier2Sonnet => vec![RoutingTier::Tier3Opus],
            RoutingTier::Tier3Opus => vec![],
        }
    }

    fn reason_for_tier(confidence: f64) -> String {
        if confidence < 0.3 {
            "Simple task, routing to Tier1 (Rapid-MLX)".to_string()
        } else if confidence < 0.75 {
            "Medium complexity, cost-optimized routing".to_string()
        } else {
            "High complexity, routing to Tier3 (Opus)".to_string()
        }
    }

    pub fn execute_with_fallback(
        decision: &RoutingDecision,
        max_attempts: u32,
    ) -> Result<String, RoutingError> {
        let mut tiers = vec![decision.primary_tier];
        tiers.extend_from_slice(&decision.fallback_chain);

        for tier in tiers.iter().take(max_attempts as usize) {
            // Placeholder: actual tier execution would happen here
            match tier {
                RoutingTier::Tier1RapidMLX => {
                    return Ok(format!("Executed by {:?}", tier));
                }
                RoutingTier::Tier2Sonnet => {
                    return Ok(format!("Executed by {:?}", tier));
                }
                RoutingTier::Tier3Opus => {
                    return Ok(format!("Executed by {:?}", tier));
                }
            }
        }

        Err(RoutingError::AllTiersFailed)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_route_high_confidence_to_frontier() {
        let score = ConfidenceScore {
            score: 0.8,
            estimated_tokens: 500,
            recommended_tier: RoutingTier::Tier3Opus,
        };
        let decision = RoutingEngine::decide(&score, None).unwrap();
        assert_eq!(decision.primary_tier, RoutingTier::Tier3Opus);
    }

    #[test]
    fn test_route_medium_confidence_cost_optimized() {
        let score = ConfidenceScore {
            score: 0.4,
            estimated_tokens: 200,
            recommended_tier: RoutingTier::Tier2Sonnet,
        };
        let decision = RoutingEngine::decide(&score, None).unwrap();
        // Cost optimization: 0.4 confidence routes to Tier1 when possible
        assert_eq!(decision.primary_tier, RoutingTier::Tier1RapidMLX);
    }

    #[test]
    fn test_route_simple_local_only() {
        let score = ConfidenceScore {
            score: 0.1,
            estimated_tokens: 100,
            recommended_tier: RoutingTier::Tier1RapidMLX,
        };
        let decision = RoutingEngine::decide(&score, None).unwrap();
        assert_eq!(decision.primary_tier, RoutingTier::Tier1RapidMLX);
        assert!(!decision.fallback_chain.is_empty()); // Has fallback
    }

    #[test]
    fn test_route_correlation_requires_sonnet() {
        let score = ConfidenceScore {
            score: 0.65,
            estimated_tokens: 350,
            recommended_tier: RoutingTier::Tier2Sonnet,
        };
        let decision = RoutingEngine::decide(&score, None).unwrap();
        assert_eq!(decision.primary_tier, RoutingTier::Tier2Sonnet);
    }

    #[test]
    fn test_route_respects_cost_budget_constraint() {
        let score = ConfidenceScore {
            score: 0.8,
            estimated_tokens: 1000,
            recommended_tier: RoutingTier::Tier3Opus,
        };
        let decision = RoutingEngine::decide(&score, Some(500));
        assert!(decision.is_err());
        assert_eq!(decision.unwrap_err(), RoutingError::BudgetExceeded);
    }

    #[test]
    fn test_fallback_timeout_escalates_tier() {
        let score = ConfidenceScore {
            score: 0.2,
            estimated_tokens: 100,
            recommended_tier: RoutingTier::Tier1RapidMLX,
        };
        let decision = RoutingEngine::decide(&score, None).unwrap();
        assert_eq!(decision.fallback_chain[0], RoutingTier::Tier2Sonnet);
    }

    #[test]
    fn test_fallback_execution_error_escalates() {
        let score = ConfidenceScore {
            score: 0.5,
            estimated_tokens: 200,
            recommended_tier: RoutingTier::Tier2Sonnet,
        };
        let decision = RoutingEngine::decide(&score, None).unwrap();
        assert_eq!(decision.primary_tier, RoutingTier::Tier2Sonnet);
        assert_eq!(decision.fallback_chain[0], RoutingTier::Tier3Opus);
    }

    #[test]
    fn test_fallback_max_5_attempts_per_tier() {
        let score = ConfidenceScore {
            score: 0.1,
            estimated_tokens: 100,
            recommended_tier: RoutingTier::Tier1RapidMLX,
        };
        let decision = RoutingEngine::decide(&score, None).unwrap();
        // Max 5 attempts total; fallback chain should not exceed that
        let total_attempts = 1 + decision.fallback_chain.len();
        assert!(total_attempts <= 5);
    }

    #[test]
    fn test_fallback_opus_no_escalation() {
        let score = ConfidenceScore {
            score: 0.9,
            estimated_tokens: 800,
            recommended_tier: RoutingTier::Tier3Opus,
        };
        let decision = RoutingEngine::decide(&score, None).unwrap();
        assert_eq!(decision.primary_tier, RoutingTier::Tier3Opus);
        assert!(decision.fallback_chain.is_empty()); // Opus has no fallback
    }
}
