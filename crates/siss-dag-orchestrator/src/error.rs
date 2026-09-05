//! Error types for DAG orchestrator

use thiserror::Error;

#[derive(Error, Debug)]
pub enum Error {
    #[error("Compilation error: {0}")]
    CompilationError(String),

    #[error("Execution error: {0}")]
    ExecutionError(String),

    #[error("Checkpoint error: {0}")]
    CheckpointError(String),

    #[error("Invalid DAG: {0}")]
    InvalidDag(String),

    #[error("Task not found: {0}")]
    TaskNotFound(String),

    #[error("Execution failed: {0}")]
    ExecutionFailed(String),

    #[error("Recovery failed: {0}")]
    RecoveryFailed(String),

    #[error("Serialization error: {0}")]
    SerializationError(#[from] serde_json::Error),

    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),

    #[error("Unknown error: {0}")]
    Unknown(String),
}

pub type Result<T> = std::result::Result<T, Error>;
