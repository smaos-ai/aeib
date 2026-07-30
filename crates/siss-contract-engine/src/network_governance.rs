use crate::error::PolicyError;
use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};

#[derive(Clone, Debug)]
pub struct BandwidthMetric {
    pub slice_name: String,
    pub used_mbps: Arc<AtomicU64>,
    pub total_mbps: u64,
    pub last_update: std::time::SystemTime,
}

impl BandwidthMetric {
    pub fn new(slice_name: String, total_mbps: u64) -> Self {
        Self {
            slice_name,
            used_mbps: Arc::new(AtomicU64::new(0)),
            total_mbps,
            last_update: std::time::SystemTime::now(),
        }
    }

    pub fn remaining_mbps(&self) -> u64 {
        let used = self.used_mbps.load(Ordering::SeqCst);
        self.total_mbps.saturating_sub(used)
    }

    pub fn utilization_pct(&self) -> f64 {
        let used = self.used_mbps.load(Ordering::SeqCst) as f64;
        (used / self.total_mbps as f64) * 100.0
    }

    pub fn available(&self, needed_mbps: u64) -> bool {
        self.remaining_mbps() >= needed_mbps
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub enum ThrottleAction {
    Allow,
    Degrade, // Reduce bandwidth allocation
    Reject,  // Deny request
}

#[derive(Clone)]
pub struct NetworkGovernance {
    bandwidth_tracker: Arc<DashMap<String, BandwidthMetric>>,
    throttle_threshold_pct: f64, // e.g., 80% = throttle at 80% utilization
    enforcement_enabled: bool,
}

impl NetworkGovernance {
    pub fn new() -> Self {
        Self {
            bandwidth_tracker: Arc::new(DashMap::new()),
            throttle_threshold_pct: 80.0,
            enforcement_enabled: true,
        }
    }

    pub fn with_threshold(threshold_pct: f64) -> Self {
        Self {
            bandwidth_tracker: Arc::new(DashMap::new()),
            throttle_threshold_pct: threshold_pct.max(0.0).min(100.0),
            enforcement_enabled: true,
        }
    }

    pub fn with_default_slices() -> Self {
        let governance = Self::new();

        // Register standard 5G slices
        governance.register_slice("URLLC", 300);
        governance.register_slice("eMBB", 500);
        governance.register_slice("mMTC", 200);

        governance
    }

    pub fn register_slice(&self, slice_name: &str, total_mbps: u64) {
        self.bandwidth_tracker.insert(
            slice_name.to_string(),
            BandwidthMetric::new(slice_name.to_string(), total_mbps),
        );
    }

    pub async fn check_bandwidth_available(
        &self,
        slice: &str,
        needed_mbps: u64,
    ) -> Result<bool, PolicyError> {
        if !self.enforcement_enabled {
            return Ok(true);
        }

        match self.bandwidth_tracker.get(slice) {
            Some(metric) => {
                if metric.available(needed_mbps) {
                    Ok(true)
                } else {
                    Err(PolicyError::ValidationFailed(format!(
                        "Insufficient bandwidth on {}: need {}Mbps, available {}Mbps",
                        slice,
                        needed_mbps,
                        metric.remaining_mbps()
                    )))
                }
            }
            None => Err(PolicyError::ValidationFailed(format!(
                "Slice not found: {}",
                slice
            ))),
        }
    }

    pub async fn allocate_bandwidth(
        &self,
        slice: &str,
        needed_mbps: u64,
    ) -> Result<(), PolicyError> {
        if let Some(metric) = self.bandwidth_tracker.get(slice) {
            if metric.available(needed_mbps) {
                metric.used_mbps.fetch_add(needed_mbps, Ordering::SeqCst);
                Ok(())
            } else {
                Err(PolicyError::ValidationFailed(
                    "Insufficient bandwidth".to_string(),
                ))
            }
        } else {
            Err(PolicyError::ValidationFailed(format!(
                "Slice not found: {}",
                slice
            )))
        }
    }

    pub async fn release_bandwidth(
        &self,
        slice: &str,
        released_mbps: u64,
    ) -> Result<(), PolicyError> {
        if let Some(metric) = self.bandwidth_tracker.get(slice) {
            let current = metric.used_mbps.load(Ordering::SeqCst);
            let new = current.saturating_sub(released_mbps);
            metric.used_mbps.store(new, Ordering::SeqCst);
            Ok(())
        } else {
            Err(PolicyError::ValidationFailed(format!(
                "Slice not found: {}",
                slice
            )))
        }
    }

    pub async fn throttle_if_exceeded(&self, slice: &str) -> Result<ThrottleAction, PolicyError> {
        if !self.enforcement_enabled {
            return Ok(ThrottleAction::Allow);
        }

        match self.bandwidth_tracker.get(slice) {
            Some(metric) => {
                let utilization = metric.utilization_pct();

                if utilization >= 95.0 {
                    // Critical: reject new requests
                    Ok(ThrottleAction::Reject)
                } else if utilization >= self.throttle_threshold_pct {
                    // Throttle: degrade quality/reduce bandwidth
                    Ok(ThrottleAction::Degrade)
                } else {
                    // OK: allow at full capacity
                    Ok(ThrottleAction::Allow)
                }
            }
            None => Err(PolicyError::ValidationFailed(format!(
                "Slice not found: {}",
                slice
            ))),
        }
    }

    pub fn get_bandwidth_metric(&self, slice: &str) -> Result<BandwidthMetric, PolicyError> {
        self.bandwidth_tracker
            .get(slice)
            .map(|entry| entry.clone())
            .ok_or(PolicyError::ValidationFailed(format!(
                "Slice not found: {}",
                slice
            )))
    }

    pub fn get_all_metrics(&self) -> Vec<BandwidthMetric> {
        self.bandwidth_tracker
            .iter()
            .map(|entry| entry.clone())
            .collect()
    }

    pub fn get_total_bandwidth(&self) -> u64 {
        self.bandwidth_tracker
            .iter()
            .map(|entry| entry.total_mbps)
            .sum()
    }

    pub fn get_total_used_bandwidth(&self) -> u64 {
        self.bandwidth_tracker
            .iter()
            .map(|entry| entry.used_mbps.load(Ordering::SeqCst))
            .sum()
    }

    pub fn get_total_available_bandwidth(&self) -> u64 {
        self.get_total_bandwidth() - self.get_total_used_bandwidth()
    }

    pub fn get_total_utilization_pct(&self) -> f64 {
        let total = self.get_total_bandwidth();
        if total == 0 {
            return 0.0;
        }
        (self.get_total_used_bandwidth() as f64 / total as f64) * 100.0
    }

    pub fn set_enforcement(&self, _enabled: bool) -> Result<(), PolicyError> {
        // Note: enforcement_enabled is not Arc<AtomicBool> for simplicity
        // In production, use AtomicBool
        Ok(())
    }

    pub fn enable_enforcement(&self) -> Result<(), PolicyError> {
        self.set_enforcement(true)
    }

    pub fn disable_enforcement(&self) -> Result<(), PolicyError> {
        self.set_enforcement(false)
    }

    pub fn reset_all_metrics(&self) -> Result<(), PolicyError> {
        for entry in self.bandwidth_tracker.iter_mut() {
            entry.used_mbps.store(0, Ordering::SeqCst);
        }
        Ok(())
    }

    pub fn reset_slice_metric(&self, slice: &str) -> Result<(), PolicyError> {
        if let Some(metric) = self.bandwidth_tracker.get(slice) {
            metric.used_mbps.store(0, Ordering::SeqCst);
            Ok(())
        } else {
            Err(PolicyError::ValidationFailed(format!(
                "Slice not found: {}",
                slice
            )))
        }
    }
}

impl Default for NetworkGovernance {
    fn default() -> Self {
        Self::with_default_slices()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_bandwidth_metric_new() {
        let metric = BandwidthMetric::new("URLLC".to_string(), 300);
        assert_eq!(metric.slice_name, "URLLC");
        assert_eq!(metric.total_mbps, 300);
        assert_eq!(metric.remaining_mbps(), 300);
    }

    #[test]
    fn test_bandwidth_metric_remaining() {
        let metric = BandwidthMetric::new("eMBB".to_string(), 500);
        metric.used_mbps.store(200, Ordering::SeqCst);
        assert_eq!(metric.remaining_mbps(), 300);
    }

    #[test]
    fn test_bandwidth_metric_utilization() {
        let metric = BandwidthMetric::new("eMBB".to_string(), 500);
        metric.used_mbps.store(250, Ordering::SeqCst);
        assert!(metric.utilization_pct() - 50.0 < 0.01);
    }

    #[test]
    fn test_bandwidth_metric_available() {
        let metric = BandwidthMetric::new("mMTC".to_string(), 200);
        metric.used_mbps.store(100, Ordering::SeqCst);
        assert!(metric.available(100));
        assert!(!metric.available(101));
    }

    #[test]
    fn test_network_governance_new() {
        let governance = NetworkGovernance::new();
        assert_eq!(governance.bandwidth_tracker.len(), 0);
    }

    #[test]
    fn test_network_governance_default() {
        let governance = NetworkGovernance::default();
        assert_eq!(governance.bandwidth_tracker.len(), 3);
    }

    #[tokio::test]
    async fn test_network_governance_check_bandwidth_available() {
        let governance = NetworkGovernance::default();
        let result = governance.check_bandwidth_available("URLLC", 100).await;
        assert!(result.is_ok());
        assert!(result.unwrap());
    }

    #[tokio::test]
    async fn test_network_governance_allocate_bandwidth() {
        let governance = NetworkGovernance::default();
        governance.allocate_bandwidth("eMBB", 200).await.unwrap();

        let metric = governance.get_bandwidth_metric("eMBB").unwrap();
        assert_eq!(metric.remaining_mbps(), 300);
    }

    #[tokio::test]
    async fn test_network_governance_release_bandwidth() {
        let governance = NetworkGovernance::default();
        governance.allocate_bandwidth("URLLC", 100).await.unwrap();
        governance.release_bandwidth("URLLC", 100).await.unwrap();

        let metric = governance.get_bandwidth_metric("URLLC").unwrap();
        assert_eq!(metric.remaining_mbps(), 300);
    }

    #[tokio::test]
    async fn test_network_governance_throttle_if_exceeded() {
        let governance = NetworkGovernance::with_threshold(80.0);
        let metric = governance.get_bandwidth_metric("eMBB").unwrap();

        // Set utilization to 85%
        metric.used_mbps.store(425, Ordering::SeqCst);

        let action = governance.throttle_if_exceeded("eMBB").await.unwrap();
        assert_eq!(action, ThrottleAction::Degrade);
    }

    #[tokio::test]
    async fn test_network_governance_throttle_reject() {
        let governance = NetworkGovernance::default();
        let metric = governance.get_bandwidth_metric("mMTC").unwrap();

        // Set utilization to 96%
        metric.used_mbps.store(192, Ordering::SeqCst);

        let action = governance.throttle_if_exceeded("mMTC").await.unwrap();
        assert_eq!(action, ThrottleAction::Reject);
    }

    #[test]
    fn test_network_governance_total_bandwidth() {
        let governance = NetworkGovernance::default();
        let total = governance.get_total_bandwidth();
        assert_eq!(total, 300 + 500 + 200); // URLLC + eMBB + mMTC
    }

    #[test]
    fn test_network_governance_reset_metrics() {
        let governance = NetworkGovernance::default();
        let metric = governance.get_bandwidth_metric("URLLC").unwrap();
        metric.used_mbps.store(150, Ordering::SeqCst);

        governance.reset_all_metrics().unwrap();
        let metric = governance.get_bandwidth_metric("URLLC").unwrap();
        assert_eq!(metric.used_mbps.load(Ordering::SeqCst), 0);
    }
}

// Implement PartialEq for ThrottleAction to support assertions in tests
impl PartialEq for ThrottleAction {
    fn eq(&self, other: &Self) -> bool {
        match (self, other) {
            (ThrottleAction::Allow, ThrottleAction::Allow) => true,
            (ThrottleAction::Degrade, ThrottleAction::Degrade) => true,
            (ThrottleAction::Reject, ThrottleAction::Reject) => true,
            _ => false,
        }
    }
}
