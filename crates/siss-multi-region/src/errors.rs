use std::fmt;
use thiserror::Error;

pub type MultiRegionResult<T> = Result<T, MultiRegionError>;

#[derive(Error, Debug, Clone)]
pub enum MultiRegionError {
    #[error("Replication failed for capsule {capsule_id}: {reason}")]
    ReplicationFailed { capsule_id: String, reason: String },

    #[error("Network error: {0}")]
    NetworkError(String),

    #[error("Region unavailable: {region}")]
    RegionUnavailable { region: String },

    #[error("Split-brain detected: {reason}")]
    SplitBrainDetected { reason: String },

    #[error("Sync timeout: {0}")]
    SyncTimeout(String),

    #[error("Vector clock conflict: {0}")]
    VectorClockConflict(String),

    #[error("Reconciliation failed: {0}")]
    ReconciliationFailed(String),

    #[error("Invalid configuration: {0}")]
    InvalidConfiguration(String),

    #[error("Quorum not achieved")]
    QuorumNotAchieved,

    #[error("Clock skew exceeds threshold: {skew_ms}ms")]
    ClockSkewExceeded { skew_ms: i64 },

    #[error("Invalid capsule hash")]
    InvalidCapsuleHash,

    #[error("Serialization error: {0}")]
    SerializationError(String),

    #[error("Database error: {0}")]
    DatabaseError(String),
}

impl From<serde_json::Error> for MultiRegionError {
    fn from(e: serde_json::Error) -> Self {
        MultiRegionError::SerializationError(e.to_string())
    }
}
