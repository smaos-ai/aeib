use siss_orchestrator::{ExecutionLatency, BottleneckType, CentralMonitoringOracle};
use uuid::Uuid;

#[test]
fn test_phase_3_3_single_slow_agent_diagnosis() {
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
    assert!(matches!(diag.bottleneck_type, BottleneckType::SingleAgentSlow { .. }));
    assert!(diag.confidence >= 0.9);
    assert!(diag.affected_agents.len() == 1);
}

#[test]
fn test_phase_3_3_cluster_congestion_diagnosis() {
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
    assert!(matches!(diag.bottleneck_type, BottleneckType::ClusterCongestion { .. }));
    assert!(diag.affected_agents.len() >= 2);
}

#[test]
fn test_phase_3_3_cascading_delay_detection() {
    let mut cmo = CentralMonitoringOracle::new(4);
    let agents: Vec<_> = (0..4).map(|_| Uuid::new_v4()).collect();

    for ts in 0..8 {
        for (idx, agent) in agents.iter().enumerate() {
            let latency = if ts < 4 {
                50 + idx as u32 * 10
            } else {
                150 + idx as u32 * 20
            };
            cmo.record_execution(ExecutionLatency {
                agent_id: *agent,
                latency_ms: latency,
                timestamp: 1000 + ts as u64,
            });
        }
    }

    let diagnosis = cmo.detect_bottleneck();
    assert!(diagnosis.is_some());
    let diag = diagnosis.unwrap();
    assert!(diag.binary_search_depth <= 4);
}

#[test]
fn test_phase_3_3_binary_search_depth_logarithmic_bound() {
    let mut cmo = CentralMonitoringOracle::new(128);
    let agent_slow = Uuid::new_v4();

    for t in 0..256 {
        let latency_ms = if t >= 128 { 250 } else { 50 };
        cmo.record_execution(ExecutionLatency {
            agent_id: agent_slow,
            latency_ms,
            timestamp: 1000 + t as u64,
        });
    }

    let diagnosis = cmo.detect_bottleneck();
    assert!(diagnosis.is_some());
    let diag = diagnosis.unwrap();
    assert!(diag.binary_search_depth <= 9, "Binary search depth should be O(log n), got {}", diag.binary_search_depth);
}

#[test]
fn test_phase_3_3_root_cause_latency_identification() {
    let mut cmo = CentralMonitoringOracle::new(3);
    let agent1 = Uuid::new_v4();
    let agent2 = Uuid::new_v4();
    let agent3 = Uuid::new_v4();

    cmo.record_execution(ExecutionLatency {
        agent_id: agent1,
        latency_ms: 50,
        timestamp: 2000,
    });
    cmo.record_execution(ExecutionLatency {
        agent_id: agent2,
        latency_ms: 60,
        timestamp: 2000,
    });
    cmo.record_execution(ExecutionLatency {
        agent_id: agent3,
        latency_ms: 300,
        timestamp: 2000,
    });

    let diagnosis = cmo.detect_bottleneck();
    assert!(diagnosis.is_some());
    let diag = diagnosis.unwrap();
    assert_eq!(diag.root_cause_latency, 300);
}

#[test]
fn test_phase_3_3_confidence_single_vs_cluster() {
    let mut cmo1 = CentralMonitoringOracle::new(3);
    let agent1 = Uuid::new_v4();
    let agent2 = Uuid::new_v4();
    let agent3 = Uuid::new_v4();

    cmo1.record_execution(ExecutionLatency {
        agent_id: agent1,
        latency_ms: 50,
        timestamp: 3000,
    });
    cmo1.record_execution(ExecutionLatency {
        agent_id: agent2,
        latency_ms: 55,
        timestamp: 3000,
    });
    cmo1.record_execution(ExecutionLatency {
        agent_id: agent3,
        latency_ms: 200,
        timestamp: 3000,
    });

    let diag1 = cmo1.detect_bottleneck().unwrap();
    assert_eq!(diag1.confidence, 0.95, "Single slow agent should have high confidence");

    let mut cmo2 = CentralMonitoringOracle::new(3);
    for agent in &[agent1, agent2, agent3] {
        cmo2.record_execution(ExecutionLatency {
            agent_id: *agent,
            latency_ms: 150,
            timestamp: 3000,
        });
    }

    let diag2 = cmo2.detect_bottleneck().unwrap();
    assert_eq!(diag2.confidence, 0.85, "Cluster congestion should have lower confidence");
}

#[test]
fn test_phase_3_3_percentile_latency_query() {
    let mut cmo = CentralMonitoringOracle::new(10);
    let agent = Uuid::new_v4();

    for i in 0..100 {
        cmo.record_execution(ExecutionLatency {
            agent_id: agent,
            latency_ms: i as u32,
            timestamp: 4000 + i as u64,
        });
    }

    let p50 = cmo.get_percentile_latency(50);
    assert!(p50.is_some());
    let p95 = cmo.get_percentile_latency(95);
    assert!(p95.is_some());
    assert!(p95.unwrap() > p50.unwrap());
}

#[test]
fn test_phase_3_3_multiple_diagnosis_events() {
    let mut cmo = CentralMonitoringOracle::new(3);
    let agents: Vec<_> = (0..3).map(|_| Uuid::new_v4()).collect();

    for batch in 0..3 {
        for (idx, agent) in agents.iter().enumerate() {
            let latency = 50 + (batch * 50) as u32 + idx as u32 * 10;
            cmo.record_execution(ExecutionLatency {
                agent_id: *agent,
                latency_ms: latency,
                timestamp: 5000 + batch as u64 * 100 + idx as u64,
            });
        }
    }

    assert!(cmo.timeline_depth() > 0);
    assert!(cmo.total_executions() >= 9);
}

#[test]
fn test_phase_3_3_empty_timeline_no_diagnosis() {
    let cmo = CentralMonitoringOracle::new(50);
    let diagnosis = cmo.detect_bottleneck();
    assert!(diagnosis.is_none());
}

#[test]
fn test_phase_3_3_anomaly_detection_threshold() {
    let mut cmo = CentralMonitoringOracle::new(5);
    let agents: Vec<_> = (0..5).map(|_| Uuid::new_v4()).collect();

    for agent in &agents {
        cmo.record_execution(ExecutionLatency {
            agent_id: *agent,
            latency_ms: 45,
            timestamp: 6000,
        });
    }

    let diagnosis = cmo.detect_bottleneck();
    assert!(diagnosis.is_none(), "No diagnosis for healthy latencies");

    let agent_slow = Uuid::new_v4();
    cmo.record_execution(ExecutionLatency {
        agent_id: agent_slow,
        latency_ms: 200,
        timestamp: 6001,
    });

    let diagnosis = cmo.detect_bottleneck();
    assert!(diagnosis.is_some(), "Should detect anomaly when latency exceeds threshold");
}
