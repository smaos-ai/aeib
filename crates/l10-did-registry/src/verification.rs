use crate::did::{DID, DidDocument};
use crate::error::DidError;
use sha2::{Digest, Sha256};

pub struct DidVerifier;

impl DidVerifier {
    pub fn verify_signature(
        did_doc: &DidDocument,
        message: &[u8],
        signature_hex: &str,
    ) -> Result<bool, DidError> {
        if did_doc.public_keys.is_empty() {
            return Err(DidError::VerificationFailed("No public keys available".to_string()));
        }

        for key in &did_doc.public_keys {
            if key.key_type == "Ed25519VerificationKey2020" {
                let sig_bytes = hex::decode(signature_hex)
                    .map_err(|e| DidError::InvalidSignature(e.to_string()))?;

                let pub_key_bytes = hex::decode(&key.public_key_hex)
                    .map_err(|e| DidError::InvalidSignature(e.to_string()))?;

                if Self::ed25519_verify(&pub_key_bytes, message, &sig_bytes) {
                    return Ok(true);
                }
            }
        }

        Ok(false)
    }

    pub fn verify_did_proof(did_doc: &DidDocument) -> Result<bool, DidError> {
        if let Some(proof) = &did_doc.proof {
            let mut hasher = Sha256::new();
            hasher.update(format!("{:?}", did_doc.id).as_bytes());
            hasher.update(did_doc.created_at.to_rfc3339().as_bytes());

            let hash = hex::encode(hasher.finalize());
            Ok(proof == &hash)
        } else {
            Err(DidError::VerificationFailed("No proof attached".to_string()))
        }
    }

    fn ed25519_verify(pub_key: &[u8], message: &[u8], signature: &[u8]) -> bool {
        if pub_key.len() != 32 || signature.len() != 64 {
            return false;
        }

        use ed25519_dalek::{Signature, VerifyingKey};

        match VerifyingKey::from_bytes(
            pub_key
                .try_into()
                .unwrap_or(&[0u8; 32]),
        ) {
            Ok(vkey) => {
                let sig = Signature::from_bytes(
                    signature
                        .try_into()
                        .unwrap_or(&[0u8; 64]),
                );
                vkey.verify_strict(message, &sig).is_ok()
            }
            Err(_) => false,
        }
    }

    pub fn compute_did_hash(did: &DID) -> String {
        let mut hasher = Sha256::new();
        hasher.update(did.to_string().as_bytes());
        hex::encode(hasher.finalize())
    }
}
