//! L8 Error Handling: Proof generation with immutable ledger
//! Prevents execution until all errors are logged with cryptographic proof

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Error, Debug, Clone, Serialize, Deserialize)]
pub enum L8Error {
    #[error("Work receipt creation failed: {reason}. Recovery: {recovery}")]
    ReceiptCreationFailed {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Ledger signing failed: {reason}. Recovery: {recovery}")]
    LedgerSigningFailed {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Immutability check failed: {reason}. Recovery: {recovery}")]
    ImmutabilityCheckFailed {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Audit trail corruption detected: {reason}. Recovery: {recovery}")]
    AuditTrailCorrupted {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Proof verification failed: {reason}. Recovery: {recovery}")]
    ProofVerificationFailed {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("AP2 ledger entry failed: {reason}. Recovery: {recovery}")]
    AP2EntryFailed {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("KMS key not available: {reason}. Recovery: {recovery}")]
    KmsKeyUnavailable {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Proof generation timeout: exceeded {timeout_ms}ms. Recovery: {recovery}")]
    ProofTimeout {
        timeout_ms: u64,
        recovery: String,
        timestamp: DateTime<Utc>,
    },
}

impl L8Error {
    pub fn reason(&self) -> String {
        match self {
            Self::ReceiptCreationFailed { reason, .. } => reason.clone(),
            Self::LedgerSigningFailed { reason, .. } => reason.clone(),
            Self::ImmutabilityCheckFailed { reason, .. } => reason.clone(),
            Self::AuditTrailCorrupted { reason, .. } => reason.clone(),
            Self::ProofVerificationFailed { reason, .. } => reason.clone(),
            Self::AP2EntryFailed { reason, .. } => reason.clone(),
            Self::KmsKeyUnavailable { reason, .. } => reason.clone(),
            Self::ProofTimeout { timeout_ms, .. } => {
                format!("Proof generation exceeded {}ms", timeout_ms)
            }
        }
    }

    pub fn timestamp(&self) -> DateTime<Utc> {
        match self {
            Self::ReceiptCreationFailed { timestamp, .. }
            | Self::LedgerSigningFailed { timestamp, .. }
            | Self::ImmutabilityCheckFailed { timestamp, .. }
            | Self::AuditTrailCorrupted { timestamp, .. }
            | Self::ProofVerificationFailed { timestamp, .. }
            | Self::AP2EntryFailed { timestamp, .. }
            | Self::KmsKeyUnavailable { timestamp, .. }
            | Self::ProofTimeout { timestamp, .. } => *timestamp,
        }
    }

    pub fn recovery(&self) -> String {
        match self {
            Self::ReceiptCreationFailed { recovery, .. }
            | Self::LedgerSigningFailed { recovery, .. }
            | Self::ImmutabilityCheckFailed { recovery, .. }
            | Self::AuditTrailCorrupted { recovery, .. }
            | Self::ProofVerificationFailed { recovery, .. }
            | Self::AP2EntryFailed { recovery, .. }
            | Self::KmsKeyUnavailable { recovery, .. }
            | Self::ProofTimeout { recovery, .. } => recovery.clone(),
        }
    }

    /// Critical: L8 errors are unrecoverable—must prevent execution
    pub fn is_critical(&self) -> bool {
        matches!(
            self,
            Self::ImmutabilityCheckFailed { .. }
                | Self::AuditTrailCorrupted { .. }
                | Self::ProofVerificationFailed { .. }
                | Self::KmsKeyUnavailable { .. }
        )
    }
}

/// AuditEntry for proof operations in L8
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct L8AuditEntry {
    pub timestamp: DateTime<Utc>,
    pub event_id: String,
    pub receipt_id: String,
    pub operation: String,
    pub signed: bool,
    pub immutable: bool,
    pub error: Option<String>,
    pub critical_error: bool,
}

impl L8AuditEntry {
    pub fn new(receipt_id: String, operation: String) -> Self {
        Self {
            timestamp: Utc::now(),
            event_id: uuid::Uuid::new_v4().to_string(),
            receipt_id,
            operation,
            signed: false,
            immutable: false,
            error: None,
            critical_error: false,
        }
    }

    pub fn mark_signed(mut self) -> Self {
        self.signed = true;
        self
    }

    pub fn mark_immutable(mut self) -> Self {
        self.immutable = true;
        self
    }

    pub fn with_error(mut self, error: L8Error) -> Self {
        let is_critical = error.is_critical();
        self.error = Some(format!("{:?}", error));
        self.critical_error = is_critical;
        self
    }
}

/// Input validation for L8
pub fn validate_receipt_id(receipt_id: &str) -> Result<(), L8Error> {
    if receipt_id.is_empty() {
        return Err(L8Error::ReceiptCreationFailed {
            reason: "Receipt ID cannot be empty".to_string(),
            recovery: "Use UUID v4 for receipt ID".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

pub fn validate_agent_id(agent_id: &str) -> Result<(), L8Error> {
    if agent_id.is_empty() {
        return Err(L8Error::ReceiptCreationFailed {
            reason: "Agent ID cannot be empty".to_string(),
            recovery: "Provide agent identifier".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

pub fn validate_hash(hash: &str) -> Result<(), L8Error> {
    if hash.is_empty() {
        return Err(L8Error::LedgerSigningFailed {
            reason: "Hash cannot be empty".to_string(),
            recovery: "Compute hash from work data".to_string(),
            timestamp: Utc::now(),
        });
    }
    if hash.len() != 64 && hash.len() != 128 {
        return Err(L8Error::LedgerSigningFailed {
            reason: format!("Invalid hash length: {}", hash.len()),
            recovery: "Use SHA256 (64 hex) or SHA512 (128 hex)".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

pub fn validate_signature(signature: &str) -> Result<(), L8Error> {
    if signature.is_empty() {
        return Err(L8Error::LedgerSigningFailed {
            reason: "Signature cannot be empty".to_string(),
            recovery: "Sign hash with private key".to_string(),
            timestamp: Utc::now(),
        });
    }
    if signature.len() < 64 {
        return Err(L8Error::LedgerSigningFailed {
            reason: "Signature too short".to_string(),
            recovery: "Ensure Ed25519 PQC signature".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

pub fn validate_work_description(description: &str) -> Result<(), L8Error> {
    if description.is_empty() {
        return Err(L8Error::ReceiptCreationFailed {
            reason: "Work description cannot be empty".to_string(),
            recovery: "Describe work performed (layer, action, outcome)".to_string(),
            timestamp: Utc::now(),
        });
    }
    if description.len() > 50_000 {
        return Err(L8Error::ReceiptCreationFailed {
            reason: "Work description exceeds 50KB".to_string(),
            recovery: "Summarize or split work description".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_validate_receipt_id_empty() {
        let result = validate_receipt_id("");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_agent_id_empty() {
        let result = validate_agent_id("");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_hash_invalid_length() {
        let result = validate_hash("abc123");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_hash_valid_sha256() {
        let sha256_hash = "a".repeat(64);
        let result = validate_hash(&sha256_hash);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_hash_valid_sha512() {
        let sha512_hash = "a".repeat(128);
        let result = validate_hash(&sha512_hash);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_signature_too_short() {
        let result = validate_signature("short");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_signature_valid() {
        let sig = "a".repeat(128);
        let result = validate_signature(&sig);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_work_description_empty() {
        let result = validate_work_description("");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_work_description_too_large() {
        let large_desc = "x".repeat(50_001);
        let result = validate_work_description(&large_desc);
        assert!(result.is_err());
    }

    #[test]
    fn test_audit_entry_mark_signed() {
        let entry = L8AuditEntry::new("receipt1".to_string(), "sign_receipt".to_string());
        let entry = entry.mark_signed();
        assert!(entry.signed);
    }

    #[test]
    fn test_audit_entry_mark_immutable() {
        let entry = L8AuditEntry::new("receipt1".to_string(), "verify".to_string());
        let entry = entry.mark_immutable();
        assert!(entry.immutable);
    }

    #[test]
    fn test_audit_entry_with_critical_error() {
        let entry = L8AuditEntry::new("receipt1".to_string(), "verify".to_string());
        let error = L8Error::ImmutabilityCheckFailed {
            reason: "hash mismatch".to_string(),
            recovery: "audit trail corrupted".to_string(),
            timestamp: Utc::now(),
        };
        let entry = entry.with_error(error.clone());
        assert!(entry.critical_error);
        assert!(error.is_critical());
    }

    #[test]
    fn test_error_is_critical_detection() {
        let critical = L8Error::ProofVerificationFailed {
            reason: "sig invalid".to_string(),
            recovery: "retry".to_string(),
            timestamp: Utc::now(),
        };
        assert!(critical.is_critical());

        let non_critical = L8Error::ReceiptCreationFailed {
            reason: "unknown".to_string(),
            recovery: "retry".to_string(),
            timestamp: Utc::now(),
        };
        assert!(!non_critical.is_critical());
    }
}
