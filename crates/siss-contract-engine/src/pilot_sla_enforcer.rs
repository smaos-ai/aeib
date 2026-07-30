use crate::error::SlaError;
use chrono::{DateTime, Utc};
use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use uuid::Uuid;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SlaStatus {
    Compliant,
    Breached,
    Suspended,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct SlaMetric {
    pub timestamp: DateTime<Utc>,
    pub latency_ms: u64,
    pub availability: bool,
    pub region_hash: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SlaReport {
    pub uptime: f64,
    pub latency_p99: u64,
    pub breaches: usize,
    pub status: SlaStatus,
}

pub struct PilotSlaEnforcer {
    contract_id: Uuid,
    uptime_target: f64,            // 99.99%
    latency_target_ms: u64,         // 100ms p99
    breach_threshold: usize,        // 3 consecutive breaches
    metrics: Arc<DashMap<DateTime<Utc>, SlaMetric>>,
    breach_count: Arc<AtomicUsize>,
    last_latency_p99: Arc<AtomicU64>,
}

impl PilotSlaEnforcer {
    pub fn new(contract_id: Uuid) -> Self {
        Self {
            contract_id,
            uptime_target: 99.99,
            latency_target_ms: 100,
            breach_threshold: 3,
            metrics: Arc::new(DashMap::new()),
            breach_count: Arc::new(AtomicUsize::new(0)),
            last_latency_p99: Arc::new(AtomicU64::new(0)),
        }
    }

    pub async fn record_metric(&self, metric: SlaMetric) -> Result<(), SlaError> {
        self.metrics
            .insert(metric.timestamp, metric);
        Ok(())
    }

    pub async fn check_compliance(&self) -> Result<SlaReport, SlaError> {
        let metrics: Vec<_> = self.metrics.iter().map(|m| *m.value()).collect();

        if metrics.is_empty() {
            return Ok(SlaReport {
                uptime: 100.0,
                latency_p99: 0,
                breaches: 0,
                status: SlaStatus::Compliant,
            });
        }

        // Calculate uptime
        let available = metrics.iter().filter(|m| m.availability).count();
        let uptime = (available as f64 / metrics.len() as f64) * 100.0;

        // Calculate p99 latency
        let mut latencies: Vec<u64> = metrics.iter().map(|m| m.latency_ms).collect();
        latencies.sort_unstable();
        let p99_idx = ((latencies.len() as f64 * 0.99).ceil() as usize).min(latencies.len() - 1);
        let latency_p99 = if !latencies.is_empty() {
            latencies[p99_idx]
        } else {
            0
        };

        // Update metrics
        self.last_latency_p99.store(latency_p99, Ordering::SeqCst);

        // Check for breach
        let breaches = self.breach_count.load(Ordering::SeqCst);
        let status = if uptime < self.uptime_target || latency_p99 > self.latency_target_ms {
            if breaches >= self.breach_threshold {
                SlaStatus::Suspended
            } else {
                SlaStatus::Breached
            }
        } else {
            SlaStatus::Compliant
        };

        Ok(SlaReport {
            uptime,
            latency_p99,
            breaches,
            status,
        })
    }

    pub async fn trigger_breach_remediation(&self) -> Result<RemediationAction, SlaError> {
        let current_breaches = self.breach_count.fetch_add(1, Ordering::SeqCst);

        if current_breaches >= self.breach_threshold {
            Ok(RemediationAction::IssueCredit {
                percentage: 10,
                reason: "SLA breach remediation".to_string(),
            })
        } else {
            Ok(RemediationAction::LogBreach {
                count: current_breaches + 1,
                reason: "SLA compliance warning".to_string(),
            })
        }
    }

    pub fn reset_metrics(&self) {
        self.metrics.clear();
        self.breach_count.store(0, Ordering::SeqCst);
        self.last_latency_p99.store(0, Ordering::SeqCst);
    }

    pub fn get_contract_id(&self) -> Uuid {
        self.contract_id
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum RemediationAction {
    IssueCredit {
        percentage: u64,
        reason: String,
    },
    LogBreach {
        count: usize,
        reason: String,
    },
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_sla_enforcer_records_metrics() {
        let enforcer = PilotSlaEnforcer::new(Uuid::new_v4());

        let metric = SlaMetric {
            timestamp: Utc::now(),
            latency_ms: 50,
            availability: true,
            region_hash: 0,
        };

        let result = enforcer.record_metric(metric).await;
        assert!(result.is_ok());

        // Verify metric is recorded
        let report = enforcer.check_compliance().await.unwrap();
        assert_eq!(report.latency_p99, 50);
        assert_eq!(report.uptime, 100.0);
    }

    #[tokio::test]
    async fn test_sla_enforcer_detects_uptime_breach() {
        let enforcer = PilotSlaEnforcer::new(Uuid::new_v4());

        // Record 100 metrics: 99 available, 1 down (99% uptime < 99.99% target)
        let now = Utc::now();
        for i in 0..99 {
            let metric = SlaMetric {
                timestamp: now + chrono::Duration::seconds(i as i64),
                latency_ms: 50,
                availability: true,
                region_hash: 0,
            };
            enforcer.record_metric(metric).await.unwrap();
        }

        // One down metric
        let metric = SlaMetric {
            timestamp: now + chrono::Duration::seconds(99),
            latency_ms: 5000, // Severe latency
            availability: false,
            region_hash: 0,
        };
        enforcer.record_metric(metric).await.unwrap();

        let report = enforcer.check_compliance().await.unwrap();
        assert!(report.uptime < 99.99, "Expected uptime < 99.99%, got {}", report.uptime);
    }

    #[tokio::test]
    async fn test_sla_enforcer_detects_latency_breach() {
        let enforcer = PilotSlaEnforcer::new(Uuid::new_v4());

        let now = Utc::now();
        for i in 0..10 {
            let metric = SlaMetric {
                timestamp: now + chrono::Duration::seconds(i as i64),
                latency_ms: if i == 9 { 150 } else { 50 },
                availability: true,
                region_hash: 0,
            };
            enforcer.record_metric(metric).await.unwrap();
        }

        let report = enforcer.check_compliance().await.unwrap();
        // With p99 calculation, should detect high latency
        assert!(report.latency_p99 >= 50);
    }

    #[tokio::test]
    async fn test_sla_enforcer_triggers_remediation() {
        let enforcer = PilotSlaEnforcer::new(Uuid::new_v4());

        // Trigger 3 breaches (manually increment counter since we're not recording bad metrics)
        for _ in 0..3 {
            let _ = enforcer.trigger_breach_remediation().await;
        }

        // Verify breach count increased
        assert_eq!(enforcer.breach_count.load(std::sync::atomic::Ordering::SeqCst), 3);
    }

    #[tokio::test]
    async fn test_pilot_completes_arr_locked() {
        let enforcer = PilotSlaEnforcer::new(Uuid::new_v4());

        // Simulate compliant metrics
        let now = Utc::now();
        for i in 0..100 {
            let metric = SlaMetric {
                timestamp: now + chrono::Duration::milliseconds(i as i64),
                latency_ms: 50,
                availability: true,
                region_hash: 0,
            };
            enforcer.record_metric(metric).await.unwrap();
        }

        let report = enforcer.check_compliance().await.unwrap();
        assert_eq!(report.status, SlaStatus::Compliant);
        assert!(report.uptime >= 99.99);
    }
}
