use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use uuid::Uuid;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub struct ExecutionLatency {
    pub agent_id: Uuid,
    pub latency_ms: u32,
    pub timestamp: u64,
}

#[derive(Clone, Debug)]
pub enum BottleneckType {
    SingleAgentSlow {
        agent_id: Uuid,
        latency_ms: u32,
    },
    ClusterCongestion {
        avg_latency_ms: u32,
        affected_count: usize,
    },
    CascadingDelay {
        root_agent: Uuid,
        depth: usize,
    },
}

#[derive(Clone, Debug)]
pub struct BottleneckDiagnosis {
    pub bottleneck_type: BottleneckType,
    pub confidence: f64,
    pub affected_agents: Vec<Uuid>,
    pub root_cause_latency: u32,
    pub binary_search_depth: usize,
}

pub struct CentralMonitoringOracle {
    timeline: BTreeMap<u64, Vec<ExecutionLatency>>,
    agent_count: usize,
    percentile_threshold: u32,
}

impl CentralMonitoringOracle {
    pub fn new(expected_agent_count: usize) -> Self {
        Self {
            timeline: BTreeMap::new(),
            agent_count: expected_agent_count,
            percentile_threshold: 95,
        }
    }

    pub fn record_execution(&mut self, latency: ExecutionLatency) {
        self.timeline
            .entry(latency.timestamp)
            .or_insert_with(Vec::new)
            .push(latency);
    }

    pub fn detect_bottleneck(&self) -> Option<BottleneckDiagnosis> {
        if self.timeline.is_empty() {
            return None;
        }

        let empty_vec = vec![];
        let mut search_depth = 0;
        let timeline_entries = self.timeline.len();
        let mut low = 0;
        let mut high = timeline_entries - 1;

        while low < high {
            search_depth += 1;
            let mid = (low + high) / 2;

            let mid_timestamp = self.timeline.keys().nth(mid).copied().unwrap_or_default();
            let mid_latencies = self.timeline.get(&mid_timestamp).unwrap_or(&empty_vec);

            if let Some(diagnosis) = self.analyze_latencies(mid_latencies, search_depth) {
                return Some(diagnosis);
            }

            let high_timestamp = self.timeline.keys().nth(high).copied().unwrap_or_default();
            let high_latencies = self.timeline.get(&high_timestamp).unwrap_or(&empty_vec);

            let avg_high = high_latencies
                .iter()
                .map(|l| l.latency_ms as u64)
                .sum::<u64>()
                / high_latencies.len().max(1) as u64;
            let avg_mid = mid_latencies
                .iter()
                .map(|l| l.latency_ms as u64)
                .sum::<u64>()
                / mid_latencies.len().max(1) as u64;

            if avg_high > avg_mid {
                low = mid + 1;
            } else {
                high = mid;
            }
        }

        let final_timestamp = self.timeline.keys().nth(high).copied().unwrap_or_default();
        let final_latencies = self.timeline.get(&final_timestamp).unwrap_or(&empty_vec);
        self.analyze_latencies(final_latencies, search_depth)
    }

    fn analyze_latencies(
        &self,
        latencies: &[ExecutionLatency],
        search_depth: usize,
    ) -> Option<BottleneckDiagnosis> {
        if latencies.is_empty() {
            return None;
        }

        let avg =
            latencies.iter().map(|l| l.latency_ms as u64).sum::<u64>() / latencies.len() as u64;
        let max_latency = latencies.iter().map(|l| l.latency_ms).max().unwrap_or(0);

        if max_latency > self.percentile_threshold {
            let slow_agents: Vec<Uuid> = latencies
                .iter()
                .filter(|l| l.latency_ms > self.percentile_threshold)
                .map(|l| l.agent_id)
                .collect();

            if slow_agents.len() == 1 {
                return Some(BottleneckDiagnosis {
                    bottleneck_type: BottleneckType::SingleAgentSlow {
                        agent_id: slow_agents[0],
                        latency_ms: max_latency,
                    },
                    confidence: 0.95,
                    affected_agents: slow_agents,
                    root_cause_latency: max_latency,
                    binary_search_depth: search_depth,
                });
            } else if slow_agents.len() > 1 {
                return Some(BottleneckDiagnosis {
                    bottleneck_type: BottleneckType::ClusterCongestion {
                        avg_latency_ms: avg as u32,
                        affected_count: slow_agents.len(),
                    },
                    confidence: 0.85,
                    affected_agents: slow_agents,
                    root_cause_latency: max_latency,
                    binary_search_depth: search_depth,
                });
            }
        }

        None
    }

    pub fn get_percentile_latency(&self, percentile: u32) -> Option<u32> {
        if self.timeline.is_empty() {
            return None;
        }

        let mut all_latencies: Vec<u32> = self
            .timeline
            .values()
            .flat_map(|v| v.iter().map(|l| l.latency_ms))
            .collect();

        if all_latencies.is_empty() {
            return None;
        }

        all_latencies.sort_unstable();
        let idx = ((percentile as usize * all_latencies.len()) / 100).min(all_latencies.len() - 1);
        Some(all_latencies[idx])
    }

    pub fn timeline_depth(&self) -> usize {
        self.timeline.len()
    }

    pub fn total_executions(&self) -> usize {
        self.timeline.values().map(|v| v.len()).sum()
    }
}

