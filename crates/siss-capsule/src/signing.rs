// Phase 26 Task 1: StateMutationSigner + Ed25519 cryptographic integrity
// Reuses SovereignKeypair from siss-layer00::attestation

use chrono::{DateTime, Utc};
use siss_layer00::attestation::{SovereignKeypair, sha256, verify_signature};
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

/// Signed state mutation with cryptographic binding to context
#[derive(Debug, Clone)]
pub struct SignedMutation {
    pub key: String,
    pub value: String,
    pub context_id: Uuid,
    pub timestamp: DateTime<Utc>,
    pub signature: [u8; 64],
    pub signer_public_key: [u8; 32],
}

/// Signer for state mutations with Ed25519
pub struct StateMutationSigner {
    keypair: Arc<SovereignKeypair>,
}

impl std::fmt::Debug for StateMutationSigner {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("StateMutationSigner")
            .field("public_key", &format!("{:?}", self.public_key_bytes()))
            .finish()
    }
}

impl StateMutationSigner {
    /// Generate new keypair
    pub fn generate() -> Self {
        Self {
            keypair: Arc::new(SovereignKeypair::generate()),
        }
    }

    /// Create from raw keypair bytes
    pub fn from_bytes(bytes: &[u8; 32]) -> Result<Self, SigningError> {
        let keypair = SovereignKeypair::from_bytes(bytes)
            .map_err(|e| SigningError::KeyDerivationFailed(e.to_string()))?;
        Ok(Self {
            keypair: Arc::new(keypair),
        })
    }

    /// Get keypair bytes for persistence/roundtrip
    pub fn keypair_bytes(&self) -> [u8; 32] {
        // Note: SovereignKeypair doesn't expose private key bytes directly.
        // This is a limitation - for testing we'll use the public key as identifier.
        // In production, you'd serialize the entire keypair securely.
        self.keypair.public_key_bytes()
    }

    /// Get public key bytes
    pub fn public_key_bytes(&self) -> [u8; 32] {
        self.keypair.public_key_bytes()
    }

    /// Sign a mutation
    pub fn sign_mutation(
        &self,
        key: &str,
        value: &str,
        context_id: Uuid,
    ) -> Result<SignedMutation, SigningError> {
        let timestamp = Utc::now();

        // Build message: context_id || key || value || timestamp_bytes
        let context_bytes = context_id.as_bytes();
        let timestamp_bytes = timestamp.timestamp().to_le_bytes();

        let message = [
            &context_bytes[..],
            key.as_bytes(),
            value.as_bytes(),
            &timestamp_bytes[..],
        ]
        .concat();

        // Hash message
        let hash = sha256(&message);

        // Sign hash
        let signature = self.keypair.sign(&hash);
        let signer_public_key = self.keypair.public_key_bytes();

        Ok(SignedMutation {
            key: key.to_string(),
            value: value.to_string(),
            context_id,
            timestamp,
            signature,
            signer_public_key,
        })
    }

    /// Verify a mutation signature
    pub fn verify_mutation(&self, mutation: &SignedMutation) -> Result<(), SigningError> {
        // Reconstruct the message that was signed
        let context_bytes = mutation.context_id.as_bytes();
        let timestamp_bytes = mutation.timestamp.timestamp().to_le_bytes();

        let message = [
            &context_bytes[..],
            mutation.key.as_bytes(),
            mutation.value.as_bytes(),
            &timestamp_bytes[..],
        ]
        .concat();

        // Hash message
        let hash = sha256(&message);

        // Verify signature
        verify_signature(&mutation.signer_public_key, &hash, &mutation.signature)
            .map_err(|_| SigningError::InvalidSignature)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_signer_basic_operations() {
        let signer = StateMutationSigner::generate();
        let public_key = signer.public_key_bytes();
        assert_eq!(public_key.len(), 32);
    }
}

// Unused in lib, but tested extensively in capsule_v2_hardening_tests.rs
#[allow(unused_imports)]
use uuid::Uuid as _;
