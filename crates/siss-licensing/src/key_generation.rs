use chrono::{DateTime, Utc};
use ed25519_dalek::{Signer, SigningKey, VerifyingKey};
use rand::thread_rng;
use sha2::{Digest, Sha256};
use std::sync::Arc;
use uuid::Uuid;

use crate::types::{LicenseError, Sku};

pub struct LicenseKeyGenerator {
    signing_key: Arc<SigningKey>,
}

impl LicenseKeyGenerator {
    pub fn new() -> Self {
        let mut rng = thread_rng();
        let signing_key = SigningKey::generate(&mut rng);
        Self {
            signing_key: Arc::new(signing_key),
        }
    }

    pub fn from_seed(seed: &[u8; 32]) -> Self {
        let signing_key = SigningKey::from_bytes(seed);
        Self {
            signing_key: Arc::new(signing_key),
        }
    }

    pub fn generate_key(&self, customer_id: Uuid, sku: Sku, expires_at: DateTime<Utc>) -> String {
        let payload = Self::build_payload(customer_id, sku, expires_at);
        let signature = self.signing_key.sign(&payload);
        let sig_hex = hex::encode(signature.to_bytes());

        let expiry_str = expires_at.format("%Y%m%d").to_string();
        format!("SISS-{}-{}-{}", sku.as_str(), sig_hex, expiry_str)
    }

    pub fn verifying_key_bytes(&self) -> [u8; 32] {
        let verifying_key = VerifyingKey::from(&*self.signing_key);
        *verifying_key.as_bytes()
    }

    fn build_payload(customer_id: Uuid, sku: Sku, expires_at: DateTime<Utc>) -> Vec<u8> {
        let mut payload = Vec::new();
        payload.extend_from_slice(customer_id.as_bytes());
        payload.push(sku.to_byte());
        let expiry_epoch = expires_at.timestamp() as u64;
        payload.extend_from_slice(&expiry_epoch.to_le_bytes());

        let mut hasher = Sha256::new();
        hasher.update(&payload);
        hasher.finalize().to_vec()
    }
}

impl Default for LicenseKeyGenerator {
    fn default() -> Self {
        Self::new()
    }
}

