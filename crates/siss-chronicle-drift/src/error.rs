use thiserror::Error;

#[derive(Error, Debug)]
pub enum DriftError {
    #[error("Invalid config: {0}")]
    InvalidConfig(String),
    #[error("Window error: {0}")]
    WindowError(String),
    #[error("Scoring error: {0}")]
    ScoringError(String),
    #[error("No decisions in window")]
    EmptyWindow,
}

pub type Result<T> = std::result::Result<T, DriftError>;
