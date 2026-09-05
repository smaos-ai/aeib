use ed25519_dalek::{Signature, Signer, SigningKey, Verifier, VerifyingKey};
use sha2::{Digest, Sha256};
use thiserror::Error;

#[derive(Debug, Clone, Error)]
pub enum AttestationError {
    #[error("Invalid signature")]
    InvalidSignature,
    #[error("Invalid key bytes")]
    InvalidKeyBytes,
}

pub struct SovereignKeypair {
    signing_key: SigningKey,
}

impl SovereignKeypair {
    pub fn generate() -> Self {
        let mut random_bytes = [0u8; 32];
        use rand::RngCore;
        rand::thread_rng().fill_bytes(&mut random_bytes);
        let signing_key = SigningKey::from_bytes(&random_bytes);
        Self { signing_key }
    }

    pub fn from_bytes(bytes: &[u8; 32]) -> Result<Self, AttestationError> {
        let signing_key = SigningKey::from_bytes(bytes);
        Ok(Self { signing_key })
    }

    pub fn public_key_bytes(&self) -> [u8; 32] {
        self.signing_key.verifying_key().to_bytes()
    }

    pub fn sign(&self, message: &[u8]) -> [u8; 64] {
        let signature = self.signing_key.sign(message);
        signature.to_bytes()
    }
}

pub fn verify_signature(
    public_key_bytes: &[u8; 32],
    message: &[u8],
    signature_bytes: &[u8; 64],
) -> Result<(), AttestationError> {
    let verifying_key = VerifyingKey::from_bytes(public_key_bytes)
        .map_err(|_| AttestationError::InvalidKeyBytes)?;
    let signature = Signature::from_bytes(signature_bytes);
    verifying_key
        .verify(message, &signature)
        .map_err(|_| AttestationError::InvalidSignature)
}

pub fn sha256(data: &[u8]) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(data);
    let result = hasher.finalize();
    let mut hash = [0u8; 32];
    hash.copy_from_slice(&result);
    hash
}
