/// Phase 40: Edge Orchestrator — Geo-Distributed 5G Edge Scheduling
/// Manages edge node placement with latency constraints and slice affinity.

use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EdgeNode {
    pub id: Uuid,
    pub name: String,
    pub rtt_ms: u16,
    pub available_cpu_cores: u16,
    pub available_memory_mb: u32,
    pub network_slice: String,
    pub geo_zone: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrchestratorConfig {
    pub max_rtt_ms: u16,
    pub enable_failover: bool,
    pub geo_zone: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EdgeScheduleResult {
    pub node: EdgeNode,
    pub optimization_score: f64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EdgeScheduleError {
    NoFeasibleNode,
    LatencyConstraintViolation,
    InsufficientResources,
}

pub struct EdgeOrchestrator {
    config: OrchestratorConfig,
    nodes: Arc<DashMap<Uuid, EdgeNode>>,
}

impl EdgeOrchestrator {
    pub fn new(config: OrchestratorConfig) -> Self {
        Self {
            config,
            nodes: Arc::new(DashMap::new()),
        }
    }

    /// Select edge node respecting latency RTT budget
    pub fn select_edge_node(
        &self,
        candidates: &[EdgeNode],
        cpu_cores_needed: u16,
        memory_mb_needed: u32,
    ) -> Result<EdgeScheduleResult, EdgeScheduleError> {
        // Filter by latency constraint
        let feasible: Vec<_> = candidates
            .iter()
            .filter(|node| node.rtt_ms <= self.config.max_rtt_ms)
            .filter(|node| {
                node.available_cpu_cores >= cpu_cores_needed
                    && node.available_memory_mb >= memory_mb_needed
            })
            .collect();

        if feasible.is_empty() {
            // Check if failure is due to latency
            if candidates.iter().any(|n| n.rtt_ms > self.config.max_rtt_ms) {
                return Err(EdgeScheduleError::LatencyConstraintViolation);
            }
            return Err(EdgeScheduleError::InsufficientResources);
        }

        // Greedy: select node with most available resources
        let selected = feasible
            .iter()
            .max_by_key(|n| n.available_memory_mb)
            .unwrap();

        Ok(EdgeScheduleResult {
            node: (*selected).clone(),
            optimization_score: 0.85,
        })
    }

    /// Route task to correct network slice
    pub fn select_edge_node_for_slice(
        &self,
        candidates: &[EdgeNode],
        slice_name: &str,
        cpu_cores_needed: u16,
        memory_mb_needed: u32,
    ) -> Result<EdgeScheduleResult, EdgeScheduleError> {
        // Filter by slice affinity first
        let slice_matched: Vec<_> = candidates
            .iter()
            .filter(|node| node.network_slice == slice_name)
            .collect();

        if slice_matched.is_empty() {
            return Err(EdgeScheduleError::NoFeasibleNode);
        }

        // Then apply latency and resource filters
        let feasible: Vec<_> = slice_matched
            .iter()
            .filter(|node| node.rtt_ms <= self.config.max_rtt_ms)
            .filter(|node| {
                node.available_cpu_cores >= cpu_cores_needed
                    && node.available_memory_mb >= memory_mb_needed
            })
            .collect();

        if feasible.is_empty() {
            return Err(EdgeScheduleError::InsufficientResources);
        }

        let selected = feasible
            .iter()
            .max_by_key(|n| n.available_memory_mb)
            .unwrap();

        Ok(EdgeScheduleResult {
            node: (**selected).clone(),
            optimization_score: 0.90,
        })
    }

    /// Cost-optimized selection among candidates
    pub fn select_edge_node_optimized(
        &self,
        candidates: &[EdgeNode],
        cpu_cores_needed: u16,
        memory_mb_needed: u32,
    ) -> Result<EdgeScheduleResult, EdgeScheduleError> {
        let feasible: Vec<_> = candidates
            .iter()
            .filter(|node| node.rtt_ms <= self.config.max_rtt_ms)
            .filter(|node| {
                node.available_cpu_cores >= cpu_cores_needed
                    && node.available_memory_mb >= memory_mb_needed
            })
            .collect();

        if feasible.is_empty() {
            return Err(EdgeScheduleError::InsufficientResources);
        }

        // Optimization score: prefer lower RTT and more resources
        let selected = feasible
            .iter()
            .max_by(|a, b| {
                let score_a = (a.available_memory_mb as f64) / (a.rtt_ms as f64 + 1.0);
                let score_b = (b.available_memory_mb as f64) / (b.rtt_ms as f64 + 1.0);
                score_a.partial_cmp(&score_b).unwrap_or(std::cmp::Ordering::Equal)
            })
            .unwrap();

        let optimization_score = (selected.available_memory_mb as f64)
            / (selected.rtt_ms as f64 + 1.0) / 1000.0;

        Ok(EdgeScheduleResult {
            node: (*selected).clone(),
            optimization_score,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_orchestrator() {
        let config = OrchestratorConfig {
            max_rtt_ms: 50,
            enable_failover: true,
            geo_zone: "us-west-2".to_string(),
        };
        let _orchestrator = EdgeOrchestrator::new(config);
    }
}