impl Default for CentralMonitoringOracle {
    fn default() -> Self {
        Self::new(50)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cmo_creation() {
        let cmo = CentralMonitoringOracle::new(50);
        assert_eq!(cmo.agent_count, 50);
        assert_eq!(cmo.timeline_depth(), 0);
    }

    #[test]
    fn test_record_execution() {
        let mut cmo = CentralMonitoringOracle::new(50);
        let latency = ExecutionLatency {
            agent_id: Uuid::new_v4(),
            latency_ms: 50,
            timestamp: 1000,
        };
        cmo.record_execution(latency);
        assert_eq!(cmo.total_executions(), 1);
    }

    #[test]
    fn test_detect_single_slow_agent() {
        let mut cmo = CentralMonitoringOracle::new(3);
        let agent_fast_1 = Uuid::new_v4();
        let agent_fast_2 = Uuid::new_v4();
        let agent_slow = Uuid::new_v4();

        cmo.record_execution(ExecutionLatency {
            agent_id: agent_fast_1,
            latency_ms: 50,
            timestamp: 1000,
        });
        cmo.record_execution(ExecutionLatency {
            agent_id: agent_fast_2,
            latency_ms: 55,
            timestamp: 1000,
        });
        cmo.record_execution(ExecutionLatency {
            agent_id: agent_slow,
            latency_ms: 200,
            timestamp: 1000,
        });

        let diagnosis = cmo.detect_bottleneck();
        assert!(diagnosis.is_some());
        let diag = diagnosis.unwrap();
        assert!(matches!(
            diag.bottleneck_type,
            BottleneckType::SingleAgentSlow { .. }
        ));
    }

    #[test]
    fn test_detect_cluster_congestion() {
        let mut cmo = CentralMonitoringOracle::new(5);
        let agents: Vec<_> = (0..5).map(|_| Uuid::new_v4()).collect();

        for agent in &agents {
            cmo.record_execution(ExecutionLatency {
                agent_id: *agent,
                latency_ms: 150,
                timestamp: 1000,
            });
        }

        let diagnosis = cmo.detect_bottleneck();
        assert!(diagnosis.is_some());
        let diag = diagnosis.unwrap();
        assert!(matches!(
            diag.bottleneck_type,
            BottleneckType::ClusterCongestion { .. }
        ));
    }

    #[test]
    fn test_get_percentile_latency() {
        let mut cmo = CentralMonitoringOracle::new(10);
        let agent = Uuid::new_v4();

        for i in 0..100 {
            cmo.record_execution(ExecutionLatency {
                agent_id: agent,
                latency_ms: i as u32,
                timestamp: 1000 + i as u64,
            });
        }

        let p50 = cmo.get_percentile_latency(50);
        assert!(p50.is_some());
        let p95 = cmo.get_percentile_latency(95);
        assert!(p95.is_some());
        assert!(p95.unwrap() > p50.unwrap());
    }

    #[test]
    fn test_binary_search_depth_logarithmic() {
        let mut cmo = CentralMonitoringOracle::new(64);
        let agent_slow = Uuid::new_v4();

        for t in 0..128 {
            let latency_ms = if t >= 64 { 200 } else { 50 };
            cmo.record_execution(ExecutionLatency {
                agent_id: agent_slow,
                latency_ms,
                timestamp: 1000 + t as u64,
            });
        }

        let diagnosis = cmo.detect_bottleneck();
        assert!(diagnosis.is_some());
        let diag = diagnosis.unwrap();
        assert!(diag.binary_search_depth <= 8);
    }

    #[test]
    fn test_empty_timeline() {
        let cmo = CentralMonitoringOracle::new(50);
        assert!(cmo.detect_bottleneck().is_none());
        assert!(cmo.get_percentile_latency(95).is_none());
    }

    #[test]
    fn test_multiple_timestamps() {
        let mut cmo = CentralMonitoringOracle::new(10);
        let agent = Uuid::new_v4();

        for ts in 0..5 {
            cmo.record_execution(ExecutionLatency {
                agent_id: agent,
                latency_ms: 50 + ts as u32,
                timestamp: 1000 + ts as u64,
            });
        }

        assert_eq!(cmo.timeline_depth(), 5);
        assert_eq!(cmo.total_executions(), 5);
    }

    #[test]
    fn test_multiple_agents_per_timestamp() {
        let mut cmo = CentralMonitoringOracle::new(4);
        let agents: Vec<_> = (0..4).map(|_| Uuid::new_v4()).collect();

        for agent in &agents {
            cmo.record_execution(ExecutionLatency {
                agent_id: *agent,
                latency_ms: 80,
                timestamp: 1000,
            });
        }

        assert_eq!(cmo.timeline_depth(), 1);
        assert_eq!(cmo.total_executions(), 4);
    }

    #[test]
    fn test_bottleneck_confidence_single_vs_cluster() {
        let mut cmo1 = CentralMonitoringOracle::new(3);
        let agent1 = Uuid::new_v4();
        let agent2 = Uuid::new_v4();
        let agent3 = Uuid::new_v4();

        cmo1.record_execution(ExecutionLatency {
            agent_id: agent1,
            latency_ms: 50,
            timestamp: 1000,
        });
        cmo1.record_execution(ExecutionLatency {
            agent_id: agent2,
            latency_ms: 55,
            timestamp: 1000,
        });
        cmo1.record_execution(ExecutionLatency {
            agent_id: agent3,
            latency_ms: 200,
            timestamp: 1000,
        });

        let diag1 = cmo1.detect_bottleneck().unwrap();
        assert_eq!(diag1.confidence, 0.95);

        let mut cmo2 = CentralMonitoringOracle::new(3);
        for agent in &[agent1, agent2, agent3] {
            cmo2.record_execution(ExecutionLatency {
                agent_id: *agent,
                latency_ms: 150,
                timestamp: 1000,
            });
        }

        let diag2 = cmo2.detect_bottleneck().unwrap();
        assert_eq!(diag2.confidence, 0.85);
    }
}
