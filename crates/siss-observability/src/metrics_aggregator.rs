use crate::{Metrics, Result, ObservabilityError};
use dashmap::DashMap;
use std::sync::Arc;
use uuid::Uuid;

#[derive(Debug, Clone)]
pub struct AggregatedMetrics {
    pub span_id: Uuid,
    pub total_requests: u64,
    pub total_errors: u64,
    pub avg_latency_ms: f64,
    pub min_latency_ms: f64,
    pub max_latency_ms: f64,
    pub p99_latency_ms: f64,
    pub throughput_rps: f64,
    pub error_rate: f64,
}

impl AggregatedMetrics {
    pub fn new(span_id: Uuid) -> Self {
        Self {
            span_id,
            total_requests: 0,
            total_errors: 0,
            avg_latency_ms: 0.0,
            min_latency_ms: 0.0,
            max_latency_ms: 0.0,
            p99_latency_ms: 0.0,
            throughput_rps: 0.0,
            error_rate: 0.0,
        }
    }
}

pub struct MetricsAggregator {
    metrics: Arc<DashMap<Uuid, Vec<Metrics>>>,
    aggregated: Arc<DashMap<Uuid, AggregatedMetrics>>,
}

impl MetricsAggregator {
    pub fn new() -> Self {
        Self {
            metrics: Arc::new(DashMap::new()),
            aggregated: Arc::new(DashMap::new()),
        }
    }

    pub fn record_metric(&self, span_id: Uuid, metric: Metrics) {
        self.metrics
            .entry(span_id)
            .or_default()
            .push(metric);
    }

    pub fn aggregate(&self, span_id: Uuid) -> Result<AggregatedMetrics> {
        let metrics_list = self.metrics
            .get(&span_id)
            .ok_or(ObservabilityError::TraceNotFound(span_id.to_string()))?
            .clone();

        if metrics_list.is_empty() {
            return Err(ObservabilityError::InvalidSpan("No metrics for span".into()));
        }

        let total_requests: u64 = metrics_list.iter().map(|m| m.request_count).sum();
        let total_errors: u64 = metrics_list.iter().map(|m| m.error_count).sum();

        let avg_latency = if !metrics_list.is_empty() {
            metrics_list.iter().map(|m| m.latency_ms).sum::<f64>() / metrics_list.len() as f64
        } else {
            0.0
        };

        let min_latency = metrics_list
            .iter()
            .map(|m| m.latency_ms)
            .fold(f64::INFINITY, f64::min);

        let max_latency = metrics_list
            .iter()
            .map(|m| m.latency_ms)
            .fold(0.0, f64::max);

        let throughput = metrics_list.iter().map(|m| m.throughput).sum::<f64>() / metrics_list.len() as f64;

        let error_rate = if total_requests > 0 {
            (total_errors as f64 / total_requests as f64) * 100.0
        } else {
            0.0
        };

        // P99 calculation
        let mut latencies: Vec<f64> = metrics_list.iter().map(|m| m.latency_ms).collect();
        latencies.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        let p99_idx = ((latencies.len() as f64 * 0.99) as usize).min(latencies.len() - 1);
        let p99 = if latencies.is_empty() { 0.0 } else { latencies[p99_idx] };

        let agg = AggregatedMetrics {
            span_id,
            total_requests,
            total_errors,
            avg_latency_ms: avg_latency,
            min_latency_ms: if min_latency == f64::INFINITY { 0.0 } else { min_latency },
            max_latency_ms: max_latency,
            p99_latency_ms: p99,
            throughput_rps: throughput,
            error_rate,
        };

        self.aggregated.insert(span_id, agg.clone());
        Ok(agg)
    }

    pub fn get_aggregated(&self, span_id: Uuid) -> Option<AggregatedMetrics> {
        self.aggregated.get(&span_id).map(|a| a.clone())
    }

    pub fn get_all_aggregated(&self) -> Vec<AggregatedMetrics> {
        self.aggregated.iter().map(|entry| entry.value().clone()).collect()
    }

    pub fn clear_metrics(&self, span_id: Uuid) {
        self.metrics.remove(&span_id);
    }

    pub fn get_raw_metrics(&self, span_id: Uuid) -> Option<Vec<Metrics>> {
        self.metrics.get(&span_id).map(|m| m.clone())
    }

    pub fn metric_count(&self) -> usize {
        self.metrics.iter().map(|entry| entry.value().len()).sum()
    }

    pub fn aggregated_count(&self) -> usize {
        self.aggregated.len()
    }
}

