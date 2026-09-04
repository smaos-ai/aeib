use thiserror::Error;

#[derive(Error, Debug)]
pub enum DidError {
    #[error("Invalid DID format: {0}")]
    InvalidFormat(String),

    #[error("DID not found: {0}")]
    NotFound(String),

    #[error("Verification failed: {0}")]
    VerificationFailed(String),

    #[error("Invalid signature: {0}")]
    InvalidSignature(String),

    #[error("Tenant not found: {0}")]
    TenantNotFound(String),

    #[error("Authorization failed")]
    Unauthorized,

    #[error("Registry error: {0}")]
    RegistryError(String),

    #[error("Serialization error: {0}")]
    SerializationError(#[from] serde_json::Error),

    #[error("Cryptographic error: {0}")]
    CryptoError(String),
}
