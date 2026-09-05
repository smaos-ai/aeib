//! Error types for semantic cache compactor

use thiserror::Error;

#[derive(Error, Debug)]
pub enum Error {
    #[error("Cache compaction failed: {0}")]
    CompactionFailed(String),

    #[error("Memory pruning error: {0}")]
    PruningError(String),

    #[error("Cost tracking error: {0}")]
    CostError(String),

    #[error("Cache entry not found: {0}")]
    EntryNotFound(String),

    #[error("Invalid cache key: {0}")]
    InvalidKey(String),

    #[error("Semantic similarity error: {0}")]
    SimilarityError(String),

    #[error("Memory exceeded: {0}")]
    MemoryExceeded(String),

    #[error("Serialization error: {0}")]
    SerializationError(#[from] serde_json::Error),

    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),

    #[error("Unknown error: {0}")]
    Unknown(String),
}

pub type Result<T> = std::result::Result<T, Error>;
