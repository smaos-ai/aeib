use siss_consensus_monitor::ConsensusMetrics;

#[test]
fn test_metrics_round_latency_tracking() {
    let mut metrics = ConsensusMetrics::new();

    // Record latencies from multiple rounds
    metrics.record_round(150, true);
    metrics.record_round(200, true);
    metrics.record_round(180, true);
    metrics.record_round(220, true);
    metrics.record_round(170, true);

    let agg = metrics.aggregate_metrics();
    assert_eq!(agg.total_rounds, 5);
    assert_eq!(agg.min_latency, 150);
    assert_eq!(agg.max_latency, 220);
    assert!(agg.avg_latency > 180 && agg.avg_latency < 190);
}

#[test]
fn test_metrics_byzantine_nodes_aggregation() {
    let mut metrics = ConsensusMetrics::new();

    // Record rounds with Byzantine nodes detected
    metrics.record_byzantine_node("node-malicious-1".to_string());
    metrics.record_byzantine_node("node-malicious-2".to_string());
    metrics.record_byzantine_node("node-malicious-1".to_string()); // duplicate

    let agg = metrics.aggregate_metrics();
    assert!(agg.byzantine_nodes_detected >= 2);
}

#[test]
fn test_metrics_success_rate() {
    let mut metrics = ConsensusMetrics::new();

    // 8 successful, 2 failed
    for _ in 0..8 {
        metrics.record_round(200, true);
    }
    for _ in 0..2 {
        metrics.record_round(600, false);
    }

    let agg = metrics.aggregate_metrics();
    assert_eq!(agg.total_rounds, 10);
    assert_eq!(agg.failed_rounds, 2);
    assert!(agg.success_rate() >= 0.75 && agg.success_rate() <= 0.85);
}

#[test]
fn test_metrics_consensus_quality_score() {
    let mut metrics = ConsensusMetrics::new();

    // High quality: all successful, low latency
    for i in 0..10 {
        metrics.record_round(200 + i as u64, true);
    }

    let agg = metrics.aggregate_metrics();
    let quality = agg.consensus_quality_score();
    assert!(quality > 0.9);
}
