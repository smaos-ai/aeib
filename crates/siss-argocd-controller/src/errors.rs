use thiserror::Error;

#[derive(Error, Debug)]
pub enum DeploymentError {
    #[error("Cluster not found: {0}")]
    ClusterNotFound(String),

    #[error("Git sync failed: {0}")]
    GitSyncError(String),

    #[error("Deployment failed: {0}")]
    DeploymentFailed(String),

    #[error("Sync status retrieval failed: {0}")]
    SyncStatusError(String),

    #[error("Configuration drift detected: {0}")]
    DriftDetected(String),

    #[error("Rollback failed: {0}")]
    RollbackFailed(String),

    #[error("RBAC error: {0}")]
    RbacError(String),

    #[error("Notification failed: {0}")]
    NotificationError(String),

    #[error("Invalid configuration: {0}")]
    InvalidConfiguration(String),
}
