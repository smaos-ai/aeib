use crate::error::{OtelError, Result};
use serde::{Deserialize, Serialize};

/// SLA threshold
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SLAThreshold {
    pub name: String,
    pub latency_p99_ms: u32,
    pub latency_p95_ms: u32,
    pub error_rate: f64,
}

impl Default for SLAThreshold {
    fn default() -> Self {
        Self {
            name: "default".to_string(),
            latency_p99_ms: 1000,
            latency_p95_ms: 500,
            error_rate: 0.01,
        }
    }
}

/// SLA metric
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SLAMetric {
    pub latencies_ms: Vec<u32>,
    pub error_count: u32,
    pub total_count: u32,
    pub timestamp: i64,
}

impl SLAMetric {
    /// Create new metric
    pub fn new() -> Self {
        Self {
            latencies_ms: Vec::new(),
            error_count: 0,
            total_count: 0,
            timestamp: chrono::Utc::now().timestamp(),
        }
    }

    /// Add latency measurement
    pub fn record_latency(&mut self, latency_ms: u32) {
        self.latencies_ms.push(latency_ms);
        self.total_count += 1;
    }

    /// Record error
    pub fn record_error(&mut self) {
        self.error_count += 1;
        self.total_count += 1;
    }

    /// Calculate p99 latency
    pub fn p99_latency(&self) -> Option<u32> {
        if self.latencies_ms.is_empty() {
            return None;
        }
        let mut sorted = self.latencies_ms.clone();
        sorted.sort_unstable();
        let idx = (sorted.len() * 99) / 100;
        Some(sorted[idx])
    }

    /// Calculate p95 latency
    pub fn p95_latency(&self) -> Option<u32> {
        if self.latencies_ms.is_empty() {
            return None;
        }
        let mut sorted = self.latencies_ms.clone();
        sorted.sort_unstable();
        let idx = (sorted.len() * 95) / 100;
        Some(sorted[idx])
    }

    /// Calculate error rate
    pub fn error_rate(&self) -> f64 {
        if self.total_count == 0 {
            return 0.0;
        }
        self.error_count as f64 / self.total_count as f64
    }
}

/// SLA Monitor
pub struct SLAMonitor {
    threshold: SLAThreshold,
    metric: std::sync::Arc<std::sync::Mutex<SLAMetric>>,
}

impl SLAMonitor {
    /// Create new monitor
    pub fn new(threshold: SLAThreshold) -> Self {
        Self {
            threshold,
            metric: std::sync::Arc::new(std::sync::Mutex::new(SLAMetric::new())),
        }
    }

    /// Check if SLA is violated
    pub fn check_sla_violation(&self) -> Result<bool> {
        let metric = self.metric.lock().unwrap();

        if let Some(p99) = metric.p99_latency() {
            if p99 > self.threshold.latency_p99_ms {
                return Ok(true);
            }
        }

        if metric.error_rate() > self.threshold.error_rate {
            return Ok(true);
        }

        Ok(false)
    }

    /// Record latency
    pub fn record_latency(&self, latency_ms: u32) {
        self.metric.lock().unwrap().record_latency(latency_ms);
    }

    /// Record error
    pub fn record_error(&self) {
        self.metric.lock().unwrap().record_error();
    }

    /// Get current metrics
    pub fn get_metrics(&self) -> SLAMetric {
        self.metric.lock().unwrap().clone()
    }

    /// Reset metrics
    pub fn reset(&self) {
        *self.metric.lock().unwrap() = SLAMetric::new();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sla_metric_creation() {
        let metric = SLAMetric::new();
        assert_eq!(metric.total_count, 0);
    }

    #[test]
    fn test_sla_record_latency() {
        let mut metric = SLAMetric::new();
        metric.record_latency(100);
        metric.record_latency(200);
        assert_eq!(metric.latencies_ms.len(), 2);
    }

    #[test]
    fn test_sla_p99_calculation() {
        let mut metric = SLAMetric::new();
        for i in 1..=100 {
            metric.record_latency(i as u32);
        }
        assert_eq!(metric.p99_latency(), Some(99));
    }

    #[test]
    fn test_sla_error_rate() {
        let mut metric = SLAMetric::new();
        metric.record_latency(100);
        metric.record_latency(200);
        metric.record_error();
        metric.record_error();
        assert!(metric.error_rate() > 0.4 && metric.error_rate() < 0.6);
    }

    #[test]
    fn test_sla_monitor_violation() {
        let mut threshold = SLAThreshold::default();
        threshold.latency_p99_ms = 50;
        let monitor = SLAMonitor::new(threshold);

        monitor.record_latency(100);
        monitor.record_latency(200);
        monitor.record_latency(300);

        assert!(monitor.check_sla_violation().unwrap());
    }
}
