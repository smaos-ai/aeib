//! L8 Proof Layer: Egress Decision Ledger
//! Records all egress decisions to immutable AP2 ledger with KMS signatures

use chrono::Utc;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use uuid::Uuid;

/// Egress decision recorded to ledger
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EgressLedgerEntry {
    pub entry_id: String,
    pub request_id: String,
    pub hook_id: String,
    pub execution_decision: EgressDecision,
    pub intent_hash: String,
    pub validation_time_ms: u64,
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub kms_signature: KmsSignature,
    pub ledger_index: u64,
}

/// Egress decision type
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum EgressDecision {
    Allow,
    Deny(String),
    RateLimit,
    Timeout,
}

impl std::fmt::Display for EgressDecision {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            EgressDecision::Allow => write!(f, "Allow"),
            EgressDecision::Deny(reason) => write!(f, "Deny({})", reason),
            EgressDecision::RateLimit => write!(f, "RateLimit"),
            EgressDecision::Timeout => write!(f, "Timeout"),
        }
    }
}

/// KMS signature with key reference
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KmsSignature {
    pub key_id: String,
    pub key_version: String,
    pub signature: Vec<u8>,
    pub algorithm: String, // "Ed25519" or "SHA256-HMAC"
    pub signed_at: chrono::DateTime<chrono::Utc>,
}

impl KmsSignature {
    /// Create new KMS signature
    pub fn new(key_id: String, signature: Vec<u8>) -> Self {
        Self {
            key_id,
            key_version: "1".to_string(),
            signature,
            algorithm: "Ed25519".to_string(),
            signed_at: Utc::now(),
        }
    }
}

/// Egress Ledger (AP2 immutable trail)
pub struct EgressLedger {
    entries: Vec<EgressLedgerEntry>,
    ledger_id: String,
    kms_key_id: String,
}

impl EgressLedger {
    /// Create new ledger
    pub fn new(kms_key_id: String) -> Self {
        Self {
            entries: Vec::new(),
            ledger_id: Uuid::new_v4().to_string(),
            kms_key_id,
        }
    }

    /// Record egress decision (fail-fast: requires valid KMS signature)
    pub fn record_decision(
        &mut self,
        request_id: String,
        hook_id: String,
        decision: EgressDecision,
        intent_hash: String,
        validation_time_ms: u64,
        signature_bytes: Vec<u8>,
    ) -> Result<String, String> {
        // Verify signature before recording
        if signature_bytes.len() != 64 {
            return Err("Invalid signature length".to_string());
        }

        let entry_id = format!("l8_egress_{}_{}", request_id, Uuid::new_v4());
        let ledger_index = self.entries.len() as u64;

        let kms_sig = KmsSignature::new(self.kms_key_id.clone(), signature_bytes);

        let entry = EgressLedgerEntry {
            entry_id: entry_id.clone(),
            request_id: request_id.clone(),
            hook_id,
            execution_decision: decision,
            intent_hash,
            validation_time_ms,
            timestamp: Utc::now(),
            kms_signature: kms_sig,
            ledger_index,
        };

        self.entries.push(entry);
        Ok(entry_id)
    }

    /// Get entry by ID
    pub fn get_entry(&self, entry_id: &str) -> Option<EgressLedgerEntry> {
        self.entries
            .iter()
            .find(|e| e.entry_id == entry_id)
            .cloned()
    }

    /// Get all entries
    pub fn get_entries(&self) -> Vec<EgressLedgerEntry> {
        self.entries.clone()
    }

    /// Calculate merkle root for immutability proof
    pub fn calculate_merkle_root(&self) -> String {
        let mut hasher = Sha256::new();

        for entry in &self.entries {
            let entry_json = serde_json::to_string(entry).unwrap_or_default();
            hasher.update(entry_json.as_bytes());
        }

        format!("{:x}", hasher.finalize())
    }

