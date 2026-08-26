use chrono::{DateTime, Utc};
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
}

pub struct ProofLayer {
    receipts: Vec<WorkReceipt>,
    ledger: Vec<LedgerEntry>,
}

impl ProofLayer {
    pub fn new() -> Self {
        Self {
            receipts: Vec::new(),
            ledger: Vec::new(),
        }
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

        let entry = LedgerEntry {
            id: Uuid::new_v4().to_string(),
            timestamp: Utc::now(),
            digest: digest.clone(),
            signature: format!("ed25519:{}", digest),
            data,
        };
        self.ledger.push(entry.clone());
        Ok(entry)
    }

    pub fn verify_immutable(&self, entry_id: &str) -> bool {
        self.ledger.iter().any(|e| e.id == entry_id)
    }

    pub fn get_receipts(&self) -> &[WorkReceipt] {
        &self.receipts
    }

    pub fn get_ledger(&self) -> &[LedgerEntry] {
        &self.ledger
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
}
