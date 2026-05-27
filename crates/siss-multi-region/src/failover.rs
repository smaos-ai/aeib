use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use std::sync::Arc;
use tokio::sync::RwLock;
use uuid::Uuid;
use serde::{Deserialize, Serialize};
use crate::errors::{MultiRegionError, MultiRegionResult};
use crate::health_check::{HealthChecker, HealthStatus};

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum FailoverDecision {
    NoFailover,
    FailoverToRegion { target_region: String, reason: String },
    HaltOnSplitBrain { detected_regions: Vec<String> },
}

pub struct FailoverManager {
    primary_region: String,
    secondary_regions: Vec<String>,
    health_checker: Arc<HealthChecker>,
    failover_threshold_ms: u64,
    last_failover: Arc<RwLock<Option<u64>>>,
    cooldown_period_ms: u64,
    total_regions: usize,
    quorum_size: usize,
}

impl FailoverManager {
    pub fn new(
        primary_region: String,
        secondary_regions: Vec<String>,
        health_checker: Arc<HealthChecker>,
    ) -> Self {
        let total_regions = secondary_regions.len() + 1;
        let quorum_size = (total_regions / 2) + 1;

        Self {
            primary_region,
            secondary_regions,
            health_checker,
            failover_threshold_ms: 30000, // 30 seconds
            last_failover: Arc::new(RwLock::new(None)),
            cooldown_period_ms: 60000, // 60 seconds between failovers
            total_regions,
            quorum_size,
        }
    }

    /// Evaluate failover decision based on region health
    pub async fn evaluate_failover(&self) -> MultiRegionResult<FailoverDecision> {
        let health_statuses = self.health_checker.get_all_health().await?;

        // Check if primary is down
        let primary_healthy = health_statuses
            .iter()
            .any(|h| h.region_id == self.primary_region && h.status == HealthStatus::Healthy);

        if !primary_healthy {
            // Primary is down, check quorum
            let healthy_secondaries: Vec<String> = health_statuses
                .iter()
                .filter(|h| {
                    h.status == HealthStatus::Healthy
                        && self.secondary_regions.contains(&h.region_id)
                })
                .map(|h| h.region_id.clone())
                .collect();

            // Check if we have quorum (majority of all regions)
            let healthy_count = if primary_healthy { 1 } else { 0 } + healthy_secondaries.len();

            if healthy_count >= self.quorum_size {
                // We have quorum, promote best secondary
                if let Some(target) = self.select_best_secondary(&healthy_secondaries) {
                    // Check cooldown
                    if self.can_failover().await {
                        self.record_failover().await?;
                        return Ok(FailoverDecision::FailoverToRegion {
                            target_region: target,
                            reason: format!("Primary region {} failed, promoting secondary", self.primary_region),
                        });
                    }
                }
            } else {
                // No quorum, detect split-brain
                return Ok(FailoverDecision::HaltOnSplitBrain {
                    detected_regions: health_statuses.iter().map(|h| h.region_id.clone()).collect(),
                });
            }
        }

        Ok(FailoverDecision::NoFailover)
    }

    /// Select the best secondary region based on health metrics
    fn select_best_secondary(&self, healthy_secondaries: &[String]) -> Option<String> {
        // For now, return first healthy secondary. Can be extended with load balancing logic.
        healthy_secondaries.first().cloned()
    }

    /// Check if enough time has passed since last failover
    async fn can_failover(&self) -> bool {
        let last_fo = self.last_failover.read().await;

        if let Some(last_ts) = *last_fo {
            let current_ts = current_timestamp();
            current_ts - last_ts >= self.cooldown_period_ms
        } else {
            true
        }
    }

    /// Record the time of failover
    async fn record_failover(&self) -> MultiRegionResult<()> {
        let mut last_fo = self.last_failover.write().await;
        *last_fo = Some(current_timestamp());
        Ok(())
    }

    /// Get quorum size
    pub fn get_quorum_size(&self) -> usize {
        self.quorum_size
    }

    /// Check if quorum is achieved
    pub async fn is_quorum_achieved(&self) -> MultiRegionResult<bool> {
        let healthy = self.health_checker.get_healthy_regions().await?;
        let healthy_count = healthy.len();

        Ok(healthy_count >= self.quorum_size)
    }

    /// Force promotion of a specific region (use with caution)
    pub async fn force_promotion(&self, target_region: &str) -> MultiRegionResult<FailoverDecision> {
        if self.can_failover().await {
            self.record_failover().await?;
            Ok(FailoverDecision::FailoverToRegion {
                target_region: target_region.to_string(),
                reason: "Forced promotion".to_string(),
            })
        } else {
            Err(MultiRegionError::InvalidConfiguration(
                "Failover in cooldown period".to_string(),
            ))
        }
    }
}

fn current_timestamp() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_millis() as u64
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_failover_manager_initialization() {
        let checker = Arc::new(HealthChecker::new(Duration::from_secs(5)));
        let manager = FailoverManager::new(
            "prague".to_string(),
            vec!["frankfurt".to_string()],
            checker,
        );

        assert_eq!(manager.get_quorum_size(), 2);
    }

    #[tokio::test]
    async fn test_quorum_calculation_three_regions() {
        let checker = Arc::new(HealthChecker::new(Duration::from_secs(5)));
        let manager = FailoverManager::new(
            "prague".to_string(),
            vec!["frankfurt".to_string(), "london".to_string()],
            checker,
        );

        // 3 regions total, quorum should be 2
        assert_eq!(manager.get_quorum_size(), 2);
    }

    #[tokio::test]
    async fn test_no_failover_when_primary_healthy() {
        let checker = Arc::new(HealthChecker::new(Duration::from_secs(5)));
        checker.register_region("prague".to_string()).await.unwrap();
        checker.register_region("frankfurt".to_string()).await.unwrap();
        checker.record_success("prague", 100).await.unwrap();
        checker.record_success("frankfurt", 150).await.unwrap();

        let manager = FailoverManager::new(
            "prague".to_string(),
            vec!["frankfurt".to_string()],
            checker,
        );

        let decision = manager.evaluate_failover().await.unwrap();
        assert_eq!(decision, FailoverDecision::NoFailover);
    }

    #[tokio::test]
    async fn test_failover_on_primary_failure() {
        let checker = Arc::new(HealthChecker::new(Duration::from_secs(5)));
        checker.register_region("prague".to_string()).await.unwrap();
        checker.register_region("frankfurt".to_string()).await.unwrap();

        // Primary fails
        for _ in 0..3 {
            checker.record_failure("prague").await.unwrap();
        }
        // Secondary healthy
        checker.record_success("frankfurt", 100).await.unwrap();

        let manager = FailoverManager::new(
            "prague".to_string(),
            vec!["frankfurt".to_string()],
            checker,
        );

        let decision = manager.evaluate_failover().await.unwrap();
        match decision {
            FailoverDecision::FailoverToRegion { target_region, .. } => {
                assert_eq!(target_region, "frankfurt");
            }
            _ => panic!("Expected failover decision"),
        }
    }
}
