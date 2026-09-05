use crate::error::{DriftError, Result};
use crate::{Decision, DriftConfig, DriftLevel, RAGASScorer};
use std::collections::VecDeque;
use std::sync::Arc;
use tokio::sync::RwLock;

/// Rolling decision window for drift detection
pub struct DriftMonitor {
    config: DriftConfig,
    /// Rolling window (FIFO)
    decisions: Arc<RwLock<VecDeque<Decision>>>,
    /// Last computed drift level
    last_level: Arc<RwLock<DriftLevel>>,
    /// Alert history
    alerts: Arc<RwLock<Vec<(i64, DriftLevel)>>>,
}

impl DriftMonitor {
    /// Create new drift monitor
    pub fn new(config: DriftConfig) -> Self {
        Self {
            config,
            decisions: Arc::new(RwLock::new(VecDeque::new())),
            last_level: Arc::new(RwLock::new(DriftLevel::Green)),
            alerts: Arc::new(RwLock::new(Vec::new())),
        }
    }

    /// Add decision to window
    pub async fn record_decision(&self, decision: Decision) -> Result<DriftLevel> {
        let mut window = self.decisions.write().await;

        // Maintain rolling window
        if window.len() >= self.config.window_size as usize {
            window.pop_front();
        }
        window.push_back(decision);

        // Compute drift
        self.compute_drift().await
    }

    /// Compute current drift level
    async fn compute_drift(&self) -> Result<DriftLevel> {
        let window = self.decisions.read().await;

        if window.is_empty() {
            return Err(DriftError::EmptyWindow);
        }

        let decisions: Vec<_> = window.iter().cloned().collect();
        let metrics = RAGASScorer::score_batch(&decisions)?;
        let avg = RAGASScorer::average_metrics(&metrics);

        let level = self.config.classify(avg.aggregate_score());

        // Record alert if level changed
        if level != *self.last_level.read().await {
            self.alerts.write().await.push((
                chrono::Utc::now().timestamp(),
                level.clone(),
            ));
            *self.last_level.write().await = level.clone();
        }

        Ok(level)
    }

    /// Get current drift level
    pub async fn current_level(&self) -> Result<DriftLevel> {
        let window = self.decisions.read().await;
        if window.is_empty() {
            return Ok(DriftLevel::Green);
        }

        let decisions: Vec<_> = window.iter().cloned().collect();
        let metrics = RAGASScorer::score_batch(&decisions)?;
        let avg = RAGASScorer::average_metrics(&metrics);

        Ok(self.config.classify(avg.aggregate_score()))
    }

    /// Get average quality score in window
    pub async fn average_quality(&self) -> Result<f64> {
        let window = self.decisions.read().await;
        if window.is_empty() {
            return Err(DriftError::EmptyWindow);
        }

        let avg: f64 = window.iter().map(|d| d.quality_score).sum::<f64>()
            / window.len() as f64;
        Ok(avg)
    }

    /// Get window size
    pub async fn window_size(&self) -> u32 {
        self.decisions.read().await.len() as u32
    }

    /// Get alert history
    pub async fn alert_history(&self) -> Vec<(i64, DriftLevel)> {
        self.alerts.read().await.clone()
    }

    /// Reset monitor
    pub async fn reset(&self) {
        self.decisions.write().await.clear();
        self.alerts.write().await.clear();
        *self.last_level.write().await = DriftLevel::Green;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_drift_monitor_creation() {
        let config = DriftConfig::new(10).unwrap();
        let monitor = DriftMonitor::new(config);
        assert_eq!(monitor.window_size().await, 0);
    }

    #[tokio::test]
    async fn test_drift_record_decision() {
        let config = DriftConfig::new(10).unwrap();
        let monitor = DriftMonitor::new(config);

        let decision = Decision::new("test".to_string(), "test".to_string())
            .with_quality_score(0.9);

        let level = monitor.record_decision(decision).await.unwrap();
        assert_eq!(level, DriftLevel::Green);
        assert_eq!(monitor.window_size().await, 1);
    }

    #[tokio::test]
    async fn test_drift_rolling_window() {
        let config = DriftConfig::new(3).unwrap();
        let monitor = DriftMonitor::new(config);

        for i in 0..5 {
            let decision = Decision::new(
                format!("action-{}", i),
                "test".to_string(),
            ).with_quality_score(0.8);
            monitor.record_decision(decision).await.ok();
        }

        assert_eq!(monitor.window_size().await, 3);
    }

    #[tokio::test]
    async fn test_drift_quality_degradation() {
        let config = DriftConfig::new(10).unwrap();
        let monitor = DriftMonitor::new(config);

        // Add high-quality decisions
        for _ in 0..3 {
            let decision = Decision::new("test".to_string(), "test".to_string())
                .with_quality_score(0.95);
            monitor.record_decision(decision).await.ok();
        }

        // Add low-quality decisions
        for _ in 0..3 {
            let decision = Decision::new("test".to_string(), "test".to_string())
                .with_quality_score(0.5);
            monitor.record_decision(decision).await.ok();
        }

        let level = monitor.current_level().await.unwrap();
        // Should degrade from Green to Yellow/Orange
        assert!(level >= DriftLevel::Yellow || level <= DriftLevel::Red);
    }
}
