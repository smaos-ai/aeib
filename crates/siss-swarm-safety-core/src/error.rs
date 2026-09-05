//! Error types for swarm safety core

use thiserror::Error;

#[derive(Error, Debug)]
pub enum Error {
    #[error("RCE gate violation: {0}")]
    RceViolation(String),

    #[error("Security boundary breach: {0}")]
    SecurityBreach(String),

    #[error("DAG scheduling error: {0}")]
    SchedulingError(String),

    #[error("Invalid schedule: {0}")]
    InvalidSchedule(String),

    #[error("Agent communication timeout")]
    CommunicationTimeout,

    #[error("Agent not found: {0}")]
    AgentNotFound(String),

    #[error("Invalid DAG: {0}")]
    InvalidDag(String),

    #[error("Serialization error: {0}")]
    SerializationError(#[from] serde_json::Error),

    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),

    #[error("Unknown error: {0}")]
    Unknown(String),
}

pub type Result<T> = std::result::Result<T, Error>;
