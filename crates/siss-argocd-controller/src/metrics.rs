use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};

/// DORA metrics for GitOps deployments
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DoraMetrics {
    pub deployment_frequency: f64,  // deployments per day
    pub lead_time_for_changes: f64, // minutes from commit to deployment
    pub mean_time_to_recovery: f64, // minutes
    pub change_failure_rate: f64,   // percentage of deployments that caused issues
}

/// GitOps sync event
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncEvent {
    pub cluster: String,
    pub app_name: String,
    pub commit_hash: String,
    pub sync_timestamp: DateTime<Utc>,
    pub duration_ms: u32,
    pub success: bool,
}

/// Deployment window statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeploymentWindow {
    pub start_time: DateTime<Utc>,
    pub end_time: DateTime<Utc>,
    pub total_deployments: u32,
    pub successful_deployments: u32,
    pub failed_deployments: u32,
}

impl Default for DoraMetrics {
    fn default() -> Self {
        Self {
            deployment_frequency: 0.0,
            lead_time_for_changes: 0.0,
            mean_time_to_recovery: 0.0,
            change_failure_rate: 0.0,
        }
    }
}

impl DoraMetrics {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn calculate_from_events(events: &[SyncEvent]) -> Self {
        if events.is_empty() {
            return Self::new();
        }

        let total_events = events.len();
        let successful = events.iter().filter(|e| e.success).count();
        let failed = total_events - successful;

        let total_duration_ms: u32 = events.iter().map(|e| e.duration_ms).sum();
        let lead_time = if total_events > 0 {
            (total_duration_ms as f64) / (total_events as f64)
        } else {
            0.0
        };

        let deployment_frequency = (total_events as f64) / 30.0; // per 30 days
        let change_failure_rate = if total_events > 0 {
            ((failed as f64) / (total_events as f64)) * 100.0
        } else {
            0.0
        };

        Self {
            deployment_frequency,
            lead_time_for_changes: lead_time,
            mean_time_to_recovery: 0.0, // would be calculated from incident data
            change_failure_rate,
        }
    }
}

impl DeploymentWindow {
    pub fn new(start_time: DateTime<Utc>) -> Self {
        Self {
            start_time,
            end_time: Utc::now(),
            total_deployments: 0,
            successful_deployments: 0,
            failed_deployments: 0,
        }
    }

    pub fn success_rate(&self) -> f64 {
        if self.total_deployments == 0 {
            return 0.0;
        }
        (self.successful_deployments as f64) / (self.total_deployments as f64)
    }

    pub fn duration(&self) -> Duration {
        self.end_time - self.start_time
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_dora_metrics_calculation() {
        let events = vec![
            SyncEvent {
                cluster: "aws".to_string(),
                app_name: "app1".to_string(),
                commit_hash: "abc123".to_string(),
                sync_timestamp: Utc::now(),
                duration_ms: 500,
                success: true,
            },
            SyncEvent {
                cluster: "gcp".to_string(),
                app_name: "app2".to_string(),
                commit_hash: "def456".to_string(),
                sync_timestamp: Utc::now(),
                duration_ms: 600,
                success: true,
            },
            SyncEvent {
                cluster: "azure".to_string(),
                app_name: "app3".to_string(),
                commit_hash: "ghi789".to_string(),
                sync_timestamp: Utc::now(),
                duration_ms: 400,
                success: false,
            },
        ];

        let metrics = DoraMetrics::calculate_from_events(&events);
        assert!(metrics.deployment_frequency > 0.0);
        assert!(metrics.lead_time_for_changes > 0.0);
        assert!(metrics.change_failure_rate > 0.0);
    }

    #[test]
    fn test_deployment_window_success_rate() {
        let mut window = DeploymentWindow::new(Utc::now());
        window.total_deployments = 10;
        window.successful_deployments = 9;
        window.failed_deployments = 1;

        let rate = window.success_rate();
        assert_eq!(rate, 0.9);
    }
}
