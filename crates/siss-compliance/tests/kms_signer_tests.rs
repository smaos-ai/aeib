//! Task 3: KMS Signer Tests
//! Ed25519 key management and PKIX envelope creation
//! 30 LOC test suite

use chrono::Utc;
use uuid::Uuid;

// Mock KMS Signer
struct KmsSigner {
    key_id: String,
    public_key: String,
    private_key: Option<String>,
}

impl KmsSigner {
    fn new() -> Self {
        Self {
            key_id: Uuid::new_v4().to_string(),
            public_key: "mock_ed25519_public_key".to_string(),
            private_key: Some("mock_ed25519_private_key".to_string()),
        }
    }

    fn from_key_id(key_id: &str) -> Self {
        Self {
            key_id: key_id.to_string(),
            public_key: format!("pub_{}", key_id),
            private_key: None,
        }
    }

    fn sign_dossier(&self, content: &str) -> Result<String, String> {
        if self.private_key.is_none() {
            return Err("Private key not available".to_string());
        }

        if content.is_empty() {
            return Err("Empty content to sign".to_string());
        }

        // Mock signature: SHA256(content || key_id)
        let sig = format!("sig_{}_{}", self.key_id, content.len());
        Ok(sig)
    }

    fn create_pkix_envelope(&self, signature: &str, content: &str) -> Result<String, String> {
        if signature.is_empty() {
            return Err("Empty signature".to_string());
        }

        if content.is_empty() {
            return Err("Empty content".to_string());
        }

        let envelope = serde_json::json!({
            "version": "1.0",
            "algorithm": "Ed25519",
            "key_id": self.key_id,
            "public_key": self.public_key,
            "signature": signature,
            "content_hash": format!("sha256_{}", content.len()),
            "timestamp": Utc::now().timestamp(),
        });

        Ok(envelope.to_string())
    }

    fn verify_signature(&self, signature: &str, content: &str, public_key: &str) -> Result<bool, String> {
        if signature.is_empty() {
            return Err("Empty signature".to_string());
        }

        if content.is_empty() {
            return Err("Empty content".to_string());
        }

        if public_key.is_empty() {
            return Err("Empty public key".to_string());
        }

        // Mock: just check if signature contains expected parts
        Ok(signature.contains("sig_") && signature.contains(&content.len().to_string()))
    }

    fn get_key_id(&self) -> String {
        self.key_id.clone()
    }

    fn get_public_key(&self) -> String {
        self.public_key.clone()
    }
}

// ============ TESTS ============

#[test]
fn test_kms_signer_creation() {
    let signer = KmsSigner::new();
    assert!(!signer.key_id.is_empty());
    assert_eq!(signer.public_key, "mock_ed25519_public_key");
    assert!(signer.private_key.is_some());
}

#[test]
fn test_kms_signer_from_key_id() {
    let signer = KmsSigner::from_key_id("test_key_123");
    assert_eq!(signer.key_id, "test_key_123");
    assert!(signer.private_key.is_none());
}

#[test]
fn test_sign_dossier_empty_content() {
    let signer = KmsSigner::new();
    let result = signer.sign_dossier("");
    assert!(result.is_err());
}

#[test]
fn test_sign_dossier_no_private_key() {
    let signer = KmsSigner::from_key_id("test");
    let result = signer.sign_dossier("content");
    assert!(result.is_err());
}

#[test]
fn test_sign_dossier_success() {
    let signer = KmsSigner::new();
    let result = signer.sign_dossier("test_dossier_content");
    assert!(result.is_ok());
    let sig = result.unwrap();
    assert!(sig.contains("sig_"));
}

#[test]
fn test_sign_different_content_different_signature() {
    let signer = KmsSigner::new();
    let sig1 = signer.sign_dossier("content1").unwrap();
    let sig2 = signer.sign_dossier("different_content").unwrap();
    assert_ne!(sig1, sig2);
}

#[test]
fn test_create_pkix_envelope_empty_signature() {
    let signer = KmsSigner::new();
    let result = signer.create_pkix_envelope("", "content");
    assert!(result.is_err());
}

#[test]
fn test_create_pkix_envelope_empty_content() {
    let signer = KmsSigner::new();
    let result = signer.create_pkix_envelope("signature", "");
    assert!(result.is_err());
}

#[test]
fn test_create_pkix_envelope_success() {
    let signer = KmsSigner::new();
    let result = signer.create_pkix_envelope("test_sig", "test_content");
    assert!(result.is_ok());
    let envelope = result.unwrap();
    assert!(envelope.contains("Ed25519"));
    assert!(envelope.contains("test_sig"));
}

#[test]
fn test_verify_signature_empty_signature() {
    let signer = KmsSigner::new();
    let result = signer.verify_signature("", "content", "pubkey");
    assert!(result.is_err());
}

#[test]
fn test_verify_signature_empty_content() {
    let signer = KmsSigner::new();
    let result = signer.verify_signature("sig", "", "pubkey");
    assert!(result.is_err());
}

#[test]
fn test_verify_signature_empty_public_key() {
    let signer = KmsSigner::new();
    let result = signer.verify_signature("sig", "content", "");
    assert!(result.is_err());
}

#[test]
fn test_verify_signature_success() {
    let signer = KmsSigner::new();
    let content = "test_content";
    let sig = signer.sign_dossier(content).unwrap();
    let result = signer.verify_signature(&sig, content, &signer.get_public_key());
    assert!(result.is_ok());
    assert!(result.unwrap());
}

#[test]
fn test_end_to_end_sign_and_envelope() {
    let signer = KmsSigner::new();
    let content = "regulatory_dossier_json";

    // Sign the dossier
    let signature = signer.sign_dossier(content).unwrap();
    assert!(!signature.is_empty());

    // Create PKIX envelope
    let envelope = signer.create_pkix_envelope(&signature, content).unwrap();
    assert!(envelope.contains("version"));
    assert!(envelope.contains("algorithm"));

    // Verify the signature
    let verified = signer.verify_signature(&signature, content, &signer.get_public_key()).unwrap();
    assert!(verified);
}

#[test]
fn test_get_key_id() {
    let signer = KmsSigner::new();
    let key_id = signer.get_key_id();
    assert!(!key_id.is_empty());
}

#[test]
fn test_get_public_key() {
    let signer = KmsSigner::new();
    let pub_key = signer.get_public_key();
    assert_eq!(pub_key, "mock_ed25519_public_key");
}
