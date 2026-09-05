use base64::{Engine as _, engine::general_purpose};
/// EDEN Cluster D: DigitalWitnessCapsule — Cryptographic witness provenance
/// for authoritarian/conflict-zone contexts. Immutable ledger signing + QR distribution.
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fmt;
use uuid::Uuid;

// Re-export for convenience
use crate::ap2_ledger::{Ap2BurnLedger, BurnError};

/// Core witness capsule structure.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DigitalWitnessCapsule {
    pub witness_id: Uuid,
    pub did: String,
    pub content_hash: String,
    pub timestamp: DateTime<Utc>,
    pub nonce: Uuid,
    pub signature: Vec<u8>,
    pub qr_code: String,
    pub resilience_tags: Vec<String>,
}

/// Witness content to be encapsulated.
#[derive(Debug, Clone)]
pub struct WitnessContent {
    pub evidence: String,
    pub context: String,
    pub origin: String,
    pub timestamp: DateTime<Utc>,
}

/// Error types for witness generation and validation.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum WitnessGenerationError {
    QrEncodingFailed(String),
    DidGenerationFailed(String),
    LedgerSigningFailed(String),
    ContentHashFailed(String),
    ResilienceIntegrationFailed(String),
}

impl fmt::Display for WitnessGenerationError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            WitnessGenerationError::QrEncodingFailed(msg) => {
                write!(f, "QR encoding failed: {}", msg)
            }
            WitnessGenerationError::DidGenerationFailed(msg) => {
                write!(f, "DID generation failed: {}", msg)
            }
            WitnessGenerationError::LedgerSigningFailed(msg) => {
                write!(f, "Ledger signing failed: {}", msg)
            }
            WitnessGenerationError::ContentHashFailed(msg) => {
                write!(f, "Content hash failed: {}", msg)
            }
            WitnessGenerationError::ResilienceIntegrationFailed(msg) => {
                write!(f, "Resilience integration failed: {}", msg)
            }
        }
    }
}

impl std::error::Error for WitnessGenerationError {}

impl DigitalWitnessCapsule {
    /// Create a new witness capsule from content.
    pub fn new(content: WitnessContent) -> Self {
        let witness_id = Uuid::new_v4();
        let content_str = format!(
            "{}|{}|{}|{}",
            content.evidence, content.context, content.origin, content.timestamp
        );
        let content_hash = Self::compute_hash(&content_str);

        DigitalWitnessCapsule {
            witness_id,
            did: String::new(), // Deferred to generate_did()
            content_hash,
            timestamp: Utc::now(),
            nonce: witness_id, // Nonce = witness_id for ledger
            signature: Vec::new(),
            qr_code: String::new(),
            resilience_tags: vec!["offline".to_string(), "tor".to_string(), "mesh".to_string()],
        }
    }

    /// Compute SHA-256 hash of content.
    fn compute_hash(content: &str) -> String {
        let mut hasher = Sha256::new();
        hasher.update(content.as_bytes());
        format!("{:x}", hasher.finalize())
    }

    /// Generate W3C-compatible DID.
    pub fn generate_did(&mut self) -> String {
        let did = format!(
            "did:sovereign:{}",
            self.witness_id.to_string().replace("-", "")
        );
        self.did = did.clone();
        did
    }

    /// Sign capsule with AP2 ledger (using a mock signer for tests).
    pub fn sign_with_ap2_ledger(
        &mut self,
        signature_bytes: Vec<u8>,
    ) -> Result<(), WitnessGenerationError> {
        if signature_bytes.is_empty() {
            return Err(WitnessGenerationError::LedgerSigningFailed(
                "signature cannot be empty".to_string(),
            ));
        }
        self.signature = signature_bytes;
        Ok(())
    }

    /// Generate QR code (base64-encoded JSON payload).
    pub fn generate_qr_code(&mut self) -> Result<(), WitnessGenerationError> {
        // Create payload with core fields
        let payload = serde_json::json!({
            "witness_id": self.witness_id.to_string(),
            "did": self.did,
            "content_hash": self.content_hash,
            "timestamp": self.timestamp.to_rfc3339(),
            "resilience_tags": self.resilience_tags,
        });

        let json_str = serde_json::to_string(&payload)
            .map_err(|e| WitnessGenerationError::QrEncodingFailed(e.to_string()))?;

        // Encode as base64
        let encoded = general_purpose::STANDARD.encode(&json_str);
        self.qr_code = encoded;
        Ok(())
    }

