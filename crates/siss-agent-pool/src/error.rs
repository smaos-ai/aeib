use thiserror::Error;

#[derive(Error, Debug)]
pub enum PoolError {
    #[error("Pool full")]
    PoolFull,
    #[error("Agent not found")]
    AgentNotFound,
    #[error("Spawn failed: {0}")]
    SpawnFailed(String),
    #[error("Drain timeout")]
    DrainTimeout,
    #[error("Invalid config: {0}")]
    InvalidConfig(String),
    #[error("State migration failed: {0}")]
    MigrationFailed(String),
    #[error("Shutdown failed: {0}")]
    ShutdownFailed(String),
}

pub type Result<T> = std::result::Result<T, PoolError>;
