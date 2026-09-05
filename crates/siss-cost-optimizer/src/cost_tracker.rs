//! Real-time cost tracking

use crate::error::Result;
use crate::types::{CostMetric, CostRecord};
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use uuid::Uuid;

/// Cost tracker configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CostTrackerConfig {
    pub enable_real_time: bool,
    pub sample_rate: f32,
}

impl Default for CostTrackerConfig {
    fn default() -> Self {
        Self {
            enable_real_time: true,
            sample_rate: 1.0,
        }
    }
}

/// Real-time cost tracker
pub struct CostTracker {
    #[allow(dead_code)]
    config: CostTrackerConfig,
    records: Arc<RwLock<Vec<CostRecord>>>,
    agent_totals: Arc<RwLock<HashMap<String, f64>>>,
}

impl CostTracker {
    /// Create new tracker
    pub fn new(config: CostTrackerConfig) -> Self {
        Self {
            config,
            records: Arc::new(RwLock::new(Vec::new())),
            agent_totals: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Record cost for transaction
    pub fn record_cost(
        &self,
        agent_id: String,
        transaction_id: String,
        cost_usd: f64,
        resource_type: String,
    ) -> Result<CostRecord> {
        let record = CostRecord {
            id: Uuid::new_v4(),
            agent_id: agent_id.clone(),
            transaction_id,
            cost_usd,
            timestamp: chrono::Utc::now(),
            resource_type,
        };

        let mut records = self.records.write();
        records.push(record.clone());

        let mut totals = self.agent_totals.write();
        *totals.entry(agent_id).or_insert(0.0) += cost_usd;

        Ok(record)
    }

    /// Get metrics for agent
    pub fn get_agent_metrics(&self, agent_id: &str) -> CostMetric {
        let records = self.records.read();
        let agent_records: Vec<_> = records
            .iter()
            .filter(|r| r.agent_id == agent_id)
            .collect();

        if agent_records.is_empty() {
            return CostMetric {
                min_cost: 0.0,
                max_cost: 0.0,
                avg_cost: 0.0,
                total_cost: 0.0,
                transaction_count: 0,
            };
        }

        let costs: Vec<f64> = agent_records.iter().map(|r| r.cost_usd).collect();
        let total: f64 = costs.iter().sum();
        let count = costs.len() as u64;

        CostMetric {
            min_cost: costs
                .iter()
                .copied()
                .fold(f64::INFINITY, f64::min),
            max_cost: costs.iter().copied().fold(0.0, f64::max),
            avg_cost: total / (count as f64),
            total_cost: total,
            transaction_count: count,
        }
    }

    /// Get total cost across all agents
    pub fn get_total_cost(&self) -> f64 {
        self.agent_totals.read().values().sum()
    }

    /// Get all records
    pub fn get_records(&self) -> Vec<CostRecord> {
        self.records.read().clone()
    }

    /// Clear records older than duration
    pub fn prune_old_records(&self, days: i64) {
        let cutoff = chrono::Utc::now() - chrono::Duration::days(days);
        let mut records = self.records.write();
        records.retain(|r| r.timestamp > cutoff);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tracker_creation() {
        let tracker = CostTracker::new(CostTrackerConfig::default());
        assert_eq!(tracker.get_total_cost(), 0.0);
    }

    #[test]
    fn test_record_cost() {
        let tracker = CostTracker::new(CostTrackerConfig::default());
        let result = tracker.record_cost(
            "agent1".to_string(),
            "txn1".to_string(),
            10.5,
            "compute".to_string(),
        );
        assert!(result.is_ok());
    }

    #[test]
    fn test_agent_metrics() {
        let tracker = CostTracker::new(CostTrackerConfig::default());
        tracker.record_cost("agent1".to_string(), "txn1".to_string(), 10.0, "compute".to_string())
            .unwrap();
        tracker.record_cost("agent1".to_string(), "txn2".to_string(), 20.0, "compute".to_string())
            .unwrap();

        let metrics = tracker.get_agent_metrics("agent1");
        assert_eq!(metrics.transaction_count, 2);
        assert_eq!(metrics.total_cost, 30.0);
        assert_eq!(metrics.min_cost, 10.0);
        assert_eq!(metrics.max_cost, 20.0);
    }

    #[test]
    fn test_total_cost() {
        let tracker = CostTracker::new(CostTrackerConfig::default());
        tracker.record_cost("agent1".to_string(), "txn1".to_string(), 15.0, "compute".to_string())
            .unwrap();
        tracker.record_cost("agent2".to_string(), "txn2".to_string(), 25.0, "compute".to_string())
            .unwrap();

        assert_eq!(tracker.get_total_cost(), 40.0);
    }

    #[test]
    fn test_get_records() {
        let tracker = CostTracker::new(CostTrackerConfig::default());
        tracker.record_cost("agent1".to_string(), "txn1".to_string(), 10.0, "compute".to_string())
            .unwrap();

        let records = tracker.get_records();
        assert_eq!(records.len(), 1);
    }
}
