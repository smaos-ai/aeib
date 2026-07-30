#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HealthCheckResult {
    pub status: HealthStatus,
    pub message: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HealthStatus {
    Healthy,
    Degraded,
    Failed,
}

impl HealthCheckResult {
    pub fn healthy() -> Self {
        Self {
            status: HealthStatus::Healthy,
            message: "All systems operational".to_string(),
        }
    }

    pub fn degraded(message: &str) -> Self {
        Self {
            status: HealthStatus::Degraded,
            message: message.to_string(),
        }
    }

    pub fn failed(message: &str) -> Self {
        Self {
            status: HealthStatus::Failed,
            message: message.to_string(),
        }
    }
}
