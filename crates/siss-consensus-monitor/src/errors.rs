use thiserror::Error;

#[derive(Error, Debug)]
pub enum Error {
    #[error("Election timeout")]
    ElectionTimeout,

    #[error("Invalid term")]
    InvalidTerm,

    #[error("Quorum not reached")]
    QuorumNotReached,

    #[error("Leader not found")]
    LeaderNotFound,

    #[error("View change failed: {0}")]
    ViewChangeFailed(String),

    #[error("Health check failed: {0}")]
    HealthCheckFailed(String),
}

pub type Result<T> = std::result::Result<T, Error>;
