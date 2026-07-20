use thiserror::Error;

#[derive(Error, Debug)]
pub enum VisionError {
    #[error("Unknown platform: {0}")]
    UnknownPlatform(String),

    #[error("Rate limited: {0}")]
    RateLimited(String),

    #[error("Auth error: {0}")]
    AuthError(String),

    #[error("Policy error: {0}")]
    PolicyError(String),

    #[error("Adapter error: {0}")]
    AdapterError(String),

    #[error("Storage error: {0}")]
    StorageError(String),

    #[error("Token error: {0}")]
    TokenError(String),

    #[error("Revenue error: {0}")]
    RevenueError(String),

    #[error("Audit error: {0}")]
    AuditError(String),
}

pub type Result<T> = std::result::Result<T, VisionError>;