    /// Validate that capsule is ready for offline distribution.
    pub fn validate_offline_distribution(&self) -> Result<(), WitnessGenerationError> {
        // Check resilience tags
        if self.resilience_tags.is_empty() {
            return Err(WitnessGenerationError::ResilienceIntegrationFailed(
                "no resilience tags present".to_string(),
            ));
        }

        // Check QR code exists and is base64
        if self.qr_code.is_empty() {
            return Err(WitnessGenerationError::ResilienceIntegrationFailed(
                "QR code not generated".to_string(),
            ));
        }

        // Validate base64 by attempting decode
        general_purpose::STANDARD
            .decode(&self.qr_code)
            .map_err(|e| {
                WitnessGenerationError::ResilienceIntegrationFailed(format!(
                    "QR code is not valid base64: {}",
                    e
                ))
            })?;

        // Check DID format
        if !self.did.starts_with("did:sovereign:") {
            return Err(WitnessGenerationError::DidGenerationFailed(
                "DID format invalid".to_string(),
            ));
        }

        // Check signature exists
        if self.signature.is_empty() {
            return Err(WitnessGenerationError::LedgerSigningFailed(
                "signature required for distribution".to_string(),
            ));
        }

        Ok(())
    }

    /// Register witness with AP2 ledger.
    pub fn sync_to_ledger(&self, ledger: &mut Ap2BurnLedger) -> Result<(), WitnessGenerationError> {
        // Use content_hash as mandate_hash
        ledger
            .register(
                self.witness_id,
                self.nonce,
                self.content_hash.clone(),
                self.timestamp,
            )
            .map_err(|e| match e {
                BurnError::NonceAlreadyBurned { .. } => {
                    WitnessGenerationError::LedgerSigningFailed(
                        "witness already registered (nonce burned)".to_string(),
                    )
                }
                BurnError::EntryNotFound { .. } => WitnessGenerationError::LedgerSigningFailed(
                    "ledger entry not found".to_string(),
                ),
            })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_content() -> WitnessContent {
        WitnessContent {
            evidence: "Evidence of human rights violation".to_string(),
            context: "Authoritarian regime crackdown".to_string(),
            origin: "Unknown Location".to_string(),
            timestamp: Utc::now(),
        }
    }

    // ============ Basic Generation Tests ============

    #[test]
    fn test_witness_new_creates_valid_capsule() {
        let content = create_test_content();
        let capsule = DigitalWitnessCapsule::new(content);

        // Check witness_id is UUID v4
        assert_ne!(capsule.witness_id, Uuid::nil());

        // Check timestamp is recent (within 1 second)
        let now = Utc::now();
        let diff = now
            .signed_duration_since(capsule.timestamp)
            .num_milliseconds();
        assert!(diff >= 0 && diff < 1000);

        // Check resilience tags
        assert_eq!(capsule.resilience_tags, vec!["offline", "tor", "mesh"]);

        // Check nonce = witness_id
        assert_eq!(capsule.nonce, capsule.witness_id);
    }

    #[test]
    fn test_witness_generate_did_format_valid() {
        let content = create_test_content();
        let mut capsule = DigitalWitnessCapsule::new(content);

        let did = capsule.generate_did();

        // Check DID format: did:sovereign:<32-char-hex>
        assert!(did.starts_with("did:sovereign:"));
        let hex_part = did.strip_prefix("did:sovereign:").unwrap();
        assert_eq!(hex_part.len(), 32); // UUID without hyphens = 32 hex chars

        // Check it's valid hex
        assert!(hex::decode(hex_part).is_ok());

        // Check self.did updated
        assert_eq!(capsule.did, did);
    }

    #[test]
    fn test_witness_content_hash_deterministic() {
        let content1 = WitnessContent {
            evidence: "Same evidence".to_string(),
            context: "Same context".to_string(),
            origin: "Same origin".to_string(),
            timestamp: Utc::now(),
        };

        let content2 = WitnessContent {
            evidence: "Same evidence".to_string(),
            context: "Same context".to_string(),
            origin: "Same origin".to_string(),
            timestamp: content1.timestamp,
        };

        let capsule1 = DigitalWitnessCapsule::new(content1);
        let capsule2 = DigitalWitnessCapsule::new(content2);

        assert_eq!(capsule1.content_hash, capsule2.content_hash);
    }

    // ============ QR Code Tests ============

    #[test]
    fn test_witness_qr_code_generation_succeeds() {
        let content = create_test_content();
        let mut capsule = DigitalWitnessCapsule::new(content);
        capsule.generate_did();

        let result = capsule.generate_qr_code();

        assert!(result.is_ok());
        assert!(!capsule.qr_code.is_empty());

        // Verify it's valid base64
        assert!(base64::decode(&capsule.qr_code).is_ok());
    }

    #[test]
    fn test_witness_qr_code_contains_all_fields() {
        let content = create_test_content();
        let mut capsule = DigitalWitnessCapsule::new(content);
        capsule.generate_did();
        capsule.generate_qr_code().unwrap();

        // Decode QR code
        let decoded = base64::decode(&capsule.qr_code).unwrap();
        let json_str = String::from_utf8(decoded).unwrap();
        let payload: serde_json::Value = serde_json::from_str(&json_str).unwrap();

        // Check all fields present
        assert!(payload.get("witness_id").is_some());
        assert!(payload.get("did").is_some());
        assert!(payload.get("content_hash").is_some());
        assert!(payload.get("timestamp").is_some());
        assert!(payload.get("resilience_tags").is_some());
    }

    #[test]
    fn test_witness_qr_code_roundtrip_decode() {
        let content = create_test_content();
        let mut capsule = DigitalWitnessCapsule::new(content);
        capsule.generate_did();
        capsule.generate_qr_code().unwrap();

        // Decode QR
        let decoded = base64::decode(&capsule.qr_code).unwrap();
        let json_str = String::from_utf8(decoded).unwrap();
        let payload: serde_json::Value = serde_json::from_str(&json_str).unwrap();

        // Verify witness_id matches
        assert_eq!(
            payload["witness_id"].as_str().unwrap(),
            capsule.witness_id.to_string()
        );

        // Verify content_hash matches
        assert_eq!(
            payload["content_hash"].as_str().unwrap(),
            capsule.content_hash
        );

        // Verify DID matches
        assert_eq!(payload["did"].as_str().unwrap(), capsule.did);
    }

    // ============ Ledger Integration Tests ============

    #[test]
    fn test_witness_ap2_ledger_signing() {
        let content = create_test_content();
        let mut capsule = DigitalWitnessCapsule::new(content);

        // Create signature (mock)
        let signature = b"mock_signature_bytes".to_vec();

        let result = capsule.sign_with_ap2_ledger(signature.clone());

        assert!(result.is_ok());
        assert_eq!(capsule.signature, signature);
    }

    #[test]
    fn test_witness_ledger_nonce_collision_rejected() {
        let content1 = create_test_content();
        let content2 = create_test_content();

        let mut capsule1 = DigitalWitnessCapsule::new(content1);
        let mut capsule2 = DigitalWitnessCapsule::new(content2);

        let mut ledger = Ap2BurnLedger::new();

        // Register first capsule
        capsule1.sign_with_ap2_ledger(b"sig1".to_vec()).unwrap();
        let result1 = capsule1.sync_to_ledger(&mut ledger);
        assert!(result1.is_ok());

        // Try to register second capsule with different nonce (should succeed)
        capsule2.sign_with_ap2_ledger(b"sig2".to_vec()).unwrap();
        let result2 = capsule2.sync_to_ledger(&mut ledger);
        assert!(result2.is_ok());

        // Try to register capsule1 again (same nonce, should fail)
        let result3 = capsule1.sync_to_ledger(&mut ledger);
        assert!(result3.is_err());
        match result3 {
            Err(WitnessGenerationError::LedgerSigningFailed(msg)) => {
                assert!(msg.contains("nonce burned"));
            }
            _ => panic!("expected LedgerSigningFailed"),
        }
    }

    #[test]
    fn test_witness_sync_to_ledger_idempotent() {
        let content = create_test_content();
        let mut capsule = DigitalWitnessCapsule::new(content);
        capsule.sign_with_ap2_ledger(b"signature".to_vec()).unwrap();

        let mut ledger = Ap2BurnLedger::new();

        // First sync succeeds
        let result1 = capsule.sync_to_ledger(&mut ledger);
        assert!(result1.is_ok());

        // Second sync fails (nonce already burned)
        let result2 = capsule.sync_to_ledger(&mut ledger);
        assert!(result2.is_err());
    }

    // ============ Resilience & Validation Tests ============

    #[test]
    fn test_witness_offline_distribution_validation_passes() {
        let content = create_test_content();
        let mut capsule = DigitalWitnessCapsule::new(content);
        capsule.generate_did();
        capsule.generate_qr_code().unwrap();
        capsule.sign_with_ap2_ledger(b"signature".to_vec()).unwrap();

        let result = capsule.validate_offline_distribution();

        assert!(result.is_ok());
    }

    #[test]
    fn test_witness_offline_distribution_rejects_unsigned() {
        let content = create_test_content();
        let mut capsule = DigitalWitnessCapsule::new(content);
        capsule.generate_did();
        capsule.generate_qr_code().unwrap();
        // Don't sign

        let result = capsule.validate_offline_distribution();

        assert!(result.is_err());
        match result {
            Err(WitnessGenerationError::LedgerSigningFailed(msg)) => {
                assert!(msg.contains("signature required"));
            }
            _ => panic!("expected LedgerSigningFailed"),
        }
    }

    #[test]
    fn test_witness_offline_distribution_rejects_no_qr() {
        let content = create_test_content();
        let mut capsule = DigitalWitnessCapsule::new(content);
        capsule.generate_did();
        capsule.sign_with_ap2_ledger(b"signature".to_vec()).unwrap();
        // Don't generate QR code

        let result = capsule.validate_offline_distribution();

        assert!(result.is_err());
        match result {
            Err(WitnessGenerationError::ResilienceIntegrationFailed(msg)) => {
                assert!(msg.contains("QR code not generated"));
            }
            _ => panic!("expected ResilienceIntegrationFailed"),
        }
    }

    #[test]
    fn test_witness_offline_distribution_rejects_no_did() {
        let content = create_test_content();
        let mut capsule = DigitalWitnessCapsule::new(content);
        // Don't generate DID
        capsule.generate_qr_code().unwrap();
        capsule.sign_with_ap2_ledger(b"signature".to_vec()).unwrap();

        let result = capsule.validate_offline_distribution();

        assert!(result.is_err());
        match result {
            Err(WitnessGenerationError::DidGenerationFailed(msg)) => {
                assert!(msg.contains("DID format invalid"));
            }
            _ => panic!("expected DidGenerationFailed"),
        }
    }

    #[test]
    fn test_witness_resilience_tags_persistent() {
        let content = create_test_content();
        let capsule = DigitalWitnessCapsule::new(content);

        // Serialize and deserialize
        let json = serde_json::to_string(&capsule).unwrap();
        let deserialized: DigitalWitnessCapsule = serde_json::from_str(&json).unwrap();

        // Check resilience tags unchanged
        assert_eq!(deserialized.resilience_tags, vec!["offline", "tor", "mesh"]);
    }

    #[test]
    fn test_witness_empty_signature_rejected() {
        let content = create_test_content();
        let mut capsule = DigitalWitnessCapsule::new(content);

        let result = capsule.sign_with_ap2_ledger(Vec::new());

        assert!(result.is_err());
        match result {
            Err(WitnessGenerationError::LedgerSigningFailed(msg)) => {
                assert!(msg.contains("signature cannot be empty"));
            }
            _ => panic!("expected LedgerSigningFailed"),
        }
    }

    #[test]
    fn test_witness_multiple_capsules_different_ids() {
        let content1 = create_test_content();
        let content2 = create_test_content();

        let capsule1 = DigitalWitnessCapsule::new(content1);
        let capsule2 = DigitalWitnessCapsule::new(content2);

        assert_ne!(capsule1.witness_id, capsule2.witness_id);
        assert_ne!(capsule1.nonce, capsule2.nonce);
    }

    #[test]
    fn test_witness_full_workflow() {
        let content = create_test_content();
        let mut capsule = DigitalWitnessCapsule::new(content);

        // Step 1: Generate DID
        let did = capsule.generate_did();
        assert!(did.starts_with("did:sovereign:"));

        // Step 2: Generate QR code
        capsule.generate_qr_code().unwrap();
        assert!(!capsule.qr_code.is_empty());

        // Step 3: Sign with ledger
        capsule.sign_with_ap2_ledger(b"signature".to_vec()).unwrap();
        assert!(!capsule.signature.is_empty());

        // Step 4: Validate for offline distribution
        let validation = capsule.validate_offline_distribution();
        assert!(validation.is_ok());

        // Step 5: Register with ledger
        let mut ledger = Ap2BurnLedger::new();
        let ledger_sync = capsule.sync_to_ledger(&mut ledger);
        assert!(ledger_sync.is_ok());

        // Step 6: Verify ledger registration
        let entry = ledger.get_entry(capsule.nonce);
        assert!(entry.is_some());
    }
}
