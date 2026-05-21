/// Routing metrics and statistics tracking

use std::sync::{Arc, Mutex};
use std::collections::HashMap;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RoutingMetrics {
    /// Total routing requests processed
    pub total_requests: u64,
    /// Requests routed to each tier
    pub tier_distribution: HashMap<String, u64>,
    /// Average latency per tier (ms)
    pub avg_latency_by_tier: HashMap<String, f64>,
    /// Total cost incurred
    pub total_cost: f64,
    /// Fallback escalations triggered
    pub fallback_escalations: u64,
    /// Budget rejections
    pub budget_rejections: u64,
}

impl RoutingMetrics {
    pub fn new() -> Self {
        RoutingMetrics {
            total_requests: 0,
            tier_distribution: HashMap::new(),
            avg_latency_by_tier: HashMap::new(),
            total_cost: 0.0,
            fallback_escalations: 0,
            budget_rejections: 0,
        }
    }

    pub fn record_routing(&mut self, tier: &str, latency_ms: u32, cost: f64) {
        self.total_requests += 1;
        *self.tier_distribution.entry(tier.to_string()).or_insert(0) += 1;
        self.total_cost += cost;

        // Update average latency
        let count = self.tier_distribution[tier];
        let current_avg = self.avg_latency_by_tier.entry(tier.to_string()).or_insert(0.0);
        *current_avg = (*current_avg * (count - 1) as f64 + latency_ms as f64) / count as f64;
    }

    pub fn record_escalation(&mut self) {
        self.fallback_escalations += 1;
    }

    pub fn record_rejection(&mut self) {
        self.budget_rejections += 1;
    }

    pub fn tier1_percentage(&self) -> f64 {
        if self.total_requests == 0 {
            0.0
        } else {
            (*self.tier_distribution.get("Tier1RapidMLX").unwrap_or(&0) as f64)
                / (self.total_requests as f64)
                * 100.0
        }
    }

    pub fn tier2_percentage(&self) -> f64 {
        if self.total_requests == 0 {
            0.0
        } else {
            (*self.tier_distribution.get("Tier2Sonnet").unwrap_or(&0) as f64)
                / (self.total_requests as f64)
                * 100.0
        }
    }

    pub fn tier3_percentage(&self) -> f64 {
        if self.total_requests == 0 {
            0.0
        } else {
            (*self.tier_distribution.get("Tier3Opus").unwrap_or(&0) as f64)
                / (self.total_requests as f64)
                * 100.0
        }
    }
}

impl Default for RoutingMetrics {
    fn default() -> Self {
        Self::new()
    }
}

/// Thread-safe metrics collector
#[derive(Clone)]
pub struct MetricsCollector {
    metrics: Arc<Mutex<RoutingMetrics>>,
}

impl MetricsCollector {
    pub fn new() -> Self {
        MetricsCollector {
            metrics: Arc::new(Mutex::new(RoutingMetrics::new())),
        }
    }

    pub fn record_routing(&self, tier: &str, latency_ms: u32, cost: f64) {
        if let Ok(mut metrics) = self.metrics.lock() {
            metrics.record_routing(tier, latency_ms, cost);
        }
    }

    pub fn record_escalation(&self) {
        if let Ok(mut metrics) = self.metrics.lock() {
            metrics.record_escalation();
        }
    }

    pub fn record_rejection(&self) {
        if let Ok(mut metrics) = self.metrics.lock() {
            metrics.record_rejection();
        }
    }

    pub fn get_metrics(&self) -> RoutingMetrics {
        self.metrics.lock().unwrap_or_else(|e| e.into_inner()).clone()
    }
}

impl Default for MetricsCollector {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_metrics_recording() {
        let mut metrics = RoutingMetrics::new();
        metrics.record_routing("Tier1RapidMLX", 2, 0.0);
        metrics.record_routing("Tier2Sonnet", 5, 0.0001);

        assert_eq!(metrics.total_requests, 2);
        assert_eq!(metrics.tier_distribution["Tier1RapidMLX"], 1);
        assert_eq!(metrics.tier_distribution["Tier2Sonnet"], 1);
        assert!(metrics.total_cost > 0.0);
    }

    #[test]
    fn test_tier_percentage_distribution() {
        let mut metrics = RoutingMetrics::new();
        for _ in 0..8 {
            metrics.record_routing("Tier1RapidMLX", 2, 0.0);
        }
        for _ in 0..2 {
            metrics.record_routing("Tier2Sonnet", 5, 0.0001);
        }

        assert_eq!(metrics.tier1_percentage(), 80.0);
        assert_eq!(metrics.tier2_percentage(), 20.0);
        assert_eq!(metrics.tier3_percentage(), 0.0);
    }

    #[test]
    fn test_metrics_collector_thread_safe() {
        let collector = MetricsCollector::new();
        collector.record_routing("Tier1RapidMLX", 2, 0.0);
        collector.record_escalation();

        let metrics = collector.get_metrics();
        assert_eq!(metrics.total_requests, 1);
        assert_eq!(metrics.fallback_escalations, 1);
    }
}
