use chrono::{DateTime, Utc};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum L0Error {
    #[error("Cache error: {reason}")]
    CacheError { reason: String },

    #[error("Inference error: {reason}")]
    InferenceError { reason: String },

    #[error("Offline fallback error: {reason}")]
    OfflineFallbackError { reason: String },

    #[error("Ledger integration error: {reason}")]
    LedgerError { reason: String },

    #[error("Serialization error: {reason}")]
    SerializationError { reason: String },

    #[error("Cost tracking error: {reason}")]
    CostTrackingError { reason: String },
}

#[derive(Debug, Clone)]
pub struct L0AuditEntry {
    pub id: String,
    pub timestamp: DateTime<Utc>,
    pub event_type: String,
    pub details: String,
}
