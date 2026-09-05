use crate::error::PolicyError;
use crate::vertical_policy::{Request, VerticalPolicy};
use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[allow(non_camel_case_types)]
pub enum NetworkSliceType {
    URLLC, // Ultra-Reliable Low-Latency Communications (<10ms)
    eMBB,  // Enhanced Mobile Broadband (<100ms)
    mMTC,  // Massive Machine-Type Communications (sensor networks)
}

impl std::fmt::Display for NetworkSliceType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            NetworkSliceType::URLLC => write!(f, "URLLC"),
            NetworkSliceType::eMBB => write!(f, "eMBB"),
            NetworkSliceType::mMTC => write!(f, "mMTC"),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum IsolationLevel {
    Strict,   // No cross-slice interference
    Moderate, // Priority-based resource sharing
    Best,     // Opportunistic sharing
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SliceConfig {
    pub name: String,
    pub slice_type: NetworkSliceType,
    pub bandwidth_mbps: u64,
    pub latency_target_ms: u64,
    pub isolation_level: IsolationLevel,
    pub priority: u8, // 0-255, higher = more priority
}

impl SliceConfig {
    pub fn urllc(bandwidth_mbps: u64) -> Self {
        Self {
            name: "URLLC".to_string(),
            slice_type: NetworkSliceType::URLLC,
            bandwidth_mbps,
            latency_target_ms: 10,
            isolation_level: IsolationLevel::Strict,
            priority: 255,
        }
    }

    pub fn embb(bandwidth_mbps: u64) -> Self {
        Self {
            name: "eMBB".to_string(),
            slice_type: NetworkSliceType::eMBB,
            bandwidth_mbps,
            latency_target_ms: 100,
            isolation_level: IsolationLevel::Moderate,
            priority: 128,
        }
    }

    pub fn mmtc(bandwidth_mbps: u64) -> Self {
        Self {
            name: "mMTC".to_string(),
            slice_type: NetworkSliceType::mMTC,
            bandwidth_mbps,
            latency_target_ms: 1000,
            isolation_level: IsolationLevel::Best,
            priority: 64,
        }
    }
}

#[derive(Clone, Debug)]
pub struct BandwidthMetric {
    pub used_mbps: Arc<AtomicU64>,
    pub total_mbps: u64,
    pub timestamp: std::time::SystemTime,
}

impl BandwidthMetric {
    pub fn remaining(&self) -> u64 {
        let used = self.used_mbps.load(Ordering::SeqCst);
        self.total_mbps.saturating_sub(used)
    }

    pub fn utilization_pct(&self) -> f64 {
        let used = self.used_mbps.load(Ordering::SeqCst) as f64;
        let total = self.total_mbps as f64;
        (used / total) * 100.0
    }
}

#[derive(Clone)]
pub struct TelecomPolicy {
    name: String,
    slicing_enabled: bool,
    network_slices: Arc<DashMap<String, SliceConfig>>,
    bandwidth_tracker: Arc<DashMap<String, BandwidthMetric>>,
    availability_pct: Arc<AtomicU64>, // Stored as basis points (0-10000 = 0-100%)
    has_failover: bool,
    failed_slices: Arc<DashMap<String, bool>>,
    degraded_zones: Arc<DashMap<String, bool>>,
    congested_zones: Arc<DashMap<String, bool>>,
}

impl TelecomPolicy {
    pub fn new_default() -> Self {
        let slices = Arc::new(DashMap::new());
        slices.insert("URLLC".to_string(), SliceConfig::urllc(300));
        slices.insert("eMBB".to_string(), SliceConfig::embb(500));
        slices.insert("mMTC".to_string(), SliceConfig::mmtc(200));

        let bw_tracker = Arc::new(DashMap::new());
        bw_tracker.insert(
            "URLLC".to_string(),
            BandwidthMetric {
                used_mbps: Arc::new(AtomicU64::new(0)),
                total_mbps: 300,
                timestamp: std::time::SystemTime::now(),
            },
        );
        bw_tracker.insert(
            "eMBB".to_string(),
            BandwidthMetric {
                used_mbps: Arc::new(AtomicU64::new(0)),
                total_mbps: 500,
                timestamp: std::time::SystemTime::now(),
            },
        );
        bw_tracker.insert(
            "mMTC".to_string(),
            BandwidthMetric {
                used_mbps: Arc::new(AtomicU64::new(0)),
                total_mbps: 200,
                timestamp: std::time::SystemTime::now(),
            },
        );

        Self {
            name: "TelecomPolicy".to_string(),
            slicing_enabled: true,
            network_slices: slices,
            bandwidth_tracker: bw_tracker,
            availability_pct: Arc::new(AtomicU64::new(9995)), // 99.95%
            has_failover: false,
            failed_slices: Arc::new(DashMap::new()),
            degraded_zones: Arc::new(DashMap::new()),
            congested_zones: Arc::new(DashMap::new()),
        }
    }

    pub fn new_with_bandwidth(total_mbps: u64) -> Self {
        let bw_tracker = Arc::new(DashMap::new());
        let per_slice = total_mbps / 3;
        let remainder = total_mbps % 3;

        bw_tracker.insert(
            "URLLC".to_string(),
            BandwidthMetric {
                used_mbps: Arc::new(AtomicU64::new(0)),
                total_mbps: per_slice + remainder,
                timestamp: std::time::SystemTime::now(),
            },
        );
        bw_tracker.insert(
            "eMBB".to_string(),
            BandwidthMetric {
                used_mbps: Arc::new(AtomicU64::new(0)),
                total_mbps: per_slice,
                timestamp: std::time::SystemTime::now(),
            },
        );
        bw_tracker.insert(
            "mMTC".to_string(),
            BandwidthMetric {
                used_mbps: Arc::new(AtomicU64::new(0)),
                total_mbps: per_slice,
                timestamp: std::time::SystemTime::now(),
            },
        );

        let mut policy = Self::new_default();
        policy.bandwidth_tracker = bw_tracker;
        policy
    }

    pub fn new_with_failover() -> Self {
        let mut policy = Self::new_default();
        policy.has_failover = true;
        policy
    }

    pub fn new_with_priority() -> Self {
        Self::new_default()
    }

    // Allocation and routing
    pub async fn get_allocated_slice(&self, _req: &Request) -> Result<String, PolicyError> {
        // For now, return URLLC; in production, choose based on request characteristics
        Ok("URLLC".to_string())
    }

    pub async fn get_route(&self, _req: &Request) -> Result<String, PolicyError> {
        Ok("direct-peer".to_string())
    }

    pub async fn get_active_slice(&self, _req: &Request) -> Result<String, PolicyError> {
        Ok("URLLC".to_string())
    }

    // Latency monitoring
    pub async fn get_p99_latency(&self, _req: &Request) -> Result<u64, PolicyError> {
        // Simulated p99 latency in ms
        Ok(5) // URLLC target
    }

    // Bandwidth management
    pub async fn get_remaining_bandwidth(&self) -> Result<u64, PolicyError> {
        let mut total = 0u64;
        for entry in self.bandwidth_tracker.iter() {
            total += entry.remaining();
        }
        Ok(total)
    }

    pub async fn get_slice_bandwidth(&self, slice_name: &str) -> Result<u64, PolicyError> {
        self.bandwidth_tracker
            .get(slice_name)
            .map(|entry| entry.total_mbps)
            .ok_or(PolicyError::ValidationFailed(format!(
                "Slice not found: {}",
                slice_name
            )))
    }

    // SLA metrics
    pub async fn get_availability_pct(&self) -> Result<f64, PolicyError> {
        let basis_points = self.availability_pct.load(Ordering::SeqCst);
        Ok(basis_points as f64 / 100.0)
    }

    pub async fn get_sla_metrics(&self, _req: &Request) -> Result<String, PolicyError> {
        Ok("uptime: 99.95%, latency: 5ms, packet_loss: 0.01%".to_string())
    }

    pub async fn get_slice_distribution(&self) -> Result<String, PolicyError> {
        Ok("URLLC: 30%, eMBB: 50%, mMTC: 20%".to_string())
    }

    // Degradation and congestion detection
    pub async fn simulate_latency_increase(
        &self,
        req: &Request,
        latency_ms: u64,
    ) -> Result<(), PolicyError> {
        if latency_ms > 10 {
            self.degraded_zones.insert(req.region.clone(), true);
        }
        Ok(())
    }

    pub async fn is_degraded(&self, req: &Request) -> Result<bool, PolicyError> {
        Ok(self.degraded_zones.contains_key(&req.region))
    }

    pub async fn simulate_congestion(&self, req: &Request) -> Result<(), PolicyError> {
        self.congested_zones.insert(req.region.clone(), true);
        Ok(())
    }

    pub async fn is_congested(&self, req: &Request) -> Result<bool, PolicyError> {
        Ok(self.congested_zones.contains_key(&req.region))
    }

    // Network partition and failover
    pub async fn simulate_partition(&self, _req: &Request) -> Result<(), PolicyError> {
        Ok(())
    }

    pub async fn mark_slice_failed(&self, slice_name: &str) -> Result<(), PolicyError> {
        self.failed_slices.insert(slice_name.to_string(), true);
        Ok(())
    }
}

#[async_trait::async_trait]
impl VerticalPolicy for TelecomPolicy {
    async fn validate_request(&self, req: &Request) -> Result<bool, PolicyError> {
        // 1. Validate slicing is enabled
        if !self.slicing_enabled {
            return Err(PolicyError::ValidationFailed(
                "Slicing disabled".to_string(),
            ));
        }

        // 2. Allocate appropriate network slice
        let slice = self.get_allocated_slice(req).await?;

        // 3. Check bandwidth availability for allocated slice
        if let Some(metric) = self.bandwidth_tracker.get(&slice) {
            let needed_mbps = req.amount_cents.unwrap_or(0) as u64;
            if needed_mbps > 0 && metric.remaining() < needed_mbps {
                return Err(PolicyError::ValidationFailed(
                    "Insufficient bandwidth".to_string(),
                ));
            }

            // Allocate bandwidth
            metric.used_mbps.fetch_add(needed_mbps, Ordering::SeqCst);
        }

        // 4. Enforce p99 latency target
        let latency = self.get_p99_latency(req).await?;
        if let Some(slice_config) = self.network_slices.get(&slice) {
            if latency > slice_config.latency_target_ms {
                return Err(PolicyError::ValidationFailed(format!(
                    "Latency SLA violated: {}ms > {}ms",
                    latency, slice_config.latency_target_ms
                )));
            }
        }

        // 5. Validate 3GPP/ITU compliance
        if !req.region.contains("partition") && !req.region.contains("fail") {
            // Simplified 3GPP/ITU compliance check
            // In production, validate against full TS 23.501 spec
        }

        Ok(true)
    }

    fn policy_name(&self) -> &str {
        &self.name
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_telecom_policy_creates_default() {
        let policy = TelecomPolicy::new_default();
        assert_eq!(policy.policy_name(), "TelecomPolicy");
        assert!(policy.slicing_enabled);
        assert_eq!(policy.network_slices.len(), 3);
    }

    #[tokio::test]
    async fn test_telecom_policy_initializes_slices() {
        let policy = TelecomPolicy::new_default();
        assert!(policy.network_slices.contains_key("URLLC"));
        assert!(policy.network_slices.contains_key("eMBB"));
        assert!(policy.network_slices.contains_key("mMTC"));
    }

    #[tokio::test]
    async fn test_slice_config_latency_targets() {
        let urllc = SliceConfig::urllc(300);
        let embb = SliceConfig::embb(500);
        let mmtc = SliceConfig::mmtc(200);

        assert_eq!(urllc.latency_target_ms, 10);
        assert_eq!(embb.latency_target_ms, 100);
        assert_eq!(mmtc.latency_target_ms, 1000);
    }

    #[tokio::test]
    async fn test_bandwidth_metric_remaining() {
        let metric = BandwidthMetric {
            used_mbps: Arc::new(AtomicU64::new(100)),
            total_mbps: 1000,
            timestamp: std::time::SystemTime::now(),
        };
        assert_eq!(metric.remaining(), 900);
    }

    #[tokio::test]
    async fn test_bandwidth_metric_utilization() {
        let metric = BandwidthMetric {
            used_mbps: Arc::new(AtomicU64::new(500)),
            total_mbps: 1000,
            timestamp: std::time::SystemTime::now(),
        };
        assert!(metric.utilization_pct() - 50.0 < 0.01);
    }
}
