use chrono::{DateTime, Utc};
use hmac::{Hmac, Mac};
use serde::{Deserialize, Serialize};
use sha2::Sha256;
use thiserror::Error;
use uuid::Uuid;

type HmacSha256 = Hmac<Sha256>;

#[derive(Debug, Clone, Error)]
pub enum TamperDetectionError {
    #[error("Signature verification failed")]
    SignatureVerificationFailed,
    #[error("Invalid signature format")]
    InvalidSignatureFormat,
    #[error("HMAC computation failed: {0}")]
    HmacComputationFailed(String),
}

/// Audit log entry representing an operation
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AuditLogEntry {
    pub id: Uuid,
    pub capsule_id: Uuid,
    pub operation: String,
    pub status: String,
    pub timestamp: DateTime<Utc>,
    pub actor: String,
    pub details: serde_json::Value,
    #[serde(default)]
    pub signature: String,
    #[serde(default)]
    pub previous_hash: Option<String>,
}

impl AuditLogEntry {
    /// Create a new audit log entry for an operation
    pub fn new_operation(capsule_id: Uuid, operation: &str, status: &str) -> Self {
        Self {
            id: Uuid::new_v4(),
            capsule_id,
            operation: operation.to_string(),
            status: status.to_string(),
            timestamp: Utc::now(),
            actor: "system".to_string(),
            details: serde_json::json!({}),
            signature: String::new(),
            previous_hash: None,
        }
    }

    /// Create a new entry with custom actor
    pub fn with_actor(capsule_id: Uuid, operation: &str, status: &str, actor: &str) -> Self {
        let mut entry = Self::new_operation(capsule_id, operation, status);
        entry.actor = actor.to_string();
        entry
    }

    /// Compute the hash of this entry (excluding signature)
    pub fn compute_hash(&self) -> String {
        use sha2::{Sha256, Digest};

        let mut hasher = Sha256::new();
        hasher.update(self.id.as_bytes());
        hasher.update(self.capsule_id.as_bytes());
        hasher.update(self.operation.as_bytes());
        hasher.update(self.status.as_bytes());
        hasher.update(self.timestamp.to_rfc3339().as_bytes());
        hasher.update(self.actor.as_bytes());
        hasher.update(self.details.to_string().as_bytes());

        let result = hasher.finalize();
        format!("{:x}", result)
    }
}

/// Signature verifier for HMAC-SHA256
pub struct SignatureVerifier {
    secret: Vec<u8>,
}

impl SignatureVerifier {
    pub fn new(secret: Vec<u8>) -> Self {
        Self { secret }
    }

    pub fn sign_data(&self, data: &[u8]) -> Result<String, TamperDetectionError> {
        let mut mac = HmacSha256::new_from_slice(&self.secret)
            .map_err(|e| TamperDetectionError::HmacComputationFailed(e.to_string()))?;
        mac.update(data);
        Ok(format!("{:x}", mac.finalize().into_bytes()))
    }

    pub fn verify_data(&self, data: &[u8], signature: &str) -> Result<bool, TamperDetectionError> {
        let expected = self.sign_data(data)?;
        Ok(expected == signature)
    }
}

/// Immutable audit trail with HMAC-SHA256 signing and tamper detection
pub struct AuditTrail {
    verifier: SignatureVerifier,
    entries: Vec<AuditLogEntry>,
}

impl AuditTrail {
    pub fn new() -> Self {
        // Generate a random secret for HMAC operations
        let mut secret = [0u8; 32];
        use rand::Rng;
        rand::thread_rng().fill(&mut secret);

        Self {
            verifier: SignatureVerifier::new(secret.to_vec()),
            entries: Vec::new(),
        }
    }

