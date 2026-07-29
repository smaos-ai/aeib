use thiserror::Error;
use siss_layer00::GateError;

#[derive(Debug, Clone, Error)]
pub enum LocalLLMError {
    #[error("Model load failed: {0}")]
    ModelLoadFailed(String),

    #[error("Inference failed: {0}")]
    InferenceFailed(String),

    #[error("Token validation failed: {0}")]
    TokenValidationFailed(String),

    #[error("Capability token expired")]
    TokenExpired,

    #[error("Action scope not allowed: {0}")]
    ActionScopeNotAllowed(String),

    #[error("Audit log failure: {0}")]
    AuditLogFailure(String),

    #[error("Model not found: {0}")]
    ModelNotFound(String),

    #[error("Invalid mandate: {0}")]
    InvalidMandate(String),

    #[error("Cache error: {0}")]
    CacheError(String),

    #[error("Serialization error: {0}")]
    SerializationError(String),
}

impl From<GateError> for LocalLLMError {
    fn from(e: GateError) -> Self {
        match e {
            GateError::MandateExpired => LocalLLMError::TokenExpired,
            GateError::InvalidSignature => LocalLLMError::TokenValidationFailed("Invalid signature".to_string()),
            GateError::CapabilityDenied(msg) => LocalLLMError::ActionScopeNotAllowed(msg),
            GateError::AuditLogFailure(msg) => LocalLLMError::AuditLogFailure(msg),
            _ => LocalLLMError::TokenValidationFailed(e.to_string()),
        }
    }
}

pub type LocalLLMResult<T> = Result<T, LocalLLMError>;