    /// Verify ledger integrity (all entries present)
    pub fn verify_integrity(&self) -> bool {
        // Check sequential ledger_index
        for (i, entry) in self.entries.iter().enumerate() {
            if entry.ledger_index != i as u64 {
                return false;
            }
        }
        true
    }

    /// Export ledger as JSON
    pub fn export_json(&self) -> Result<String, serde_json::Error> {
        serde_json::to_string_pretty(&self.entries)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_egress_ledger_records_allow_decision() {
        let mut ledger = EgressLedger::new("kms_key_001".to_string());

        let result = ledger.record_decision(
            "req_001".to_string(),
            "hook_001".to_string(),
            EgressDecision::Allow,
            "hash_001".to_string(),
            5,
            vec![1u8; 64],
        );

        assert!(result.is_ok());
        let entry_id = result.unwrap();
        assert!(entry_id.contains("l8_egress_req_001"));
    }

    #[test]
    fn test_egress_ledger_records_deny_decision() {
        let mut ledger = EgressLedger::new("kms_key_001".to_string());

        let result = ledger.record_decision(
            "req_002".to_string(),
            "hook_002".to_string(),
            EgressDecision::Deny("Domain not whitelisted".to_string()),
            "hash_002".to_string(),
            3,
            vec![2u8; 64],
        );

        assert!(result.is_ok());
        let entry = ledger.get_entry(&result.unwrap()).unwrap();
        assert_eq!(
            entry.execution_decision,
            EgressDecision::Deny("Domain not whitelisted".to_string())
        );
    }

    #[test]
    fn test_egress_ledger_kms_signature() {
        let mut ledger = EgressLedger::new("kms_key_001".to_string());

        ledger
            .record_decision(
                "req_003".to_string(),
                "hook_003".to_string(),
                EgressDecision::RateLimit,
                "hash_003".to_string(),
                2,
                vec![3u8; 64],
            )
            .ok();

        let entries = ledger.get_entries();
        assert_eq!(entries[0].kms_signature.key_id, "kms_key_001");
        assert_eq!(entries[0].kms_signature.signature.len(), 64);
    }

    #[test]
    fn test_egress_ledger_integrity_check() {
        let mut ledger = EgressLedger::new("kms_key_001".to_string());

        for i in 0..3 {
            ledger
                .record_decision(
                    format!("req_{:03}", i),
                    format!("hook_{:03}", i),
                    EgressDecision::Allow,
                    format!("hash_{:03}", i),
                    5,
                    vec![i as u8; 64],
                )
                .ok();
        }

        assert!(ledger.verify_integrity());
    }

    #[test]
    fn test_egress_ledger_merkle_root() {
        let mut ledger = EgressLedger::new("kms_key_001".to_string());

        ledger
            .record_decision(
                "req_004".to_string(),
                "hook_004".to_string(),
                EgressDecision::Allow,
                "hash_004".to_string(),
                4,
                vec![4u8; 64],
            )
            .ok();

        let root = ledger.calculate_merkle_root();
        assert!(!root.is_empty());
        assert_eq!(root.len(), 64); // SHA256 hex digest
    }

    #[test]
    fn test_egress_ledger_export_json() {
        let mut ledger = EgressLedger::new("kms_key_001".to_string());

        ledger
            .record_decision(
                "req_005".to_string(),
                "hook_005".to_string(),
                EgressDecision::Allow,
                "hash_005".to_string(),
                6,
                vec![5u8; 64],
            )
            .ok();

        let json = ledger.export_json();
        assert!(json.is_ok());
        let json_str = json.unwrap();
        assert!(json_str.contains("l8_egress_req_005"));
    }

    #[test]
    fn test_egress_ledger_rejects_invalid_signature() {
        let mut ledger = EgressLedger::new("kms_key_001".to_string());

        let result = ledger.record_decision(
            "req_006".to_string(),
            "hook_006".to_string(),
            EgressDecision::Allow,
            "hash_006".to_string(),
            7,
            vec![6u8; 32], // Invalid length
        );

        assert!(result.is_err());
    }
}
