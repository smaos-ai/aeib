#[cfg(test)]
mod integration_tests {
    use crate::{DriftMonitor, DriftConfig, Decision, DriftLevel};

    #[tokio::test]
    async fn test_drift_full_cycle() {
        let config = DriftConfig::new(100).unwrap();
        let monitor = DriftMonitor::new(config);

        // Simulate 50 high-quality decisions
        for i in 0..50 {
            let decision = Decision::new(
                format!("approve-{}", i),
                "meets high standards".to_string(),
            ).with_quality_score(0.92);
            monitor.record_decision(decision).await.ok();
        }

        let level = monitor.current_level().await.unwrap();
        assert_eq!(level, DriftLevel::Green);

        // Simulate degradation: 30 low-quality decisions
        for i in 0..30 {
            let decision = Decision::new(
                format!("borderline-{}", i),
                "marginal approval".to_string(),
            ).with_quality_score(0.62);
            monitor.record_decision(decision).await.ok();
        }

        let level = monitor.current_level().await.unwrap();
        assert!(level >= DriftLevel::Orange);
    }

    #[tokio::test]
    async fn test_drift_alert_history() {
        let config = DriftConfig::new(20).unwrap();
        let monitor = DriftMonitor::new(config);

        // Add decisions with varying quality
        for i in 0..30 {
            let quality = if i < 10 { 0.95 } else { 0.55 };
            let decision = Decision::new("test".to_string(), "test".to_string())
                .with_quality_score(quality);
            monitor.record_decision(decision).await.ok();
        }

        let alerts = monitor.alert_history().await;
        // Should have recorded alert when transitioning from Green to Red
        assert!(!alerts.is_empty());
    }

    #[tokio::test]
    async fn test_drift_reset() {
        let config = DriftConfig::new(10).unwrap();
        let monitor = DriftMonitor::new(config);

        let decision = Decision::new("test".to_string(), "test".to_string())
            .with_quality_score(0.5);
        monitor.record_decision(decision).await.ok();

        assert!(monitor.window_size().await > 0);

        monitor.reset().await;
        assert_eq!(monitor.window_size().await, 0);
    }

    #[tokio::test]
    async fn test_drift_concurrent_recording() {
        let config = DriftConfig::new(100).unwrap();
        let monitor = std::sync::Arc::new(DriftMonitor::new(config));

        let mut handles = vec![];
        for i in 0..20 {
            let monitor = monitor.clone();
            let handle = tokio::spawn(async move {
                let decision = Decision::new(
                    format!("action-{}", i),
                    "test".to_string(),
                ).with_quality_score(0.8);
                monitor.record_decision(decision).await.ok()
            });
            handles.push(handle);
        }

        for handle in handles {
            handle.await.ok();
        }

        assert_eq!(monitor.window_size().await, 20);
    }
}
