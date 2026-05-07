pub mod local;
pub mod mock;

use thiserror::Error;

#[derive(Debug, Error)]
#[error("signing error: {message}")]
pub struct SigningError {
    pub message: String,
}

/// Trait for cryptographic signing of PaymentMandate payloads.
pub trait Signer: Send + Sync {
    fn sign(&self, payload: &[u8]) -> Result<Vec<u8>, SigningError>;
    fn verify(&self, payload: &[u8], signature: &[u8]) -> Result<bool, SigningError>;
}
