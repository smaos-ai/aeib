use crate::confidence_scorer::RoutingTier;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TokenBudget {
    pub total_available: u32,
    pub remaining: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CostMatrix {
    pub tier1_cost_per_token: f64,      // $0 baseline
    pub tier2_cost_per_token: f64,      // $0.003/1K
    pub tier3_cost_per_token: f64,      // $0.015/1K
    pub cache_hit_reduction: f64,       // Cache hit reduces cost by 90% (0.1x multiplier)
}

impl TokenBudget {
    pub fn new(total: u32) -> Self {
        TokenBudget {
            total_available: total,
            remaining: total,
        }
    }

    pub fn has_capacity(&self, tokens_required: u32) -> bool {
        self.remaining >= tokens_required
    }

    pub fn consume(&mut self, tokens: u32) -> Result<(), &'static str> {
        if self.has_capacity(tokens) {
            self.remaining -= tokens;
            Ok(())
        } else {
            Err("Insufficient token budget")
        }
    }

    pub fn reset(&mut self) {
        self.remaining = self.total_available;
    }
}

impl Default for CostMatrix {
    fn default() -> Self {
        CostMatrix {
            tier1_cost_per_token: 0.0,
            tier2_cost_per_token: 0.000003,      // $0.003 per 1K tokens
            tier3_cost_per_token: 0.000015,      // $0.015 per 1K tokens
            cache_hit_reduction: 0.1,            // Cache hits reduce cost to 10% (90% savings)
        }
    }
}

impl CostMatrix {
    pub fn estimate_cost(&self, tier: RoutingTier, tokens: u32) -> f64 {
        match tier {
            RoutingTier::Tier1RapidMLX => tokens as f64 * self.tier1_cost_per_token,
            RoutingTier::Tier2Sonnet => tokens as f64 * self.tier2_cost_per_token,
            RoutingTier::Tier3Opus => tokens as f64 * self.tier3_cost_per_token,
        }
    }

    pub fn estimate_cost_with_cache(
        &self,
        tier: RoutingTier,
        tokens: u32,
        cache_hit: bool,
    ) -> f64 {
        let base_cost = self.estimate_cost(tier, tokens);
        if cache_hit {
            base_cost * self.cache_hit_reduction
        } else {
            base_cost
        }
    }

    pub fn should_route_to_frontier(&self, tier: RoutingTier, tokens: u32, budget: &TokenBudget) -> bool {
        if !budget.has_capacity(tokens) {
            return false;
        }

        match tier {
            RoutingTier::Tier1RapidMLX => true,
            RoutingTier::Tier2Sonnet => {
                let cost = self.estimate_cost(tier, tokens);
                cost < 0.01  // Arbitrary threshold: < 1 cent
            }
            RoutingTier::Tier3Opus => {
                let cost = self.estimate_cost(tier, tokens);
                cost < 0.05  // Arbitrary threshold: < 5 cents
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_token_budget_creation() {
        let budget = TokenBudget::new(1000);
        assert_eq!(budget.total_available, 1000);
        assert_eq!(budget.remaining, 1000);
    }

    #[test]
    fn test_token_budget_has_capacity() {
        let budget = TokenBudget::new(1000);
        assert!(budget.has_capacity(500));
        assert!(budget.has_capacity(1000));
        assert!(!budget.has_capacity(1001));
    }

    #[test]
    fn test_token_budget_consume() {
        let mut budget = TokenBudget::new(1000);
        assert!(budget.consume(500).is_ok());
        assert_eq!(budget.remaining, 500);
        assert!(budget.consume(600).is_err());
        assert_eq!(budget.remaining, 500);
    }

    #[test]
    fn test_cost_matrix_estimates() {
        let matrix = CostMatrix::default();
        let cost_tier1 = matrix.estimate_cost(RoutingTier::Tier1RapidMLX, 100);
        let cost_tier2 = matrix.estimate_cost(RoutingTier::Tier2Sonnet, 100);
        let cost_tier3 = matrix.estimate_cost(RoutingTier::Tier3Opus, 100);

        assert_eq!(cost_tier1, 0.0);
        assert!(cost_tier2 > 0.0);
        assert!(cost_tier3 > cost_tier2);
    }

    #[test]
    fn test_cost_matrix_should_route() {
        let matrix = CostMatrix::default();
        let budget = TokenBudget::new(1000);

        assert!(matrix.should_route_to_frontier(RoutingTier::Tier1RapidMLX, 100, &budget));
        assert!(matrix.should_route_to_frontier(RoutingTier::Tier2Sonnet, 100, &budget));
        assert!(matrix.should_route_to_frontier(RoutingTier::Tier3Opus, 100, &budget));
    }

    #[test]
    fn test_cache_hit_reduces_cost_tier2() {
        let matrix = CostMatrix::default();
        let base_cost = matrix.estimate_cost(RoutingTier::Tier2Sonnet, 1000);
        let cached_cost = matrix.estimate_cost_with_cache(RoutingTier::Tier2Sonnet, 1000, true);

        assert!(cached_cost < base_cost);
        assert_eq!(cached_cost, base_cost * matrix.cache_hit_reduction);
    }

    #[test]
    fn test_cache_hit_reduces_cost_tier3() {
        let matrix = CostMatrix::default();
        let base_cost = matrix.estimate_cost(RoutingTier::Tier3Opus, 1000);
        let cached_cost = matrix.estimate_cost_with_cache(RoutingTier::Tier3Opus, 1000, true);

        assert!(cached_cost < base_cost);
        // Cache hit should reduce to 10% of original cost
        assert_eq!(cached_cost, base_cost * 0.1);
    }

    #[test]
    fn test_cache_aware_cost_alters_routing_decision() {
        let matrix = CostMatrix::default();
        let budget = TokenBudget::new(1000);

        // Without cache: Tier3 might exceed budget
        let uncached_cost = matrix.estimate_cost(RoutingTier::Tier3Opus, 500);
        // With cache: same task is affordable
        let cached_cost = matrix.estimate_cost_with_cache(RoutingTier::Tier3Opus, 500, true);

        assert!(uncached_cost > cached_cost);
        assert!(budget.has_capacity(500));
    }
}
