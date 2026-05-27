use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use std::sync::Arc;
use tokio::sync::RwLock;
use uuid::Uuid;
use serde::{Deserialize, Serialize};
use crate::errors::{MultiRegionError, MultiRegionResult};

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum HealthStatus {
    Healthy,
    Degraded,
    Unhealthy,
    Unknown,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RegionHealth {
    pub region_id: String,
    pub status: HealthStatus,
    pub last_heartbeat: u64,
    pub response_time_ms: u64,
    pub error_count: u32,
    pub consecutive_failures: u32,
}

impl RegionHealth {
    pub fn new(region_id: String) -> Self {
        Self {
            region_id,
            status: HealthStatus::Unknown,
            last_heartbeat: current_timestamp(),
            response_time_ms: 0,
            error_count: 0,
            consecutive_failures: 0,
        }
    }
}

pub struct HealthChecker {
    regions: Arc<RwLock<std::collections::HashMap<String, RegionHealth>>>,
    check_interval: Duration,
    failure_threshold: u32,
    recovery_threshold: u32,
}

impl HealthChecker {
    pub fn new(check_interval: Duration) -> Self {
        Self {
            regions: Arc::new(RwLock::new(std::collections::HashMap::new())),
            check_interval,
            failure_threshold: 3,
            recovery_threshold: 2,
        }
    }

    pub async fn register_region(&self, region_id: String) -> MultiRegionResult<()> {
        let mut regions = self.regions.write().await;
        regions.insert(region_id.clone(), RegionHealth::new(region_id));
        Ok(())
    }

    pub async fn record_success(&self, region_id: &str, response_time_ms: u64) -> MultiRegionResult<()> {
        let mut regions = self.regions.write().await;

        if let Some(health) = regions.get_mut(region_id) {
            health.last_heartbeat = current_timestamp();
            health.response_time_ms = response_time_ms;
            health.consecutive_failures = 0;

            // Mark as healthy if response time is acceptable
            if response_time_ms < 5000 {
                health.status = HealthStatus::Healthy;
            } else {
                health.status = HealthStatus::Degraded;
            }
        }
        Ok(())
    }

    pub async fn record_failure(&self, region_id: &str) -> MultiRegionResult<()> {
        let mut regions = self.regions.write().await;

        if let Some(health) = regions.get_mut(region_id) {
            health.error_count += 1;
            health.consecutive_failures += 1;

            if health.consecutive_failures >= self.failure_threshold {
                health.status = HealthStatus::Unhealthy;
            } else {
                health.status = HealthStatus::Degraded;
            }
        }
        Ok(())
    }

    pub async fn get_region_status(&self, region_id: &str) -> MultiRegionResult<HealthStatus> {
        let regions = self.regions.read().await;

        Ok(regions
            .get(region_id)
            .map(|h| h.status.clone())
            .unwrap_or(HealthStatus::Unknown))
    }

    pub async fn get_healthy_regions(&self) -> MultiRegionResult<Vec<String>> {
        let regions = self.regions.read().await;
        Ok(regions
            .iter()
            .filter(|(_, health)| health.status == HealthStatus::Healthy)
            .map(|(id, _)| id.clone())
            .collect())
    }

    pub async fn all_regions_healthy(&self) -> MultiRegionResult<bool> {
        let regions = self.regions.read().await;
        Ok(regions.values().all(|h| h.status == HealthStatus::Healthy))
    }

    pub async fn get_all_health(&self) -> MultiRegionResult<Vec<RegionHealth>> {
        let regions = self.regions.read().await;
        Ok(regions.values().cloned().collect())
    }
}

fn current_timestamp() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_health_checker_initialization() {
        let checker = HealthChecker::new(Duration::from_secs(5));
        checker.register_region("prague".to_string()).await.unwrap();

        let status = checker.get_region_status("prague").await.unwrap();
        assert_eq!(status, HealthStatus::Unknown);
    }

    #[tokio::test]
    async fn test_record_success_marks_healthy() {
        let checker = HealthChecker::new(Duration::from_secs(5));
        checker.register_region("prague".to_string()).await.unwrap();

        checker.record_success("prague", 100).await.unwrap();
        let status = checker.get_region_status("prague").await.unwrap();
        assert_eq!(status, HealthStatus::Healthy);
    }

    #[tokio::test]
    async fn test_consecutive_failures_mark_unhealthy() {
        let checker = HealthChecker::new(Duration::from_secs(5));
        checker.register_region("prague".to_string()).await.unwrap();

        for _ in 0..3 {
            checker.record_failure("prague").await.unwrap();
        }

        let status = checker.get_region_status("prague").await.unwrap();
        assert_eq!(status, HealthStatus::Unhealthy);
    }

    #[tokio::test]
    async fn test_get_healthy_regions() {
        let checker = HealthChecker::new(Duration::from_secs(5));
        checker.register_region("prague".to_string()).await.unwrap();
        checker.register_region("frankfurt".to_string()).await.unwrap();

        checker.record_success("prague", 100).await.unwrap();
        checker.record_failure("frankfurt").await.unwrap();

        let healthy = checker.get_healthy_regions().await.unwrap();
        assert_eq!(healthy.len(), 1);
        assert!(healthy.contains(&"prague".to_string()));
    }
}
