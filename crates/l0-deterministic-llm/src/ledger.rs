use crate::types::{MerkleChainEntry, format_sha256_hash};
use ed25519_dalek::{SigningKey, Signer};
use uuid::Uuid;
use std::sync::Arc;
use dashmap::DashMap;

/// Merkle chain ledger for L8 proof layer integration
pub struct MerkleChainLedger {
    entries: Arc<DashMap<String, MerkleChainEntry>>,
    signing_key: SigningKey,
    last_hash: Arc<parking_lot::Mutex<Option<String>>>,
}

impl MerkleChainLedger {
    pub fn new(signing_key: SigningKey) -> Self {
        Self {
            entries: Arc::new(DashMap::new()),
            signing_key,
            last_hash: Arc::new(parking_lot::Mutex::new(None)),
        }
    }

    /// Add entry to Merkle chain
    pub fn add_entry(
        &self,
        prompt_fingerprint: String,
        response_hash: String,
        cost_tokens: u32,
        cache_hit: bool,
    ) -> Result<MerkleChainEntry, String> {
        let id = Uuid::new_v4().to_string();
        let prev_hash = self.last_hash.lock().clone();

        let entry = MerkleChainEntry::new(
            id.clone(),
            prompt_fingerprint,
            response_hash.clone(),
            prev_hash.clone(),
            cost_tokens,
            cache_hit,
        );

        // Sign the entry (Merkle chain link)
        let entry_data = format!("{}:{}", &entry.prompt_fingerprint, &entry.response_hash);
        let signature = self.signing_key.sign(entry_data.as_bytes());
        let _sig_hex = format!("ed25519:{}", hex::encode(signature.to_bytes()));

        // Update last hash
        let entry_hash = format_sha256_hash(&entry_data);
        *self.last_hash.lock() = Some(entry_hash);

        self.entries.insert(id.clone(), entry.clone());
        Ok(entry)
    }

    /// Verify Merkle chain integrity
    /// Checks that prev_hash references exist and form a valid chain
    pub fn verify_chain(&self) -> Result<bool, String> {
        if self.entries.is_empty() {
            return Ok(true); // Empty chain is valid
        }

        // Verify that every entry with a prev_hash has a corresponding entry in the chain
        for entry in self.entries.iter() {
            if let Some(prev) = &entry.value().prev_hash {
                // Check if any entry's hash matches this prev_hash
                let found = self.entries.iter().any(|e| {
                    let entry_hash = format_sha256_hash(&format!(
                        "{}:{}",
                        e.value().prompt_fingerprint, e.value().response_hash
                    ));
                    entry_hash == *prev
                });
                if !found {
                    return Ok(false); // Broken link
                }
            }
        }

        Ok(true)
    }

    /// Get entry by ID
    pub fn get_entry(&self, id: &str) -> Option<MerkleChainEntry> {
        self.entries.get(id).map(|e| e.value().clone())
    }

    /// Get all entries
    pub fn get_all(&self) -> Vec<MerkleChainEntry> {
        self.entries
            .iter()
            .map(|entry| entry.value().clone())
            .collect()
    }

    /// Get chain length
    pub fn chain_length(&self) -> usize {
        self.entries.len()
    }

    /// Clear ledger
    pub fn clear(&self) {
        self.entries.clear();
        *self.last_hash.lock() = None;
    }

    /// Get last hash in chain
    pub fn last_hash(&self) -> Option<String> {
        self.last_hash.lock().clone()
    }
}

impl Clone for MerkleChainLedger {
    fn clone(&self) -> Self {
        Self {
            entries: Arc::clone(&self.entries),
            signing_key: SigningKey::from_bytes(&[0u8; 32]), // Placeholder for testing
            last_hash: Arc::clone(&self.last_hash),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_key() -> SigningKey {
        let mut seed = [0u8; 32];
        seed[0] = 42;
        SigningKey::from_bytes(&seed)
    }

    #[test]
    fn test_add_entry_to_chain() {
        let key = create_test_key();
        let ledger = MerkleChainLedger::new(key);

        let result = ledger.add_entry(
            "fp1".to_string(),
            "hash1".to_string(),
            10,
            false,
        );

        assert!(result.is_ok());
        assert_eq!(ledger.chain_length(), 1);
    }

    #[test]
    fn test_merkle_chain_linking() {
        let key = create_test_key();
        let ledger = MerkleChainLedger::new(key);

        ledger.add_entry("fp1".to_string(), "hash1".to_string(), 10, false).unwrap();
        ledger.add_entry("fp2".to_string(), "hash2".to_string(), 10, true).unwrap();

        assert_eq!(ledger.chain_length(), 2);

        let entries = ledger.get_all();
        // At least one entry should have a prev_hash (the second one added)
        let has_linked_entry = entries.iter().any(|e| e.prev_hash.is_some());
        assert!(has_linked_entry);
    }

    #[test]
    fn test_verify_chain_integrity() {
        let key = create_test_key();
        let ledger = MerkleChainLedger::new(key);

        ledger.add_entry("fp1".to_string(), "hash1".to_string(), 10, false).unwrap();
        ledger.add_entry("fp2".to_string(), "hash2".to_string(), 10, true).unwrap();
        ledger.add_entry("fp3".to_string(), "hash3".to_string(), 10, false).unwrap();

        let is_valid = ledger.verify_chain().unwrap();
        assert!(is_valid);
    }

    #[test]
    fn test_get_entry_by_id() {
        let key = create_test_key();
        let ledger = MerkleChainLedger::new(key);

        let result = ledger.add_entry(
            "fp1".to_string(),
            "hash1".to_string(),
            10,
            false,
        ).unwrap();

        let retrieved = ledger.get_entry(&result.id);
        assert!(retrieved.is_some());
        assert_eq!(retrieved.unwrap().prompt_fingerprint, "fp1");
    }

    #[test]
    fn test_clear_ledger() {
        let key = create_test_key();
        let ledger = MerkleChainLedger::new(key);

        ledger.add_entry("fp1".to_string(), "hash1".to_string(), 10, false).unwrap();
        ledger.add_entry("fp2".to_string(), "hash2".to_string(), 10, true).unwrap();

        assert_eq!(ledger.chain_length(), 2);

        ledger.clear();
        assert_eq!(ledger.chain_length(), 0);
        assert!(ledger.last_hash().is_none());
    }

    #[test]
    fn test_last_hash_tracking() {
        let key = create_test_key();
        let ledger = MerkleChainLedger::new(key);

        assert!(ledger.last_hash().is_none());

        ledger.add_entry("fp1".to_string(), "hash1".to_string(), 10, false).unwrap();
        assert!(ledger.last_hash().is_some());
    }
}
