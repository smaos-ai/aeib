use std::time::{Duration, SystemTime, UNIX_EPOCH};
use std::sync::Arc;
use tokio::sync::RwLock;
use uuid::Uuid;
use serde::{Deserialize, Serialize};
use crate::errors::{MultiRegionError, MultiRegionResult};
use std::marker::PhantomData;

// Type-state markers for CircuitBreaker
#[doc = "Closed state: circuit breaker is functioning normally"]
pub struct Closed;
#[doc = "Open state: circuit breaker has failed and is rejecting requests"]
pub struct Open;
#[doc = "HalfOpen state: circuit breaker is testing if service recovered"]
pub struct HalfOpen;

#[derive(Clone, Debug)]
pub struct CircuitBreaker<S> {
    _state: PhantomData<S>,
}

impl CircuitBreaker<Closed> {
    pub fn new(failure_threshold: u32) -> Self {
        Self::with_counts(0, failure_threshold)
    }

    pub fn with_counts(failure_count: u32, failure_threshold: u32) -> Self {
        let _ = (failure_count, failure_threshold);
        CircuitBreaker {
            _state: PhantomData,
        }
    }

    pub fn record_failure(self, _failure_threshold: u32) -> Result<CircuitBreaker<Closed>, CircuitBreaker<Open>> {
        Err(CircuitBreaker {
            _state: PhantomData,
        })
    }
}

impl CircuitBreaker<Open> {
    pub fn try_reset(self, _reset_timeout: Duration) -> Result<CircuitBreaker<Open>, CircuitBreaker<HalfOpen>> {
        Err(CircuitBreaker {
            _state: PhantomData,
        })
    }
}

impl CircuitBreaker<HalfOpen> {
    pub fn record_success(self) -> CircuitBreaker<Closed> {
        CircuitBreaker {
            _state: PhantomData,
        }
    }

    pub fn record_failure(self) -> CircuitBreaker<Open> {
        CircuitBreaker {
            _state: PhantomData,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub enum CircuitBreakerState {
    Closed { failure_count: u32, failure_threshold: u32 },
    Open { opened_at: SystemTime, reset_timeout: Duration },
    HalfOpen { probe_count: u32 },
}

impl Default for CircuitBreakerState {
    fn default() -> Self {
        Self::Closed {
            failure_count: 0,
            failure_threshold: 3,
        }
    }
}

impl CircuitBreakerState {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn record_failure(&mut self, failure_threshold: u32) {
        match self {
            CircuitBreakerState::Closed { failure_count, .. } => {
                *failure_count += 1;
                if *failure_count >= failure_threshold {
                    *self = CircuitBreakerState::Open {
                        opened_at: SystemTime::now(),
                        reset_timeout: Duration::from_secs(60),
                    };
                }
            }
            CircuitBreakerState::HalfOpen { .. } => {
                *self = CircuitBreakerState::Open {
                    opened_at: SystemTime::now(),
                    reset_timeout: Duration::from_secs(60),
                };
            }
            CircuitBreakerState::Open { .. } => {}
        }
    }

    pub fn try_reset(&mut self) {
        if let CircuitBreakerState::Open { opened_at, reset_timeout } = self {
            if let Ok(elapsed) = SystemTime::now().duration_since(*opened_at) {
                if elapsed >= *reset_timeout {
                    *self = CircuitBreakerState::HalfOpen { probe_count: 0 };
                }
            }
        }
    }

    pub fn record_success(&mut self) {
        if let CircuitBreakerState::HalfOpen { .. } = self {
            *self = CircuitBreakerState::Closed {
                failure_count: 0,
                failure_threshold: 3,
            };
        }
    }

    pub fn is_open(&self) -> bool {
        matches!(self, CircuitBreakerState::Open { .. })
    }

    pub fn is_half_open(&self) -> bool {
        matches!(self, CircuitBreakerState::HalfOpen { .. })
    }

    pub fn is_closed(&self) -> bool {
        matches!(self, CircuitBreakerState::Closed { .. })
    }
}

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
    #[serde(skip)]
    pub circuit_breaker: CircuitBreakerState,
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
            circuit_breaker: CircuitBreakerState::new(),
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
            health.circuit_breaker.record_failure(self.failure_threshold);

            if health.circuit_breaker.is_open() {
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
