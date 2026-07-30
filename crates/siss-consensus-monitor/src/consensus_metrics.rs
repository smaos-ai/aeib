use std::collections::HashSet;

#[derive(Debug, Clone)]
pub struct MetricsAggregate {
    pub total_rounds: u64,
    pub failed_rounds: u64,
    pub avg_latency: u64,
    pub min_latency: u64,
    pub max_latency: u64,
    pub last_latency_ms: u64,
    pub rounds_completed: u64,
    pub byzantine_nodes_detected: usize,
}

impl MetricsAggregate {
    pub fn success_rate(&self) -> f64 {
        if self.total_rounds == 0 {
            1.0
        } else {
            (self.total_rounds - self.failed_rounds) as f64 / self.total_rounds as f64
        }
    }

    pub fn consensus_quality_score(&self) -> f64 {
        let success_weight = 0.9;
        let latency_weight = 0.1;

        let success_score = self.success_rate();
        let latency_score = if self.avg_latency > 500 {
            0.5  // Penalize if latency exceeds 500ms
        } else if self.avg_latency > 0 {
            1.0 - (self.avg_latency as f64 / 500.0) * 0.5
        } else {
            1.0
        };

        success_weight * success_score + latency_weight * latency_score
    }
}

pub struct ConsensusMetrics {
    latencies: Vec<u64>,
    failures: Vec<bool>,
    byzantine_nodes: HashSet<String>,
}

impl ConsensusMetrics {
    pub fn new() -> Self {
        Self {
            latencies: Vec::new(),
            failures: Vec::new(),
            byzantine_nodes: HashSet::new(),
        }
    }

    pub fn record_round(&mut self, latency_ms: u64, success: bool) {
        self.latencies.push(latency_ms);
        self.failures.push(!success);
    }

    pub fn record_byzantine_node(&mut self, node_id: String) {
        self.byzantine_nodes.insert(node_id);
    }

    pub fn aggregate_metrics(&self) -> MetricsAggregate {
        let total_rounds = self.latencies.len() as u64;
        let failed_rounds = self.failures.iter().filter(|&&f| f).count() as u64;
        let last_latency = self.latencies.last().copied().unwrap_or(0);

        let (min_latency, max_latency, avg_latency) = if !self.latencies.is_empty() {
            let min = *self.latencies.iter().min().unwrap_or(&0);
            let max = *self.latencies.iter().max().unwrap_or(&0);
            let avg = self.latencies.iter().sum::<u64>() / self.latencies.len() as u64;
            (min, max, avg)
        } else {
            (0, 0, 0)
        };

        MetricsAggregate {
            total_rounds,
            failed_rounds,
            avg_latency,
            min_latency,
            max_latency,
            last_latency_ms: last_latency,
            rounds_completed: total_rounds,
            byzantine_nodes_detected: self.byzantine_nodes.len(),
        }
    }
}

impl Default for ConsensusMetrics {
    fn default() -> Self {
        Self::new()
    }
}
