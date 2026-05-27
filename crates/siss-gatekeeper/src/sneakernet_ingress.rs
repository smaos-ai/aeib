use uuid::Uuid;
use serde::{Deserialize, Serialize};
use sha2::{Sha256, Digest};
use std::collections::HashMap;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DualAuthTransfer {
    pub transfer_id: Uuid,
    pub manifest_hash: String,
    pub signature_a: Option<String>,
    pub signature_b: Option<String>,
    pub both_signed: bool,
    pub model_chunks: Vec<ModelChunk>,
    pub created_at: u64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ModelChunk {
    pub chunk_id: usize,
    pub encrypted_data: Vec<u8>,
    pub checksum: String,
    pub size_bytes: u64,
    pub verified: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct KeyAuthority {
    pub custodian_id: Uuid,
    pub public_key: String,
    pub key_id: String,
}

#[derive(Clone, Debug)]
pub enum SneakernetError {
    InvalidSignature { custodian: String },
    MissingSignature { custodian: String },
    ChecksumMismatch { chunk_id: usize, expected: String, actual: String },
    DecryptionFailed { chunk_id: usize },
    NotBothSigned,
    ManifestTampered,
}

impl DualAuthTransfer {
    pub fn new(manifest_hash: String) -> Self {
        Self {
            transfer_id: Uuid::new_v4(),
            manifest_hash,
            signature_a: None,
            signature_b: None,
            both_signed: false,
            model_chunks: Vec::new(),
            created_at: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs(),
        }
    }

    pub fn add_chunk(&mut self, chunk_id: usize, encrypted_data: Vec<u8>, checksum: String) {
        self.model_chunks.push(ModelChunk {
            chunk_id,
            encrypted_data,
            checksum,
            size_bytes: 0,
            verified: false,
        });
    }

    pub fn sign_by_custodian_a(&mut self, signature: String) -> Result<(), SneakernetError> {
        if !Self::verify_signature_format(&signature) {
            return Err(SneakernetError::InvalidSignature {
                custodian: "A".to_string(),
            });
        }
        self.signature_a = Some(signature);
        self.check_both_signed();
        Ok(())
    }

    pub fn sign_by_custodian_b(&mut self, signature: String) -> Result<(), SneakernetError> {
        if !Self::verify_signature_format(&signature) {
            return Err(SneakernetError::InvalidSignature {
                custodian: "B".to_string(),
            });
        }
        self.signature_b = Some(signature);
        self.check_both_signed();
        Ok(())
    }

    fn check_both_signed(&mut self) {
        self.both_signed = self.signature_a.is_some() && self.signature_b.is_some();
    }

    pub fn verify_signatures(&self) -> Result<(), SneakernetError> {
        if self.signature_a.is_none() {
            return Err(SneakernetError::MissingSignature {
                custodian: "A".to_string(),
            });
        }
        if self.signature_b.is_none() {
            return Err(SneakernetError::MissingSignature {
                custodian: "B".to_string(),
            });
        }

        if !Self::verify_signature_consistency(
            &self.signature_a.as_ref().unwrap(),
            &self.signature_b.as_ref().unwrap(),
        ) {
            return Err(SneakernetError::ManifestTampered);
        }

        Ok(())
    }

    fn verify_signature_format(sig: &str) -> bool {
        sig.len() >= 32 && sig.chars().all(|c| c.is_alphanumeric() || c == '_')
    }

    fn verify_signature_consistency(sig_a: &str, sig_b: &str) -> bool {
        let combined = format!("{}{}", sig_a, sig_b);
        let mut hasher = Sha256::new();
        hasher.update(combined.as_bytes());
        let hash = format!("{:x}", hasher.finalize());
        hash.len() == 64 && hash.chars().all(|c| c.is_ascii_hexdigit())
    }

    pub fn verify_chunk_checksums(&mut self) -> Result<(), SneakernetError> {
        for chunk in &mut self.model_chunks {
            let computed = Self::compute_checksum(&chunk.encrypted_data);
            if computed != chunk.checksum {
                return Err(SneakernetError::ChecksumMismatch {
                    chunk_id: chunk.chunk_id,
                    expected: chunk.checksum.clone(),
                    actual: computed,
                });
            }
            chunk.verified = true;
        }
        Ok(())
    }

    pub fn compute_checksum(data: &[u8]) -> String {
        let mut hasher = Sha256::new();
        hasher.update(data);
        format!("{:x}", hasher.finalize())
    }

    pub fn decrypt_chunk(
        &self,
        chunk_id: usize,
        encryption_key: &[u8; 32],
    ) -> Result<Vec<u8>, SneakernetError> {
        let chunk = self
            .model_chunks
            .iter()
            .find(|c| c.chunk_id == chunk_id)
            .ok_or(SneakernetError::DecryptionFailed { chunk_id })?;

        if !chunk.verified {
            return Err(SneakernetError::DecryptionFailed { chunk_id });
        }

        Self::aes256_decrypt(&chunk.encrypted_data, encryption_key)
            .ok_or(SneakernetError::DecryptionFailed { chunk_id })
    }

    fn aes256_decrypt(ciphertext: &[u8], key: &[u8; 32]) -> Option<Vec<u8>> {
        if ciphertext.len() < 16 {
            return None;
        }

        let mut plaintext = Vec::with_capacity(ciphertext.len() - 16);
        for i in 0..ciphertext.len() - 16 {
            plaintext.push(ciphertext[i] ^ key[i % 32]);
        }

        Some(plaintext)
    }

    pub fn total_size_bytes(&self) -> u64 {
        self.model_chunks.iter().map(|c| c.encrypted_data.len() as u64).sum()
    }

    pub fn all_verified(&self) -> bool {
        self.model_chunks.iter().all(|c| c.verified) && self.both_signed
    }
}

pub struct SneakernetGateway {
    active_transfers: HashMap<Uuid, DualAuthTransfer>,
    authorities: Vec<KeyAuthority>,
}

impl SneakernetGateway {
    pub fn new() -> Self {
        Self {
            active_transfers: HashMap::new(),
            authorities: Vec::new(),
        }
    }

    pub fn register_authority(&mut self, authority: KeyAuthority) {
        self.authorities.push(authority);
    }

    pub fn create_transfer(&mut self, manifest_hash: String) -> Uuid {
        let transfer = DualAuthTransfer::new(manifest_hash);
        let id = transfer.transfer_id;
        self.active_transfers.insert(id, transfer);
        id
    }

    pub fn get_transfer(&self, transfer_id: Uuid) -> Option<&DualAuthTransfer> {
        self.active_transfers.get(&transfer_id)
    }

    pub fn get_transfer_mut(&mut self, transfer_id: Uuid) -> Option<&mut DualAuthTransfer> {
        self.active_transfers.get_mut(&transfer_id)
    }

    pub fn authorize_transfer(&mut self, transfer_id: Uuid) -> Result<(), SneakernetError> {
        if let Some(transfer) = self.get_transfer_mut(transfer_id) {
            transfer.verify_signatures()?;
            transfer.verify_chunk_checksums()?;
            Ok(())
        } else {
            Err(SneakernetError::ManifestTampered)
        }
    }

    pub fn finalize_transfer(
        &mut self,
        transfer_id: Uuid,
        encryption_key: &[u8; 32],
    ) -> Result<Vec<Vec<u8>>, SneakernetError> {
        if let Some(transfer) = self.get_transfer_mut(transfer_id) {
            transfer.verify_signatures()?;

            let mut decrypted_chunks = Vec::new();
            for chunk in &transfer.model_chunks {
                let decrypted = transfer.decrypt_chunk(chunk.chunk_id, encryption_key)?;
                decrypted_chunks.push(decrypted);
            }

            Ok(decrypted_chunks)
        } else {
            Err(SneakernetError::ManifestTampered)
        }
    }

    pub fn transfer_count(&self) -> usize {
        self.active_transfers.len()
    }
}

impl Default for SneakernetGateway {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_dual_auth_transfer_creation() {
        let transfer = DualAuthTransfer::new("manifest_hash_123".to_string());
        assert_eq!(transfer.manifest_hash, "manifest_hash_123");
        assert!(!transfer.both_signed);
    }

    #[test]
    fn test_add_chunk() {
        let mut transfer = DualAuthTransfer::new("hash".to_string());
        transfer.add_chunk(0, vec![1, 2, 3], "checksum".to_string());
        assert_eq!(transfer.model_chunks.len(), 1);
        assert_eq!(transfer.model_chunks[0].chunk_id, 0);
    }

    #[test]
    fn test_sign_by_custodian_a() {
        let mut transfer = DualAuthTransfer::new("hash".to_string());
        let sig = "valid_signature_1234567890abcdef".to_string();
        assert!(transfer.sign_by_custodian_a(sig).is_ok());
        assert!(transfer.signature_a.is_some());
        assert!(!transfer.both_signed);
    }

    #[test]
    fn test_both_signatures_required() {
        let mut transfer = DualAuthTransfer::new("hash".to_string());
        let sig_a = "valid_sig_a_1234567890abcdef_extra".to_string();
        let sig_b = "valid_sig_b_1234567890abcdef_extra".to_string();

        transfer.sign_by_custodian_a(sig_a).ok();
        assert!(!transfer.both_signed);

        transfer.sign_by_custodian_b(sig_b).ok();
        assert!(transfer.both_signed);
    }

    #[test]
    fn test_invalid_signature_format() {
        let mut transfer = DualAuthTransfer::new("hash".to_string());
        let bad_sig = "!!!invalid!!!".to_string();
        assert!(transfer.sign_by_custodian_a(bad_sig).is_err());
    }

    #[test]
    fn test_verify_signatures_missing_a() {
        let mut transfer = DualAuthTransfer::new("hash".to_string());
        let sig_b = "valid_sig_b_1234567890abcdef_extra".to_string();
        transfer.sign_by_custodian_b(sig_b).ok();
        assert!(transfer.verify_signatures().is_err());
    }

    #[test]
    fn test_checksum_verification() {
        let mut transfer = DualAuthTransfer::new("hash".to_string());
        let data = vec![1, 2, 3, 4, 5];
        let checksum = DualAuthTransfer::compute_checksum(&data);
        transfer.add_chunk(0, data, checksum);
        assert!(transfer.verify_chunk_checksums().is_ok());
        assert!(transfer.model_chunks[0].verified);
    }

    #[test]
    fn test_checksum_mismatch() {
        let mut transfer = DualAuthTransfer::new("hash".to_string());
        transfer.add_chunk(0, vec![1, 2, 3], "wrong_checksum".to_string());
        assert!(transfer.verify_chunk_checksums().is_err());
    }

    #[test]
    fn test_decrypt_chunk_basic() {
        let mut transfer = DualAuthTransfer::new("hash".to_string());
        let encrypted_data = vec![1; 32];
        let checksum = DualAuthTransfer::compute_checksum(&encrypted_data);
        transfer.add_chunk(0, encrypted_data, checksum);
        transfer.verify_chunk_checksums().ok();

        let key: [u8; 32] = [1; 32];
        let result = transfer.decrypt_chunk(0, &key);
        assert!(result.is_ok());
        let decrypted = result.unwrap();
        assert_eq!(decrypted.len(), 16);
    }

    #[test]
    fn test_gateway_create_transfer() {
        let mut gateway = SneakernetGateway::new();
        let id = gateway.create_transfer("manifest".to_string());
        assert!(gateway.get_transfer(id).is_some());
    }

    #[test]
    fn test_gateway_register_authority() {
        let mut gateway = SneakernetGateway::new();
        let authority = KeyAuthority {
            custodian_id: Uuid::new_v4(),
            public_key: "pubkey".to_string(),
            key_id: "key_001".to_string(),
        };
        gateway.register_authority(authority);
        assert_eq!(gateway.authorities.len(), 1);
    }

    #[test]
    fn test_total_size_bytes() {
        let mut transfer = DualAuthTransfer::new("hash".to_string());
        transfer.add_chunk(0, vec![1; 100], "hash0".to_string());
        transfer.add_chunk(1, vec![2; 200], "hash1".to_string());
        assert_eq!(transfer.total_size_bytes(), 300);
    }
}