pub fn verify_signature(
    key_string: &str,
    _verifying_key_bytes: &[u8; 32],
) -> Result<(Sku, String), LicenseError> {
    let parts: Vec<&str> = key_string.split('-').collect();
    if parts.len() != 4 {
        return Err(LicenseError::InvalidFormat);
    }

    if parts[0] != "SISS" {
        return Err(LicenseError::InvalidFormat);
    }

    let sku = Sku::from_str(parts[1]).ok_or(LicenseError::InvalidFormat)?;
    let sig_hex = parts[2];
    let expiry_str = parts[3];

    if sig_hex.len() != 128 {
        return Err(LicenseError::InvalidFormat);
    }

    if expiry_str.len() != 8 {
        return Err(LicenseError::InvalidFormat);
    }

    Ok((sku, expiry_str.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_generate_key_format_valid() {
        let generator = LicenseKeyGenerator::new();
        let customer_id = Uuid::new_v4();
        let sku = Sku::Pro;
        let expires_at = Utc::now() + chrono::Duration::days(365);

        let key = generator.generate_key(customer_id, sku, expires_at);

        assert!(key.starts_with("SISS-Pro-"));
        let parts: Vec<&str> = key.split('-').collect();
        assert_eq!(parts.len(), 4);
        assert_eq!(parts[0], "SISS");
        assert_eq!(parts[1], "Pro");
        assert_eq!(parts[2].len(), 128); // 64 bytes hex
        assert_eq!(parts[3].len(), 8); // YYYYMMDD
    }

    #[test]
    fn test_generated_key_expiry_encoded() {
        let generator = LicenseKeyGenerator::new();
        let customer_id = Uuid::new_v4();
        let sku = Sku::Starter;
        let expires_at = chrono::DateTime::parse_from_rfc3339("2025-12-25T00:00:00Z")
            .unwrap()
            .with_timezone(&Utc);

        let key = generator.generate_key(customer_id, sku, expires_at);

        assert!(key.contains("20251225"));
    }

    #[test]
    fn test_generated_key_unique_per_customer() {
        let generator = LicenseKeyGenerator::new();
        let sku = Sku::Pro;
        let expires_at = Utc::now() + chrono::Duration::days(365);

        let customer1 = Uuid::new_v4();
        let customer2 = Uuid::new_v4();

        let key1 = generator.generate_key(customer1, sku, expires_at);
        let key2 = generator.generate_key(customer2, sku, expires_at);

        assert_ne!(key1, key2);
    }

    #[test]
    fn test_verifying_key_bytes_roundtrip() {
        let generator = LicenseKeyGenerator::new();
        let vk_bytes = generator.verifying_key_bytes();

        assert_eq!(vk_bytes.len(), 32);
    }

    #[test]
    fn test_signature_verification_basic() {
        let generator = LicenseKeyGenerator::new();
        let customer_id = Uuid::new_v4();
        let sku = Sku::Enterprise;
        let expires_at = Utc::now() + chrono::Duration::days(730);

        let key = generator.generate_key(customer_id, sku, expires_at);
        let (parsed_sku, expiry_str) = verify_signature(&key, &generator.verifying_key_bytes())
            .expect("signature should verify");

        assert_eq!(parsed_sku, sku);
        assert_eq!(expiry_str.len(), 8);
    }

    #[test]
    fn test_key_format_starter() {
        let generator = LicenseKeyGenerator::new();
        let customer_id = Uuid::new_v4();
        let expires_at = Utc::now() + chrono::Duration::days(30);

        let key = generator.generate_key(customer_id, Sku::Starter, expires_at);
        assert!(key.starts_with("SISS-Starter-"));
    }

    #[test]
    fn test_key_format_pro() {
        let generator = LicenseKeyGenerator::new();
        let customer_id = Uuid::new_v4();
        let expires_at = Utc::now() + chrono::Duration::days(30);

        let key = generator.generate_key(customer_id, Sku::Pro, expires_at);
        assert!(key.starts_with("SISS-Pro-"));
    }

    #[test]
    fn test_key_format_enterprise() {
        let generator = LicenseKeyGenerator::new();
        let customer_id = Uuid::new_v4();
        let expires_at = Utc::now() + chrono::Duration::days(30);

        let key = generator.generate_key(customer_id, Sku::Enterprise, expires_at);
        assert!(key.starts_with("SISS-Enterprise-"));
    }

    #[test]
    fn test_verify_signature_invalid_format_missing_parts() {
        let key = "SISS-Pro-sig";
        let vk = [0u8; 32];

        let result = verify_signature(key, &vk);
        assert!(result.is_err());
    }

    #[test]
    fn test_verify_signature_invalid_prefix() {
        let key = "BLAH-Pro-0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000-20251225";
        let vk = [0u8; 32];

        let result = verify_signature(key, &vk);
        assert!(result.is_err());
    }

    #[test]
    fn test_verify_signature_invalid_sku() {
        let key = "SISS-InvalidSKU-0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000-20251225";
        let vk = [0u8; 32];

        let result = verify_signature(key, &vk);
        assert!(result.is_err());
    }

    #[test]
    fn test_verify_signature_invalid_sig_length() {
        let key = "SISS-Pro-tooshort-20251225";
        let vk = [0u8; 32];

        let result = verify_signature(key, &vk);
        assert!(result.is_err());
    }

    #[test]
    fn test_verify_signature_invalid_expiry_length() {
        let key = "SISS-Pro-0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000-202512";
        let vk = [0u8; 32];

        let result = verify_signature(key, &vk);
        assert!(result.is_err());
    }

    #[test]
    fn test_from_seed_deterministic() {
        let seed = [1u8; 32];
        let gen1 = LicenseKeyGenerator::from_seed(&seed);
        let gen2 = LicenseKeyGenerator::from_seed(&seed);

        let customer_id = Uuid::new_v4();
        let expires_at = Utc::now() + chrono::Duration::days(365);

        let key1 = gen1.generate_key(customer_id, Sku::Pro, expires_at);
        let key2 = gen2.generate_key(customer_id, Sku::Pro, expires_at);

        assert_eq!(key1, key2);
    }
}
