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
}
