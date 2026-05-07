use ed25519_dalek::{Signer as DalekSigner, SigningKey, Verifier, VerifyingKey};
use super::{Signer, SigningError};

pub struct LocalEd25519Signer {
    signing_key: SigningKey,
    verifying_key: VerifyingKey,
}

impl LocalEd25519Signer {
    pub fn generate() -> Self {
        let signing_key = SigningKey::generate(&mut rand::thread_rng());
        let verifying_key = signing_key.verifying_key();
        Self { signing_key, verifying_key }
    }

    pub fn from_key_bytes(bytes: &[u8; 32]) -> Result<Self, SigningError> {
        let signing_key = SigningKey::from_bytes(bytes);
        let verifying_key = signing_key.verifying_key();
        Ok(Self { signing_key, verifying_key })
    }

    pub fn signing_key_bytes(&self) -> [u8; 32] {
        self.signing_key.to_bytes()
    }
}

impl Signer for LocalEd25519Signer {
    fn sign(&self, payload: &[u8]) -> Result<Vec<u8>, SigningError> {
        let signature = self.signing_key.sign(payload);
        Ok(signature.to_bytes().to_vec())
    }

    fn verify(&self, payload: &[u8], signature: &[u8]) -> Result<bool, SigningError> {
        if signature.len() != 64 {
            return Ok(false);
        }
        let sig_bytes: [u8; 64] = signature.try_into().map_err(|_| SigningError {
            message: "invalid signature length".into(),
        })?;
        let sig = ed25519_dalek::Signature::from_bytes(&sig_bytes);
        Ok(self.verifying_key.verify(payload, &sig).is_ok())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_local_signer_sign_and_verify() {
        let signer = LocalEd25519Signer::generate();
        let payload = b"test payload for signing";
        let signature = signer.sign(payload).unwrap();
        assert_eq!(signature.len(), 64);
        assert!(signer.verify(payload, &signature).unwrap());
    }

    #[test]
    fn test_local_signer_verify_rejects_tampered_payload() {
        let signer = LocalEd25519Signer::generate();
        let payload = b"original payload";
        let signature = signer.sign(payload).unwrap();
        assert!(!signer.verify(b"tampered payload", &signature).unwrap());
    }

    #[test]
    fn test_local_signer_verify_rejects_wrong_signature() {
        let signer = LocalEd25519Signer::generate();
        let payload = b"test payload";
        let wrong_sig = vec![0xFF; 64];
        assert!(!signer.verify(payload, &wrong_sig).unwrap());
    }

    #[test]
    fn test_from_bytes_roundtrip() {
        let signer = LocalEd25519Signer::generate();
        let key_bytes = signer.signing_key_bytes();
        let restored = LocalEd25519Signer::from_key_bytes(&key_bytes).unwrap();
        let payload = b"roundtrip test";
        let sig = signer.sign(payload).unwrap();
        assert!(restored.verify(payload, &sig).unwrap());
    }
}
