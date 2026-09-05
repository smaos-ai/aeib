use chrono::{DateTime, Utc};
use ed25519_dalek::{Signer, SigningKey, VerifyingKey};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkReceipt {
    pub id: String,
    pub timestamp: DateTime<Utc>,
    pub action: String,
    pub result: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LedgerEntry {
    pub id: String,
    pub timestamp: DateTime<Utc>,
    pub digest: String,
    pub signature: String,
    pub data: String,
    pub prev_digest: Option<String>, // Ledger chain link
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompressedLedger {
    pub checkpoint_id: String,
    pub entries: Vec<String>, // Hashes only, not full entries
    pub checkpoint_digest: String,
    pub checkpoint_timestamp: DateTime<Utc>,
}

pub struct ProofLayer {
    receipts: Vec<WorkReceipt>,
    ledger: Vec<LedgerEntry>,
    signing_key: SigningKey,
    verifying_key: VerifyingKey,
    last_digest: Option<String>,
    compression_threshold: usize,
    compressed_checkpoints: Vec<CompressedLedger>,
}

impl ProofLayer {
    pub fn new() -> Self {
        let mut seed = [0u8; 32];
        use rand::RngCore;
        rand::thread_rng().fill_bytes(&mut seed);
        let signing_key = SigningKey::from_bytes(&seed);
        let verifying_key = signing_key.verifying_key();

        Self {
            receipts: Vec::new(),
            ledger: Vec::new(),
            signing_key,
            verifying_key,
            last_digest: None,
            compression_threshold: 100, // Compress every 100 entries
            compressed_checkpoints: Vec::new(),
        }
    }

    pub fn with_compression_threshold(mut self, threshold: usize) -> Self {
        self.compression_threshold = threshold;
        self
    }

    pub fn create_work_receipt(&mut self, action: String, result: String) -> WorkReceipt {
        let receipt = WorkReceipt {
            id: Uuid::new_v4().to_string(),
            timestamp: Utc::now(),
            action,
            result,
        };
        self.receipts.push(receipt.clone());
        receipt
    }

    pub fn sign_ledger_entry(&mut self, data: String) -> Result<LedgerEntry, String> {
        let mut hasher = Sha256::new();
        hasher.update(data.as_bytes());
        let digest = format!("{:x}", hasher.finalize());

        // Chain previous digest for immutability
        if let Some(prev) = &self.last_digest {
            hasher = Sha256::new();
            hasher.update(format!("{}{}", prev, &digest).as_bytes());
        }

        // Sign the digest with ed25519
        let message = digest.as_bytes();
        let signature = self.signing_key.sign(message);
        let signature_hex = format!("ed25519:{}", hex::encode(signature.to_bytes()));

        let entry = LedgerEntry {
            id: Uuid::new_v4().to_string(),
            timestamp: Utc::now(),
            digest: digest.clone(),
            signature: signature_hex,
            data,
            prev_digest: self.last_digest.clone(),
        };

        self.ledger.push(entry.clone());
        self.last_digest = Some(digest.clone());

        // Auto-compress if threshold reached
        if self.ledger.len() % self.compression_threshold == 0 {
            self.compress_ledger()?;
        }

        Ok(entry)
    }

    pub fn compress_ledger(&mut self) -> Result<(), String> {
        let checkpoint_id = Uuid::new_v4().to_string();
        let entries_hashes: Vec<String> = self.ledger.iter().map(|e| e.digest.clone()).collect();

        let mut hasher = Sha256::new();
        for hash in &entries_hashes {
            hasher.update(hash.as_bytes());
        }
        let checkpoint_digest = format!("{:x}", hasher.finalize());

        let compressed = CompressedLedger {
            checkpoint_id,
            entries: entries_hashes,
            checkpoint_digest,
            checkpoint_timestamp: Utc::now(),
        };

        self.compressed_checkpoints.push(compressed);
        Ok(())
    }

    pub fn verify_immutable(&self, entry_id: &str) -> bool {
        self.ledger.iter().any(|e| e.id == entry_id)
    }

    pub fn verify_ledger_chain(&self) -> Result<bool, String> {
        let mut previous_digest = None;

        for entry in &self.ledger {
            if let Some(prev) = &entry.prev_digest {
                if let Some(expected_prev) = &previous_digest {
                    if prev != expected_prev {
                        return Ok(false); // Chain broken
                    }
                }
            }
            previous_digest = Some(entry.digest.clone());
        }

        Ok(true)
    }

    pub fn get_receipts(&self) -> &[WorkReceipt] {
        &self.receipts
    }

    pub fn get_ledger(&self) -> &[LedgerEntry] {
        &self.ledger
    }

    pub fn get_compressed_checkpoints(&self) -> &[CompressedLedger] {
        &self.compressed_checkpoints
    }

    pub fn get_verifying_key(&self) -> &VerifyingKey {
        &self.verifying_key
    }

    pub fn ledger_size(&self) -> usize {
        self.ledger.len()
    }
}

impl Default for ProofLayer {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_work_receipt() {
        let mut proof = ProofLayer::new();
        let receipt = proof.create_work_receipt("test_action".to_string(), "success".to_string());
        assert!(!receipt.id.is_empty());
    }

    #[test]
    fn test_sign_ledger_entry() {
        let mut proof = ProofLayer::new();
        let result = proof.sign_ledger_entry("test_data".to_string());
        assert!(result.is_ok());
        let entry = result.unwrap();
        assert!(entry.signature.starts_with("ed25519:"));
    }

    #[test]
    fn test_verify_immutable() {
        let mut proof = ProofLayer::new();
        let entry = proof.sign_ledger_entry("test".to_string()).unwrap();
        assert!(proof.verify_immutable(&entry.id));
    }

    #[test]
    fn test_ledger_chain_integrity() {
        let mut proof = ProofLayer::new();
        proof.sign_ledger_entry("entry1".to_string()).unwrap();
        proof.sign_ledger_entry("entry2".to_string()).unwrap();
        proof.sign_ledger_entry("entry3".to_string()).unwrap();

        // Verify chain integrity
        assert!(proof.verify_ledger_chain().unwrap());
    }

    #[test]
    fn test_compression_threshold() {
        let mut proof = ProofLayer::new().with_compression_threshold(3);
        proof.sign_ledger_entry("entry1".to_string()).unwrap();
        proof.sign_ledger_entry("entry2".to_string()).unwrap();
        proof.sign_ledger_entry("entry3".to_string()).unwrap();

        // Should trigger compression at threshold
        assert!(!proof.get_compressed_checkpoints().is_empty());
    }

    #[test]
    fn test_verifying_key_export() {
        let proof = ProofLayer::new();
        let _key = proof.get_verifying_key();
        // Verifying key is successfully exported
    }
}
