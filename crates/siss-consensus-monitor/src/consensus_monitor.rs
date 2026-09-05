use crate::consensus_metrics::ConsensusMetrics;
use parking_lot::RwLock;
use std::collections::HashSet;
use std::sync::Arc;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HealthStatus {
    Healthy,
    Degraded,
    Unhealthy,
}

#[derive(Debug, Clone)]
pub struct HealthReport {
    pub node_id: String,
    pub rounds_completed: u64,
    pub rounds_failed: u64,
    pub avg_latency_ms: u64,
    pub min_latency_ms: u64,
    pub max_latency_ms: u64,
    pub consensus_quality: f64,
    pub leader_id: String,
    pub byzantine_nodes_detected: usize,
}

pub struct ConsensusMonitor {
    node_id: String,
    cluster_size: usize,
    metrics: Arc<RwLock<ConsensusMetrics>>,
    byzantine_nodes: Arc<RwLock<HashSet<String>>>,
}

impl ConsensusMonitor {
    pub fn new(node_id: String, cluster_size: usize) -> Self {
        Self {
            node_id,
            cluster_size,
            metrics: Arc::new(RwLock::new(ConsensusMetrics::new())),
            byzantine_nodes: Arc::new(RwLock::new(HashSet::new())),
        }
    }

    pub fn node_id(&self) -> &str {
        &self.node_id
    }

    pub fn cluster_size(&self) -> usize {
        self.cluster_size
    }

    pub fn track_round(
        &mut self,
        _round_number: u64,
        latency_ms: u64,
        success: bool,
    ) -> crate::Result<()> {
        let mut metrics = self.metrics.write();
        metrics.record_round(latency_ms, success);
        Ok(())
    }

    pub fn mark_byzantine_node(&self, node_id: String) {
        let mut byzantine = self.byzantine_nodes.write();
        byzantine.insert(node_id);
    }

    pub fn get_metrics(&self) -> crate::consensus_metrics::MetricsAggregate {
        let metrics = self.metrics.read();
        metrics.aggregate_metrics()
    }

    pub fn generate_health_report(&self) -> HealthReport {
        let metrics = self.metrics.read();
        let agg = metrics.aggregate_metrics();
        let byzantine = self.byzantine_nodes.read();

        HealthReport {
            node_id: self.node_id.clone(),
            rounds_completed: agg.total_rounds,
            rounds_failed: agg.failed_rounds,
            avg_latency_ms: agg.avg_latency,
            min_latency_ms: agg.min_latency,
            max_latency_ms: agg.max_latency,
            consensus_quality: agg.consensus_quality_score(),
            leader_id: format!("node-{}", agg.total_rounds % self.cluster_size as u64),
            byzantine_nodes_detected: byzantine.len(),
        }
    }

    pub fn health_status(&self) -> HealthStatus {
        let report = self.generate_health_report();

        if report.rounds_failed > report.rounds_completed / 2 {
            HealthStatus::Unhealthy
        } else if report.rounds_failed > 0 {
            HealthStatus::Degraded
        } else {
            HealthStatus::Healthy
        }
    }
}
