//! L8 Proof Layer: Local KMS Vault for Ed25519 Key Management
//! Provides secure key generation, signing, and verification with operation audit trail

use chrono::Utc;
use ed25519_dalek::{Signer, SigningKey, Verifier, VerifyingKey};
use rand::RngCore;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

/// KMS key metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KmsKey {
    pub key_id: String,
    pub algorithm: String,
    pub created_at: chrono::DateTime<chrono::Utc>,
}

/// KMS operation audit entry
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KmsOperation {
    pub id: String,
    pub key_id: String,
    pub operation: String,
    pub success: bool,
    pub timestamp: chrono::DateTime<chrono::Utc>,
}

/// Local KMS Vault for Ed25519 key management
pub struct KmsVault {
    keys: HashMap<String, (SigningKey, VerifyingKey, chrono::DateTime<chrono::Utc>)>,
    operations: Vec<KmsOperation>,
}

impl KmsVault {
    /// Create new KMS vault
    pub fn new() -> Self {
        Self {
            keys: HashMap::new(),
            operations: Vec::new(),
        }
    }

    /// Generate new Ed25519 key pair
    pub async fn generate_key(&mut self) -> Result<KmsKey, String> {
        let mut seed = [0u8; 32];
        rand::thread_rng().fill_bytes(&mut seed);

        let signing_key = SigningKey::from_bytes(&seed);
        let verifying_key = signing_key.verifying_key();

        let key_id = Uuid::new_v4().to_string();
        let created_at = Utc::now();

        self.keys
            .insert(key_id.clone(), (signing_key, verifying_key, created_at));

        // Log operation
        self.operations.push(KmsOperation {
            id: Uuid::new_v4().to_string(),
            key_id: key_id.clone(),
            operation: "generate".to_string(),
            success: true,
            timestamp: Utc::now(),
        });

        Ok(KmsKey {
            key_id,
            algorithm: "Ed25519".to_string(),
            created_at,
        })
    }

    /// Sign data with specified key
    pub async fn sign_data(&mut self, key_id: &str, data: &[u8]) -> Result<Vec<u8>, String> {
        let key_tuple = self
            .keys
            .get(key_id)
            .ok_or_else(|| format!("Key not found: {}", key_id))?;

        let signing_key = &key_tuple.0;
        let signature = signing_key.sign(data);

        // Log operation
        self.operations.push(KmsOperation {
            id: Uuid::new_v4().to_string(),
            key_id: key_id.to_string(),
            operation: "sign".to_string(),
            success: true,
            timestamp: Utc::now(),
        });

        Ok(signature.to_bytes().to_vec())
    }

    /// Verify signature with specified key
    pub async fn verify_signature(
        &mut self,
        key_id: &str,
        data: &[u8],
        signature: &[u8],
    ) -> Result<bool, String> {
        let key_tuple = self
            .keys
            .get(key_id)
            .ok_or_else(|| format!("Key not found: {}", key_id))?;

        let verifying_key = &key_tuple.1;

        // Convert signature bytes to fixed array
        let sig_array: [u8; 64] = signature
            .try_into()
            .map_err(|_| "Invalid signature length".to_string())?;

        let signature = ed25519_dalek::Signature::from_bytes(&sig_array);

        let verify_result = verifying_key.verify(data, &signature).is_ok();

        // Log operation
        self.operations.push(KmsOperation {
            id: Uuid::new_v4().to_string(),
            key_id: key_id.to_string(),
            operation: "verify".to_string(),
            success: verify_result,
            timestamp: Utc::now(),
        });

        Ok(verify_result)
    }

    /// Get KMS key metadata
    pub fn get_key(&self, key_id: &str) -> Option<KmsKey> {
        self.keys.get(key_id).map(|(_, _, created_at)| KmsKey {
            key_id: key_id.to_string(),
            algorithm: "Ed25519".to_string(),
            created_at: *created_at,
        })
    }

    /// Get all operations
    pub fn get_operations(&self) -> &[KmsOperation] {
        &self.operations
    }
}

impl Default for KmsVault {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_generate_ed25519_key() {
        let mut kms = KmsVault::new();
        let key = kms.generate_key().await.expect("Failed to generate key");

        assert_eq!(key.algorithm, "Ed25519");
        assert!(!key.key_id.is_empty());
        assert!(kms.get_key(&key.key_id).is_some());
    }

    #[tokio::test]
    async fn test_sign_and_verify() {
        let mut kms = KmsVault::new();
        let key = kms.generate_key().await.expect("Failed to generate key");
        let key_id = key.key_id.clone();

        let data = b"test data to sign";
        let signature = kms
            .sign_data(&key_id, data)
            .await
            .expect("Failed to sign data");

        let verify_result = kms
            .verify_signature(&key_id, data, &signature)
            .await
            .expect("Failed to verify signature");

        assert!(verify_result);
    }

    #[tokio::test]
    async fn test_signature_verification_fails_on_tampered_data() {
        let mut kms = KmsVault::new();
        let key = kms.generate_key().await.expect("Failed to generate key");
        let key_id = key.key_id.clone();

        let data = b"original data";
        let signature = kms
            .sign_data(&key_id, data)
            .await
            .expect("Failed to sign data");

        let tampered_data = b"tampered data";
        let verify_result = kms
            .verify_signature(&key_id, tampered_data, &signature)
            .await
            .expect("Failed to verify signature");

        assert!(!verify_result);
    }

    #[tokio::test]
    async fn test_multiple_keys_independent() {
        let mut kms = KmsVault::new();
        let key1 = kms.generate_key().await.expect("Failed to generate key1");
        let key2 = kms.generate_key().await.expect("Failed to generate key2");

        let key1_id = key1.key_id.clone();
        let key2_id = key2.key_id.clone();

        let data = b"test data";

        // Sign with key1
        let signature = kms
            .sign_data(&key1_id, data)
            .await
            .expect("Failed to sign with key1");

        // Verify with key2 should fail
        let verify_result = kms
            .verify_signature(&key2_id, data, &signature)
            .await
            .expect("Failed to verify with key2");

        assert!(!verify_result);
    }
}
