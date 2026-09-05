//! Error types for cost optimizer

use thiserror::Error;

#[derive(Error, Debug)]
pub enum Error {
    #[error("Cost tracking error: {0}")]
    CostTrackingError(String),

    #[error("Allocation error: {0}")]
    AllocationError(String),

    #[error("Budget error: {0}")]
    BudgetError(String),

    #[error("Prediction error: {0}")]
    PredictionError(String),

    #[error("Agent not found: {0}")]
    AgentNotFound(String),

    #[error("Budget exceeded: {0}")]
    BudgetExceeded(String),

    #[error("Invalid configuration: {0}")]
    InvalidConfig(String),

    #[error("Serialization error: {0}")]
    SerializationError(#[from] serde_json::Error),

    #[error("Unknown error: {0}")]
    Unknown(String),
}

pub type Result<T> = std::result::Result<T, Error>;
