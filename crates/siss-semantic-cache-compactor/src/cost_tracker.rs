//! Cost tracking: real-time token cost optimization

use crate::error::Result;
use crate::types::CostRecord;
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use uuid::Uuid;

/// Cost configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CostConfig {
    pub per_token_cost_usd: f64,
    pub cache_hit_reduction_pct: f64,
    pub compaction_overhead_tokens: f64,
}

impl Default for CostConfig {
    fn default() -> Self {
        Self {
            per_token_cost_usd: 0.001,
            cache_hit_reduction_pct: 0.3,
            compaction_overhead_tokens: 10.0,
        }
    }
}

/// Cost tracker: monitors and reduces transaction costs
pub struct CostTracker {
    config: CostConfig,
    records: Arc<RwLock<Vec<CostRecord>>>,
    total_savings: Arc<RwLock<f64>>,
}

impl CostTracker {
    /// Create new cost tracker
    pub fn new(config: CostConfig) -> Self {
        Self {
            config,
            records: Arc::new(RwLock::new(Vec::new())),
            total_savings: Arc::new(RwLock::new(0.0)),
        }
    }

    /// Record transaction cost before and after optimization
    pub fn record_transaction(
        &self,
        initial_tokens: f64,
        final_tokens: f64,
    ) -> Result<CostRecord> {
        let initial_cost = initial_tokens * self.config.per_token_cost_usd;
        let final_cost = final_tokens * self.config.per_token_cost_usd;
        let savings = (initial_cost - final_cost).max(0.0);

        let record = CostRecord {
            transaction_id: Uuid::new_v4(),
            initial_cost,
            final_cost,
            savings,
            timestamp: chrono::Utc::now(),
        };

        let mut records = self.records.write();
        records.push(record.clone());

        let mut total = self.total_savings.write();
        *total += savings;

        Ok(record)
    }

    /// Estimate cost reduction from cache hit
    pub fn estimate_cache_hit_savings(&self, tokens_without_cache: f64) -> f64 {
        tokens_without_cache
            * self.config.cache_hit_reduction_pct
            * self.config.per_token_cost_usd
    }

    /// Calculate compaction cost-benefit
    pub fn compaction_cost_benefit(&self, bytes_freed: usize) -> f64 {
        let overhead_cost = self.config.compaction_overhead_tokens * self.config.per_token_cost_usd;

        // Assume ~1 token per 4 bytes of cache
        let tokens_saved = (bytes_freed as f64) / 4.0;
        let savings = tokens_saved * self.config.per_token_cost_usd;

        savings - overhead_cost
    }

    /// Optimize token usage: return reduced token count
    pub fn optimize_tokens(&self, base_tokens: f64) -> f64 {
        // Apply cache reduction percentage
        let after_cache = base_tokens * (1.0 - self.config.cache_hit_reduction_pct);

        // Apply compaction overhead (one-time)
        (after_cache - self.config.compaction_overhead_tokens).max(1.0)
    }

    /// Get transaction history
    pub fn transaction_history(&self) -> Vec<CostRecord> {
        self.records.read().clone()
    }

    /// Get total savings
    pub fn total_savings(&self) -> f64 {
        *self.total_savings.read()
    }

    /// Get average transaction cost
    pub fn average_transaction_cost(&self) -> f64 {
        let records = self.records.read();
        if records.is_empty() {
            return 0.0;
        }

        let total: f64 = records.iter().map(|r| r.final_cost).sum();
        total / (records.len() as f64)
    }

    /// Get transaction count
    pub fn transaction_count(&self) -> usize {
        self.records.read().len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cost_tracker_creation() {
        let tracker = CostTracker::new(CostConfig::default());
        assert_eq!(tracker.transaction_count(), 0);
        assert_eq!(tracker.total_savings(), 0.0);
    }

    #[test]
    fn test_record_transaction() {
        let tracker = CostTracker::new(CostConfig::default());
        let result = tracker.record_transaction(1000.0, 700.0);
        assert!(result.is_ok());

        let record = result.unwrap();
        assert!(record.savings > 0.0);
        assert_eq!(tracker.transaction_count(), 1);
    }

    #[test]
    fn test_estimate_cache_hit_savings() {
        let tracker = CostTracker::new(CostConfig::default());
        let savings = tracker.estimate_cache_hit_savings(1000.0);
        assert!(savings > 0.0);
    }

    #[test]
    fn test_compaction_cost_benefit() {
        let tracker = CostTracker::new(CostConfig::default());
        let benefit = tracker.compaction_cost_benefit(40000);
        assert!(benefit.is_finite());
    }

    #[test]
    fn test_optimize_tokens() {
        let tracker = CostTracker::new(CostConfig::default());
        let optimized = tracker.optimize_tokens(1000.0);
        assert!(optimized < 1000.0);
        assert!(optimized > 0.0);
    }

    #[test]
    fn test_average_transaction_cost() {
        let tracker = CostTracker::new(CostConfig::default());
        tracker.record_transaction(100.0, 80.0).unwrap();
        tracker.record_transaction(200.0, 140.0).unwrap();

        let avg = tracker.average_transaction_cost();
        assert!(avg > 0.0);
    }

    #[test]
    fn test_total_savings_accumulation() {
        let tracker = CostTracker::new(CostConfig::default());
        tracker.record_transaction(100.0, 50.0).unwrap();
        tracker.record_transaction(100.0, 50.0).unwrap();

        let total = tracker.total_savings();
        assert!(total > 0.0);
    }
}