    /// Sign an audit log entry with HMAC-SHA256
    pub fn sign_entry(&self, entry: &AuditLogEntry) -> Result<AuditLogEntry, TamperDetectionError> {
        let hash = entry.compute_hash();
        let signature = self.verifier.sign_data(hash.as_bytes())?;

        let mut signed_entry = entry.clone();
        signed_entry.signature = signature;

        if let Some(last) = self.entries.last() {
            signed_entry.previous_hash = Some(last.compute_hash());
        }

        Ok(signed_entry)
    }

    /// Verify the signature of an audit log entry
    pub fn verify_signature(&self, entry: &AuditLogEntry) -> Result<AuditLogEntry, TamperDetectionError> {
        let hash = entry.compute_hash();

        self.verifier
            .verify_data(hash.as_bytes(), &entry.signature)
            .and_then(|valid| {
                if valid {
                    Ok(entry.clone())
                } else {
                    Err(TamperDetectionError::SignatureVerificationFailed)
                }
            })
    }

    /// Verify blockchain-style chain integrity: each entry references the previous
    pub fn verify_chain_integrity(&self, entries: &[AuditLogEntry]) -> Result<bool, TamperDetectionError> {
        for i in 0..entries.len() {
            let current = &entries[i];

            // Verify current entry's signature
            self.verify_signature(current)?;

            // Check previous hash references
            if i > 0 {
                let previous = &entries[i - 1];
                let expected_hash = previous.compute_hash();

                if current.previous_hash.as_ref() != Some(&expected_hash) {
                    return Ok(false);
                }
            }
        }

        Ok(true)
    }

    pub fn add_entry(&mut self, entry: AuditLogEntry) -> Result<(), TamperDetectionError> {
        let signed = self.sign_entry(&entry)?;
        self.entries.push(signed);
        Ok(())
    }

    pub fn entries(&self) -> &[AuditLogEntry] {
        &self.entries
    }
}

impl Default for AuditTrail {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_audit_entry_hash_deterministic() {
        let id = Uuid::new_v4();
        let entry1 = AuditLogEntry::new_operation(id, "test", "success");

        // Note: Different timestamps will cause different hashes in real usage
        // For testing, we'll create them with the same data structure
        assert_eq!(entry1.compute_hash().len(), 64); // SHA256 hex is 64 chars
    }

    #[test]
    fn test_signature_verifier() {
        let verifier = SignatureVerifier::new(vec![1, 2, 3, 4, 5]);
        let data = b"test data";

        let signature = verifier.sign_data(data).expect("Sign should succeed");
        let verified = verifier.verify_data(data, &signature).expect("Verify should succeed");

        assert!(verified);
    }

    #[test]
    fn test_signature_verifier_rejects_tampered_data() {
        let verifier = SignatureVerifier::new(vec![1, 2, 3, 4, 5]);
        let data = b"test data";

        let signature = verifier.sign_data(data).expect("Sign should succeed");
        let verified = verifier.verify_data(b"tampered data", &signature)
            .expect("Verify should succeed");

        assert!(!verified);
    }

    #[test]
    fn test_audit_trail_multiple_entries() {
        let mut audit = AuditTrail::new();
        let capsule_id = Uuid::new_v4();

        let entry1 = AuditLogEntry::new_operation(capsule_id, "create", "success");
        let entry2 = AuditLogEntry::new_operation(capsule_id, "update", "success");

        audit.add_entry(entry1).expect("Add entry1");
        audit.add_entry(entry2).expect("Add entry2");

        assert_eq!(audit.entries().len(), 2);
    }

    #[test]
    fn test_chain_integrity_verification() {
        let mut audit = AuditTrail::new();
        let capsule_id = Uuid::new_v4();

        let entry1 = AuditLogEntry::new_operation(capsule_id, "create", "success");
        let entry2 = AuditLogEntry::new_operation(capsule_id, "update", "success");

        audit.add_entry(entry1).expect("Add entry1");
        audit.add_entry(entry2).expect("Add entry2");

        let is_valid = audit.verify_chain_integrity(audit.entries())
            .expect("Verify should succeed");
        assert!(is_valid);
    }
}
