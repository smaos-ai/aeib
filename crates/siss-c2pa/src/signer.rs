use ed25519_dalek::{Signer, SigningKey, VerifyingKey};

/// Wraps SMAOS Ed25519 key for C2PA manifest signing.
/// Manages Ed25519 signatures for research result provenance.
pub struct Ed25519C2PASigner {
    signing_key: SigningKey,
    verifying_key: VerifyingKey,
}

impl Ed25519C2PASigner {
    pub fn new(signing_key: SigningKey) -> Self {
        let verifying_key = signing_key.verifying_key();
        Self {
            signing_key,
            verifying_key,
        }
    }

    pub fn public_key_hex(&self) -> String {
        hex::encode(self.verifying_key.as_bytes())
    }

    /// Sign arbitrary data using the stored Ed25519 key.
    pub fn sign(&self, data: &[u8]) -> Vec<u8> {
        let signature = self.signing_key.sign(data);
        signature.to_bytes().to_vec()
    }
}