impl Default for MetricsAggregator {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_metric(latency: f64, requests: u64, errors: u64) -> Metrics {
        Metrics {
            latency_ms: latency,
            throughput: 100.0,
            error_rate: if requests > 0 { (errors as f64 / requests as f64) * 100.0 } else { 0.0 },
            request_count: requests,
            error_count: errors,
        }
    }

    #[test]
    fn test_record_metric() {
        let agg = MetricsAggregator::new();
        let span_id = Uuid::new_v4();
        let metric = sample_metric(50.0, 100, 0);

        agg.record_metric(span_id, metric);
        assert_eq!(agg.metric_count(), 1);
    }

    #[test]
    fn test_aggregate_single_metric() {
        let agg = MetricsAggregator::new();
        let span_id = Uuid::new_v4();
        let metric = sample_metric(50.0, 100, 5);

        agg.record_metric(span_id, metric);
        let result = agg.aggregate(span_id).unwrap();

        assert_eq!(result.total_requests, 100);
        assert_eq!(result.total_errors, 5);
        assert_eq!(result.avg_latency_ms, 50.0);
        assert!((result.error_rate - 5.0).abs() < 0.1);
    }

    #[test]
    fn test_aggregate_multiple_metrics() {
        let agg = MetricsAggregator::new();
        let span_id = Uuid::new_v4();

        agg.record_metric(span_id, sample_metric(50.0, 100, 5));
        agg.record_metric(span_id, sample_metric(100.0, 100, 10));
        agg.record_metric(span_id, sample_metric(75.0, 100, 7));

        let result = agg.aggregate(span_id).unwrap();

        assert_eq!(result.total_requests, 300);
        assert_eq!(result.total_errors, 22);
        assert!((result.avg_latency_ms - 75.0).abs() < 0.1);
    }

    #[test]
    fn test_latency_percentiles() {
        let agg = MetricsAggregator::new();
        let span_id = Uuid::new_v4();

        for i in 1..=100 {
            agg.record_metric(span_id, sample_metric(i as f64, 1, 0));
        }

        let result = agg.aggregate(span_id).unwrap();

        assert_eq!(result.min_latency_ms, 1.0);
        assert_eq!(result.max_latency_ms, 100.0);
        assert!(result.p99_latency_ms >= 99.0);
    }

    #[test]
    fn test_error_rate_calculation() {
        let agg = MetricsAggregator::new();
        let span_id = Uuid::new_v4();

        agg.record_metric(span_id, sample_metric(50.0, 1000, 50));
        let result = agg.aggregate(span_id).unwrap();

        assert!((result.error_rate - 5.0).abs() < 0.1);
    }

    #[test]
    fn test_get_aggregated() {
        let agg = MetricsAggregator::new();
        let span_id = Uuid::new_v4();

        agg.record_metric(span_id, sample_metric(50.0, 100, 0));
        agg.aggregate(span_id).unwrap();

        let retrieved = agg.get_aggregated(span_id);
        assert!(retrieved.is_some());
        assert_eq!(retrieved.unwrap().span_id, span_id);
    }

    #[test]
    fn test_clear_metrics() {
        let agg = MetricsAggregator::new();
        let span_id = Uuid::new_v4();

        agg.record_metric(span_id, sample_metric(50.0, 100, 0));
        assert_eq!(agg.metric_count(), 1);

        agg.clear_metrics(span_id);
        assert_eq!(agg.metric_count(), 0);
    }

    #[test]
    fn test_throughput_aggregation() {
        let agg = MetricsAggregator::new();
        let span_id = Uuid::new_v4();

        agg.record_metric(span_id, sample_metric(50.0, 100, 0));
        agg.record_metric(span_id, sample_metric(50.0, 100, 0));

        let result = agg.aggregate(span_id).unwrap();
        assert!(result.throughput_rps > 0.0);
    }

    #[test]
    fn test_get_all_aggregated() {
        let agg = MetricsAggregator::new();

        for _ in 0..5 {
            let span_id = Uuid::new_v4();
            agg.record_metric(span_id, sample_metric(50.0, 100, 0));
            agg.aggregate(span_id).unwrap();
        }

        let all = agg.get_all_aggregated();
        assert_eq!(all.len(), 5);
    }

    #[test]
    fn test_aggregate_nonexistent_span() {
        let agg = MetricsAggregator::new();
        let span_id = Uuid::new_v4();

        let result = agg.aggregate(span_id);
        assert!(result.is_err());
    }
}
