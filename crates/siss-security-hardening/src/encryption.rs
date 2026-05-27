use aes_gcm::{
    aead::{Aead, KeyInit, Payload},
    Aes256Gcm, Nonce,
};
use serde::{Deserialize, Serialize};
use thiserror::Error;
use rand::Rng;

#[derive(Debug, Clone, Error)]
pub enum EncryptionError {
    #[error("Encryption failed: {0}")]
    EncryptionFailed(String),
    #[error("Decryption failed: {0}")]
    DecryptionFailed(String),
    #[error("Key derivation failed: {0}")]
    KeyDerivationFailed(String),
    #[error("Invalid key material")]
    InvalidKeyMaterial,
}

/// 256-bit AES key for capsule encryption
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EncryptionKey([u8; 32]);

impl EncryptionKey {
    pub fn as_bytes(&self) -> &[u8; 32] {
        &self.0
    }
}

/// Key manager for generating and managing encryption keys
pub struct KeyManager;

impl KeyManager {
    /// Generate a cryptographically secure 256-bit key
    pub fn generate_key() -> EncryptionKey {
        let mut rng = rand::thread_rng();
        let mut key_bytes = [0u8; 32];
        rng.fill(&mut key_bytes);
        EncryptionKey(key_bytes)
    }

    /// Derive a key from a master key using a customer namespace
    pub fn derive_key_for_customer(master_key: &EncryptionKey, customer_id: &str) -> EncryptionKey {
        use sha2::{Sha256, Digest};

        let mut hasher = Sha256::new();
        hasher.update(master_key.as_bytes());
        hasher.update(customer_id.as_bytes());

        let result = hasher.finalize();
        let mut key_bytes = [0u8; 32];
        key_bytes.copy_from_slice(&result[..32]);
        EncryptionKey(key_bytes)
    }
}

/// Encrypted payload with nonce and authentication tag
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EncryptedPayload {
    pub nonce: Vec<u8>,
    pub ciphertext: Vec<u8>,
    pub tag: Vec<u8>,
}

/// AES-256-GCM encryption/decryption for capsules
pub struct CapsuleEncryption {
    cipher: Aes256Gcm,
    key: EncryptionKey,
}

impl CapsuleEncryption {
    pub fn new(key: EncryptionKey) -> Self {
        let cipher = Aes256Gcm::new_from_slice(key.as_bytes())
            .expect("Key size mismatch");

        Self { cipher, key }
    }

    /// Encrypt plaintext and return ciphertext with nonce
    pub fn encrypt(&self, plaintext: &[u8]) -> Result<EncryptedPayload, EncryptionError> {
        let mut rng = rand::thread_rng();
        let mut nonce_bytes = [0u8; 12];
        rng.fill(&mut nonce_bytes);
        let nonce = Nonce::from_slice(&nonce_bytes);

        let payload = Payload {
            msg: plaintext,
            aad: b"",
        };

        match self.cipher.encrypt(nonce, payload) {
            Ok(ciphertext) => {
                Ok(EncryptedPayload {
                    nonce: nonce_bytes.to_vec(),
                    ciphertext: ciphertext.clone(),
                    tag: Vec::new(), // GCM tag is included in ciphertext
                })
            }
            Err(e) => Err(EncryptionError::EncryptionFailed(e.to_string())),
        }
    }

    /// Decrypt ciphertext using stored nonce
    pub fn decrypt(&self, encrypted: &EncryptedPayload) -> Result<Vec<u8>, EncryptionError> {
        if encrypted.nonce.len() != 12 {
            return Err(EncryptionError::DecryptionFailed("Invalid nonce length".to_string()));
        }

        let nonce = Nonce::from_slice(&encrypted.nonce);
        let payload = Payload {
            msg: encrypted.ciphertext.as_slice(),
            aad: b"",
        };

        match self.cipher.decrypt(nonce, payload) {
            Ok(plaintext) => Ok(plaintext),
            Err(e) => Err(EncryptionError::DecryptionFailed(e.to_string())),
        }
    }

    pub fn key(&self) -> &EncryptionKey {
        &self.key
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_key_generation() {
        let key1 = KeyManager::generate_key();
        let key2 = KeyManager::generate_key();

        // Keys should be different
        assert_ne!(key1.as_bytes(), key2.as_bytes());
    }

    #[test]
    fn test_key_derivation() {
        let master_key = KeyManager::generate_key();
        let customer_key_a = KeyManager::derive_key_for_customer(&master_key, "customer_a");
        let customer_key_b = KeyManager::derive_key_for_customer(&master_key, "customer_b");

        // Same customer should get same key
        let customer_key_a_again = KeyManager::derive_key_for_customer(&master_key, "customer_a");
        assert_eq!(customer_key_a.as_bytes(), customer_key_a_again.as_bytes());

        // Different customers should get different keys
        assert_ne!(customer_key_a.as_bytes(), customer_key_b.as_bytes());
    }

    #[test]
    fn test_encryption_produces_different_ciphertexts() {
        let key = KeyManager::generate_key();
        let cipher = CapsuleEncryption::new(key);
        let plaintext = b"same data";

        let encrypted1 = cipher.encrypt(plaintext).expect("First encrypt should succeed");
        let encrypted2 = cipher.encrypt(plaintext).expect("Second encrypt should succeed");

        // Due to random nonce, ciphertexts should be different
        assert_ne!(encrypted1.nonce, encrypted2.nonce);
        assert_ne!(encrypted1.ciphertext, encrypted2.ciphertext);
    }

    #[test]
    fn test_encryption_with_large_payload() {
        let key = KeyManager::generate_key();
        let cipher = CapsuleEncryption::new(key);

        let large_plaintext = vec![0xAB; 1_000_000]; // 1MB
        let encrypted = cipher.encrypt(&large_plaintext)
            .expect("Encrypt large payload should succeed");
        let decrypted = cipher.decrypt(&encrypted)
            .expect("Decrypt large payload should succeed");

        assert_eq!(large_plaintext, decrypted);
    }
}
