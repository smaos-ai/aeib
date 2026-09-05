use thiserror::Error;

pub type Result<T> = std::result::Result<T, A2AError>;

#[derive(Error, Debug)]
pub enum A2AError {
    #[error("Peer not found: {0}")]
    PeerNotFound(String),

    #[error("Signature verification failed")]
    SignatureVerificationFailed,

    #[error("Message tampering detected")]
    MessageTampering,

    #[error("Handoff conflict: {0}")]
    HandoffConflict(String),

    #[error("Task state corrupted: {0}")]
    TaskStateCorrupted(String),

    #[error("Ledger integrity violation")]
    LedgerIntegrityViolation,

    #[error("Cryptographic error: {0}")]
    CryptoError(String),

    #[error("Serialization error: {0}")]
    SerializationError(String),

    #[error("Network error: {0}")]
    NetworkError(String),

    #[error("Vault integration error: {0}")]
    VaultError(String),

    #[error("Peer manifest expired")]
    PeerManifestExpired,

    #[error("Capability not available: {0}")]
    CapabilityNotAvailable(String),

    #[error("Invalid message: {0}")]
    InvalidMessage(String),

    #[error("Task not found: {0}")]
    TaskNotFound(String),

    #[error("Handoff timeout")]
    HandoffTimeout,

    #[error("Internal error: {0}")]
    InternalError(String),
}

impl From<anyhow::Error> for A2AError {
    fn from(err: anyhow::Error) -> Self {
        A2AError::InternalError(err.to_string())
    }
}

impl From<serde_json::Error> for A2AError {
    fn from(err: serde_json::Error) -> Self {
        A2AError::SerializationError(err.to_string())
    }
}
