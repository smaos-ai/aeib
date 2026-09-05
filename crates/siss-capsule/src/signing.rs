// Stub implementation for signing module
use chrono::{DateTime, Utc};
use std::sync::Arc;
use thiserror::Error;
use uuid::Uuid;

#[derive(Debug, Clone, Error)]
pub enum SigningError {
    #[error("Invalid signature")]
    InvalidSignature,
    #[error("Key derivation failed: {0}")]
    KeyDerivationFailed(String),
}

#[derive(Debug, Clone)]
pub struct SignedMutation {
    pub key: String,
    pub value: String,
    pub context_id: Uuid,
    pub timestamp: DateTime<Utc>,
    pub signature: [u8; 64],
    pub signer_public_key: [u8; 32],
}

pub struct StateMutationSigner {
    _dummy: Arc<[u8; 32]>,
}

impl std::fmt::Debug for StateMutationSigner {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("StateMutationSigner").finish()
    }
}

impl StateMutationSigner {
    pub fn generate() -> Self {
        Self {
            _dummy: Arc::new([0u8; 32]),
        }
    }

    pub fn public_key_bytes(&self) -> [u8; 32] {
        [0u8; 32]
    }

    pub fn sign_mutation(
        &self,
        key: &str,
        value: &str,
        context_id: Uuid,
    ) -> Result<SignedMutation, SigningError> {
        Ok(SignedMutation {
            key: key.to_string(),
            value: value.to_string(),
            context_id,
            timestamp: Utc::now(),
            signature: [0u8; 64],
            signer_public_key: [0u8; 32],
        })
    }
}
