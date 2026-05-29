#[cfg(test)]
mod integration_tests {
    use crate::confidence_scorer::{ConfidenceScore, RoutingTier, SimpleScorer};
    use crate::cost_budget::{CostMatrix, TokenBudget};
    use crate::routing_engine::{RoutingEngine, RoutingEngine};

    #[test]
    fn test_e2e_simple_task_routing() {
        // Given: simple polling task
        let task = "polling: fetch current status by id";
        let score = SimpleScorer::score_task(task);

        // When: routing decision made
        let decision = RoutingEngine::decide(&score, None).unwrap();

        // Then: routes to Tier1 with fallback
        assert_eq!(decision.primary_tier, RoutingTier::Tier1RapidMLX);
        assert!(!decision.fallback_chain.is_empty());
    }

    #[test]
    fn test_e2e_complex_task_escalation() {
        // Given: complex decision task
        let task = "decide optimal reconciliation strategy";
        let score = SimpleScorer::score_task(task);

        // When: routing decision made
        let decision = RoutingEngine::decide(&score, None).unwrap();

        // Then: routes to Tier3 with no fallback
        assert_eq!(decision.primary_tier, RoutingTier::Tier3Opus);
        assert!(decision.fallback_chain.is_empty());
    }

    #[test]
    fn test_e2e_budget_exhaustion() {
        // Given: limited budget
        let budget = TokenBudget::new(100);
        let score = ConfidenceScore {
            score: 0.8,
            estimated_tokens: 500,
            recommended_tier: RoutingTier::Tier3Opus,
        };

        // When: routing decision respects budget
        let result = RoutingEngine::decide(&score, Some(budget.remaining));

        // Then: rejected for budget
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), RoutingError::BudgetExceeded);
    }

    #[test]
    fn test_e2e_fallback_escalation_scenario() {
        // Given: medium confidence task with Tier2 primary
        let score = ConfidenceScore {
            score: 0.5,
            estimated_tokens: 200,
            recommended_tier: RoutingTier::Tier2Sonnet,
        };

        // When: decision made
        let decision = RoutingEngine::decide(&score, None).unwrap();

        // Then: has escalation path to Tier3
        assert_eq!(decision.primary_tier, RoutingTier::Tier2Sonnet);
        assert_eq!(decision.fallback_chain[0], RoutingTier::Tier3Opus);
    }

    #[test]
    fn test_e2e_cost_calculation_accuracy() {
        // Given: cost matrix
        let matrix = CostMatrix::default();

        // When: estimating costs for each tier
        let cost_tier1 = matrix.estimate_cost(RoutingTier::Tier1RapidMLX, 1000);
        let cost_tier2 = matrix.estimate_cost(RoutingTier::Tier2Sonnet, 1000);
        let cost_tier3 = matrix.estimate_cost(RoutingTier::Tier3Opus, 1000);

        // Then: tier costs follow expected hierarchy
        assert_eq!(cost_tier1, 0.0);
        assert!(cost_tier2 > 0.0 && cost_tier2 < cost_tier3);
        assert!(cost_tier3 > cost_tier2);
    }

    #[test]
    fn test_e2e_multi_task_routing_variety() {
        // Given: diverse task descriptions
        let tasks = vec![
            ("polling status", RoutingTier::Tier1RapidMLX),
            ("filter by severity level", RoutingTier::Tier1RapidMLX),
            ("correlate anomalies", RoutingTier::Tier2Sonnet),
            ("decide next action", RoutingTier::Tier3Opus),
        ];

        // When/Then: each routes correctly
        for (task, expected_tier) in tasks {
            let score = SimpleScorer::score_task(task);
            let decision = RoutingEngine::decide(&score, None).unwrap();
            assert_eq!(decision.primary_tier, expected_tier, "Task: {}", task);
        }
    }

    #[test]
    fn test_e2e_token_budget_consumption() {
        // Given: budget tracking
        let mut budget = TokenBudget::new(1000);

        // When: consuming tokens for three tasks
        assert!(budget.consume(300).is_ok());
        assert!(budget.consume(300).is_ok());
        assert!(budget.consume(300).is_ok());

        // Then: remaining reflects consumption
        assert_eq!(budget.remaining, 100);
        assert!(budget.consume(101).is_err());
    }

    #[test]
    fn test_e2e_confidence_consistency() {
        // Given: same task scored multiple times
        let task = "correlation analysis of drift patterns";

        // When: scoring multiple times
        let scores: Vec<_> = (0..5)
            .map(|_| SimpleScorer::score_task(task))
            .collect();

        // Then: all scores are identical
        let first_score = scores[0].score;
        for score in &scores[1..] {
            assert_eq!(score.score, first_score);
        }
    }

    #[test]
    fn test_e2e_invalid_confidence_rejected() {
        // Given: invalid confidence score
        let invalid_score = ConfidenceScore {
            score: 1.5,
            estimated_tokens: 100,
            recommended_tier: RoutingTier::Tier3Opus,
        };

        // When: routing decision attempted
        let result = RoutingEngine::decide(&invalid_score, None);

        // Then: rejected as invalid
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), RoutingError::InvalidInput);
    }

    #[test]
    fn test_e2e_zero_confidence_routes_to_tier1() {
        // Given: zero confidence (minimum valid)
        let score = ConfidenceScore {
            score: 0.0,
            estimated_tokens: 50,
            recommended_tier: RoutingTier::Tier1RapidMLX,
        };

        // When: routing decision made
        let decision = RoutingEngine::decide(&score, None).unwrap();

        // Then: routes to Tier1
        assert_eq!(decision.primary_tier, RoutingTier::Tier1RapidMLX);
    }

    #[test]
    fn test_e2e_boundary_confidence_0_3() {
        // Given: confidence exactly at 0.3 boundary
        let score = ConfidenceScore {
            score: 0.3,
            estimated_tokens: 150,
            recommended_tier: RoutingTier::Tier1RapidMLX,
        };

        // When: routing decision made
        let decision = RoutingEngine::decide(&score, None).unwrap();

        // Then: routes to Tier1 (< 0.75)
        assert_eq!(decision.primary_tier, RoutingTier::Tier1RapidMLX);
    }

    #[test]
    fn test_e2e_boundary_confidence_0_75() {
        // Given: confidence exactly at 0.75 boundary
        let score = ConfidenceScore {
            score: 0.75,
            estimated_tokens: 400,
            recommended_tier: RoutingTier::Tier3Opus,
        };

        // When: routing decision made
        let decision = RoutingEngine::decide(&score, None).unwrap();

        // Then: routes to Tier3 (>= 0.75)
        assert_eq!(decision.primary_tier, RoutingTier::Tier3Opus);
    }

    #[test]
    fn test_e2e_cost_optimization_at_boundary() {
        // Given: confidence 0.4 (cost optimization boundary)
        let score = ConfidenceScore {
            score: 0.4,
            estimated_tokens: 200,
            recommended_tier: RoutingTier::Tier2Sonnet,
        };

        // When: routing decision made
        let decision = RoutingEngine::decide(&score, None).unwrap();

        // Then: routes to Tier1 despite mid-range confidence
        assert_eq!(decision.primary_tier, RoutingTier::Tier1RapidMLX);
    }

    #[test]
    fn test_e2e_full_confidence_spectrum() {
        // Given: 10 confidence points across spectrum
        let confidences = vec![0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.75, 0.8, 0.95];

        // When/Then: all route successfully
        for conf in confidences {
            let score = ConfidenceScore {
                score: conf,
                estimated_tokens: 100,
                recommended_tier: RoutingTier::Tier1RapidMLX,
            };
            let result = RoutingEngine::decide(&score, None);
            assert!(result.is_ok(), "Failed at confidence {}", conf);
        }
    }
}
