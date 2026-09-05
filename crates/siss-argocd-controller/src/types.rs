use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// ArgoCD ApplicationSet template configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApplicationSetTemplate {
    pub name: String,
    pub namespace: String,
    pub source_repo: String,
    pub target_revision: String,
}

/// Kubernetes cluster configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClusterConfig {
    pub name: String,
    pub api_url: String,
    pub enabled: bool,
}

/// Sync status of deployment
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub enum SyncStatus {
    Synced,
    OutOfSync,
    Unknown,
    Progressing,
    Failed,
}

/// Deployment proof record
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeploymentProof {
    pub commit_hash: String,
    pub clusters_deployed: Vec<String>,
    pub sync_status: SyncStatus,
    pub timestamp: DateTime<Utc>,
}

/// Deployment metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeploymentMetrics {
    pub deployment_count: u32,
    pub success_rate: f64,
    pub average_sync_time_ms: u32,
}
