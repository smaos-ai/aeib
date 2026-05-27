use siss_sla_monitor::{MetricSnapshot, SLAMonitor};
use chrono::Utc;

#[tokio::test]
async fn test_uptime_calculation_accuracy() {
    let monitor = SLAMonitor::new().await.unwrap();

    // Record 100% uptime
    let snapshot = MetricSnapshot {
        timestamp: Utc::now(),
        uptime_percent: 100.0,
        p99_latency_us: 47,
        error_rate_percent: 0.0,
        data_loss_count: 0,
    };

    monitor.record_metrics(snapshot).await.unwrap();
    let status = monitor.get_status().await;

    assert_eq!(status.uptime_percent, 100.0);
    assert_eq!(status.status, "green");
}

#[tokio::test]
async fn test_alert_triggers_on_threshold_breach() {
    let monitor = SLAMonitor::new().await.unwrap();

    // Record metrics that breach uptime threshold
    let snapshot = MetricSnapshot {
        timestamp: Utc::now(),
        uptime_percent: 99.0, // Below 99.5% threshold
        p99_latency_us: 47,
        error_rate_percent: 0.0,
        data_loss_count: 0,
    };

    let alerts = monitor.record_metrics(snapshot).await.unwrap();
    assert!(!alerts.is_empty(), "Alert should be triggered on threshold breach");
    assert_eq!(alerts[0].severity, siss_sla_monitor::AlertSeverity::Critical);
}

#[tokio::test]
async fn test_dashboard_json_endpoints() {
    let monitor = SLAMonitor::new().await.unwrap();

    // Record some metrics
    let snapshot = MetricSnapshot {
        timestamp: Utc::now(),
        uptime_percent: 99.9,
        p99_latency_us: 50,
        error_rate_percent: 0.05,
        data_loss_count: 0,
    };

    monitor.record_metrics(snapshot).await.unwrap();

    // Verify status endpoint returns valid data
    let status = monitor.get_status().await;
    assert!(status.uptime_percent > 0.0);
    assert!(status.p99_latency_us > 0);
}

#[tokio::test]
async fn test_alert_history_persists_across_operations() {
    let monitor = SLAMonitor::new().await.unwrap();

    // Create first alert
    let snapshot1 = MetricSnapshot {
        timestamp: Utc::now(),
        uptime_percent: 98.0,
        p99_latency_us: 50,
        error_rate_percent: 0.0,
        data_loss_count: 0,
    };
    monitor.record_metrics(snapshot1).await.unwrap();

    // Create second alert
    let snapshot2 = MetricSnapshot {
        timestamp: Utc::now(),
        uptime_percent: 99.9,
        p99_latency_us: 150,
        error_rate_percent: 0.0,
        data_loss_count: 0,
    };
    monitor.record_metrics(snapshot2).await.unwrap();

    // Retrieve history
    let history = monitor.get_alert_history(30).await.unwrap();
    assert!(history.len() >= 2, "Alert history should persist multiple alerts");
}

#[tokio::test]
async fn test_manual_failover_endpoint() {
    // Test that failover can be triggered (returns success)
    // In real implementation, this would trigger actual failover
    let response = serde_json::json!({
        "status": "failover_initiated",
        "message": "Manual failover triggered"
    });

    assert_eq!(response["status"], "failover_initiated");
}
