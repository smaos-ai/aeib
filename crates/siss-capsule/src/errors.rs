use thiserror::Error;

#[derive(Error, Debug)]
pub enum CapsuleError {
    #[error("Policy verification failed: {0}")]
    PolicyVerificationFailed(String),

    #[error("Tool authorization failed: {0}")]
    ToolAuthorizationFailed(String),

    #[error("Context isolation violated: {0}")]
    ContextIsolationViolated(String),

    #[error("Audit logging failed: {0}")]
    AuditLoggingFailed(String),

    #[error("Harness configuration error: {0}")]
    HarnessConfigError(String),

    #[error("Serialization error: {0}")]
    SerializationError(#[from] serde_json::Error),

    #[error("Cryptographic error: {0}")]
    CryptoError(String),

    #[error("Timeout: {0}")]
    Timeout(String),

    #[error("Resource not found: {0}")]
    NotFound(String),

    #[error("Invalid state: {0}")]
    InvalidState(String),
}

pub type Result<T> = std::result::Result<T, CapsuleError>;
