use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

/// MiFID II Best Execution Rule definition
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum BestExecutionRule {
    /// Order routing rule: lowest price with equivalent speed
    LowestPrice,
    /// Execution speed rule: fastest settlement with acceptable cost
    FastestSpeed,
    /// Liquidity rule: highest execution probability
    HighestLiquidity,
    /// Composite rule: weighted combination of price, speed, liquidity
    Composite,
}

impl BestExecutionRule {
    /// Check if rule is applicable to client type
    pub fn applicable_to_retail(&self) -> bool {
        matches!(
            self,
            BestExecutionRule::LowestPrice | BestExecutionRule::Composite
        )
    }

    /// Check if rule is applicable to professional/institutional
    pub fn applicable_to_professional(&self) -> bool {
        true
    }
}

/// Execution quality metrics
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct ExecutionQuality {
    pub price_improvement_bps: i32,      // basis points
    pub execution_speed_ms: u32,         // milliseconds
    pub fill_probability: f64,           // 0.0-1.0
    pub cost_to_client_eur: f64,         // in euros
    pub total_cost_basis_eur: f64,       // for cost comparison
}

impl ExecutionQuality {
    pub fn new(
        price_improvement_bps: i32,
        execution_speed_ms: u32,
        fill_probability: f64,
        cost_to_client_eur: f64,
    ) -> Self {
        let total_cost = cost_to_client_eur; // simplified; in reality more complex
        Self {
            price_improvement_bps,
            execution_speed_ms,
            fill_probability,
            cost_to_client_eur,
            total_cost_basis_eur: total_cost,
        }
    }

    /// Composite score (0.0-100.0): higher is better
    pub fn composite_score(&self) -> f64 {
        let price_score = (self.price_improvement_bps.max(0) as f64 / 100.0).min(40.0);
        let speed_score = (100.0 - (self.execution_speed_ms as f64 / 100.0)).max(0.0).min(30.0);
        let fill_score = self.fill_probability * 30.0;
        price_score + speed_score + fill_score
    }
}

/// Execution analysis result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionAnalysis {
    pub order_id: Uuid,
    pub rule_applied: BestExecutionRule,
    pub chosen_venue_id: Uuid,
    pub alternatives: Vec<(Uuid, ExecutionQuality)>, // venue_id, quality
    pub quality_delivered: ExecutionQuality,
    pub analysis_timestamp: DateTime<Utc>,
}

impl ExecutionAnalysis {
    pub fn new(
        order_id: Uuid,
        rule_applied: BestExecutionRule,
        chosen_venue_id: Uuid,
        quality_delivered: ExecutionQuality,
    ) -> Self {
        Self {
            order_id,
            rule_applied,
            chosen_venue_id,
            alternatives: Vec::new(),
            quality_delivered,
            analysis_timestamp: Utc::now(),
        }
    }

    /// Add alternative venue for comparison
    pub fn add_alternative(&mut self, venue_id: Uuid, quality: ExecutionQuality) {
        self.alternatives.push((venue_id, quality));
    }

    /// Verify that chosen venue meets best execution criteria
    pub fn verify_best_execution(&self) -> bool {
        match &self.rule_applied {
            BestExecutionRule::LowestPrice => {
                // Check that chosen venue has lowest total cost
                self.alternatives
                    .iter()
                    .all(|(_, q)| q.total_cost_basis_eur >= self.quality_delivered.total_cost_basis_eur)
            }
            BestExecutionRule::FastestSpeed => {
                // Check that chosen venue has fastest execution
                self.alternatives
                    .iter()
                    .all(|(_, q)| q.execution_speed_ms >= self.quality_delivered.execution_speed_ms)
            }
            BestExecutionRule::HighestLiquidity => {
                // Check that chosen venue has highest fill probability
                self.alternatives
                    .iter()
                    .all(|(_, q)| q.fill_probability <= self.quality_delivered.fill_probability)
            }
            BestExecutionRule::Composite => {
                // Check composite score
                let chosen_score = self.quality_delivered.composite_score();
                self.alternatives
                    .iter()
                    .all(|(_, q)| q.composite_score() <= chosen_score)
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_best_execution_rule_retail_applicability() {
        assert!(BestExecutionRule::LowestPrice.applicable_to_retail());
        assert!(BestExecutionRule::Composite.applicable_to_retail());
        assert!(!BestExecutionRule::FastestSpeed.applicable_to_retail());
    }

    #[test]
    fn test_execution_quality_composite_score() {
        let quality = ExecutionQuality::new(100, 50, 0.95, 10.0);
        let score = quality.composite_score();
        assert!(score > 0.0 && score < 100.0);
    }

    #[test]
    fn test_execution_analysis_lowest_price_verification() {
        let order_id = Uuid::new_v4();
        let venue1 = Uuid::new_v4();
        let venue2 = Uuid::new_v4();

        let chosen_quality = ExecutionQuality::new(50, 100, 0.9, 5.0);
        let mut analysis = ExecutionAnalysis::new(
            order_id,
            BestExecutionRule::LowestPrice,
            venue1,
            chosen_quality,
        );

        // Add worse venue
        analysis.add_alternative(venue2, ExecutionQuality::new(30, 100, 0.9, 8.0));
        assert!(analysis.verify_best_execution());

        // Add better venue (should fail)
        analysis.add_alternative(Uuid::new_v4(), ExecutionQuality::new(60, 100, 0.9, 3.0));
        assert!(!analysis.verify_best_execution());
    }

    #[test]
    fn test_execution_analysis_fastest_speed() {
        let order_id = Uuid::new_v4();
        let venue1 = Uuid::new_v4();

        let chosen_quality = ExecutionQuality::new(50, 50, 0.9, 5.0);
        let mut analysis = ExecutionAnalysis::new(
            order_id,
            BestExecutionRule::FastestSpeed,
            venue1,
            chosen_quality,
        );

        // Add slower venue
        analysis.add_alternative(Uuid::new_v4(), ExecutionQuality::new(50, 150, 0.9, 5.0));
        assert!(analysis.verify_best_execution());
    }

    #[test]
    fn test_execution_analysis_highest_liquidity() {
        let order_id = Uuid::new_v4();
        let venue1 = Uuid::new_v4();

        let chosen_quality = ExecutionQuality::new(50, 100, 0.95, 5.0);
        let mut analysis = ExecutionAnalysis::new(
            order_id,
            BestExecutionRule::HighestLiquidity,
            venue1,
            chosen_quality,
        );

        // Add lower liquidity venue
        analysis.add_alternative(Uuid::new_v4(), ExecutionQuality::new(50, 100, 0.75, 5.0));
        assert!(analysis.verify_best_execution());
    }

    #[test]
    fn test_execution_analysis_composite_rule() {
        let order_id = Uuid::new_v4();
        let venue1 = Uuid::new_v4();

        let chosen_quality = ExecutionQuality::new(100, 50, 0.95, 5.0);
        let mut analysis = ExecutionAnalysis::new(
            order_id,
            BestExecutionRule::Composite,
            venue1,
            chosen_quality,
        );

        // Add alternative with lower composite score
        analysis.add_alternative(Uuid::new_v4(), ExecutionQuality::new(50, 150, 0.70, 8.0));
        assert!(analysis.verify_best_execution());
    }
}
