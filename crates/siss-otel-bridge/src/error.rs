use thiserror::Error;

#[derive(Error, Debug)]
pub enum OtelError {
    #[error("Invalid config: {0}")]
    InvalidConfig(String),
    #[error("Trace context error: {0}")]
    TraceError(String),
    #[error("SLA violation: {0}")]
    SLAViolation(String),
    #[error("Serialization error: {0}")]
    SerializationError(String),
}

pub type Result<T> = std::result::Result<T, OtelError>;
