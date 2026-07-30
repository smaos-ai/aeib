use siss_consensus_monitor::ConsensusMonitor;

#[test]
fn test_monitor_creation() {
    let monitor = ConsensusMonitor::new("node-1".to_string(), 7);
    assert_eq!(monitor.node_id(), "node-1");
    assert_eq!(monitor.cluster_size(), 7);
}

#[test]
fn test_track_consensus_round_latency() {
    let mut monitor = ConsensusMonitor::new("node-2".to_string(), 7);
    let result = monitor.track_round(1, 250, true);

    assert!(result.is_ok());
    let metrics = monitor.get_metrics();
    assert_eq!(metrics.rounds_completed, 1);
    assert_eq!(metrics.last_latency_ms, 250);
}

#[test]
fn test_detect_consensus_success() {
    let mut monitor = ConsensusMonitor::new("node-3".to_string(), 7);

    // Track 5 successful rounds
    for i in 1..=5 {
        monitor.track_round(i, 200 + i as u64 * 10, true).unwrap();
    }

    let report = monitor.generate_health_report();
    assert_eq!(report.rounds_completed, 5);
    assert!(report.consensus_quality >= 0.95);
}

#[test]
fn test_detect_consensus_failure() {
    let mut monitor = ConsensusMonitor::new("node-4".to_string(), 7);

    // Track 3 successful, 2 failed
    monitor.track_round(1, 200, true).unwrap();
    monitor.track_round(2, 210, true).unwrap();
    monitor.track_round(3, 220, true).unwrap();
    monitor.track_round(4, 500, false).unwrap();
    monitor.track_round(5, 600, false).unwrap();

    let report = monitor.generate_health_report();
    assert_eq!(report.rounds_completed, 5);
    assert_eq!(report.rounds_failed, 2);
    assert!(report.consensus_quality < 0.95);
}

#[test]
fn test_report_generation() {
    let mut monitor = ConsensusMonitor::new("node-5".to_string(), 7);

    for i in 1..=10 {
        monitor
            .track_round(i, 250 + (i % 3) as u64 * 50, true)
            .unwrap();
    }

    let report = monitor.generate_health_report();
    assert!(!report.leader_id.is_empty());
    assert_eq!(report.rounds_completed, 10);
    assert!(report.avg_latency_ms > 0);
    assert!(report.avg_latency_ms < 1000);
}

#[test]
fn test_health_status_degradation() {
    let mut monitor = ConsensusMonitor::new("node-6".to_string(), 7);

    // Healthy: all successful
    for i in 1..=5 {
        monitor.track_round(i, 200, true).unwrap();
    }
    let status = monitor.health_status();
    assert!(
        matches!(status, siss_consensus_monitor::HealthStatus::Healthy),
        "Expected Healthy, got {:?}",
        status
    );

    // Degraded: some failures
    for i in 6..=10 {
        monitor.track_round(i, 600, false).unwrap();
    }
    let status = monitor.health_status();
    assert!(
        matches!(status, siss_consensus_monitor::HealthStatus::Degraded),
        "Expected Degraded, got {:?}",
        status
    );

    // Unhealthy: many failures
    for i in 11..=20 {
        monitor.track_round(i, 1000, false).unwrap();
    }
    let status = monitor.health_status();
    assert!(
        matches!(status, siss_consensus_monitor::HealthStatus::Unhealthy),
        "Expected Unhealthy, got {:?}",
        status
    );
}

#[test]
fn test_byzantine_node_detection() {
    let monitor = ConsensusMonitor::new("node-7".to_string(), 7);

    // Mark a node as Byzantine
    monitor.mark_byzantine_node("malicious-node-1".to_string());

    let report = monitor.generate_health_report();
    assert_eq!(report.byzantine_nodes_detected, 1);

    // Mark another
    monitor.mark_byzantine_node("malicious-node-2".to_string());
    let report = monitor.generate_health_report();
    assert_eq!(report.byzantine_nodes_detected, 2);
}

#[test]
fn test_metrics_aggregation() {
    let mut monitor = ConsensusMonitor::new("node-8".to_string(), 7);

    let latencies = vec![100, 150, 200, 250, 300];
    for (i, latency) in latencies.iter().enumerate() {
        monitor.track_round((i + 1) as u64, *latency, true).unwrap();
    }

    let report = monitor.generate_health_report();
    assert_eq!(report.min_latency_ms, 100);
    assert_eq!(report.max_latency_ms, 300);
    assert!(report.avg_latency_ms > 190 && report.avg_latency_ms < 210);
}
