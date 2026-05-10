use super::{Attestation, AttestationVector, DataSensitivityLevel};
use chrono::Utc;
use std::collections::BTreeMap;

#[derive(Debug)]
pub enum AttestationValidationError {
    SignatureInvalid,
    IssuerNotTrusted,
    PayloadMalformed,
    Expired,
    TooOld,
}

/// Validates signature and freshness of an attestation
/// In a real implementation, this would verify cryptographic signatures
pub fn validate_attestation(
    attestation: &Attestation,
    max_attestation_age_seconds: u64,
    trusted_issuers: &[String],
) -> Result<(), AttestationValidationError> {
    // Check issuer is trusted
    if !trusted_issuers.contains(&attestation.issuer) {
        return Err(AttestationValidationError::IssuerNotTrusted);
    }

    // Check expiry
    if Utc::now() >= attestation.valid_until {
        return Err(AttestationValidationError::Expired);
    }

    // Check freshness
    let age = Utc::now()
        .signed_duration_since(attestation.issued_at)
        .num_seconds() as u64;
    if age > max_attestation_age_seconds {
        return Err(AttestationValidationError::TooOld);
    }

    Ok(())
}

/// Build capability vector from validated attestation
pub fn build_attestation_vector(attestation: &Attestation) -> AttestationVector {
    // Extract jurisdiction from SovereignOrigin payload if present
    let jurisdiction = if attestation.attestation_type == super::AttestationType::SovereignOrigin {
        serde_json::from_str::<serde_json::Value>(&attestation.payload)
            .ok()
            .and_then(|payload| payload.get("sovereign_id").and_then(|v| v.as_str()).map(|s| s.to_string()))
    } else {
        None
    };

    AttestationVector {
        attestation_type: attestation.attestation_type,
        score_contribution: attestation.attestation_type.score_contribution(),
        data_sensitivity_allowed: match attestation.attestation_type {
            super::AttestationType::HardwareEnclave => DataSensitivityLevel::Secret,
            super::AttestationType::ModelIntegrity => DataSensitivityLevel::Confidential,
            super::AttestationType::SovereignOrigin => DataSensitivityLevel::Internal,
            super::AttestationType::RuntimeIntegrity => DataSensitivityLevel::Confidential,
        },
        hardware_classes_allowed: vec!["LocalMlx".to_string(), "Hybrid".to_string()],
        max_concurrency: match attestation.attestation_type {
            super::AttestationType::HardwareEnclave => 10,
            super::AttestationType::ModelIntegrity => 5,
            super::AttestationType::SovereignOrigin => 5,
            super::AttestationType::RuntimeIntegrity => 3,
        },
        max_session_ttl_seconds: Some(86400),  // 24 hours default
        jurisdiction,
        verified_at: Utc::now(),
        valid_until: attestation.valid_until,
    }
}

/// Verify Ed25519 signature of a SovereignOrigin attestation.
/// Uses strict verification mode and canonical payload construction.
pub fn verify_sovereign_origin_signature(
    attestation: &Attestation,
    sovereign_public_key_pem: &str,
) -> Result<(), AttestationValidationError> {
    // 1. Decode signature from hex to 64-byte array
    let sig_bytes = hex::decode(&attestation.signature)
        .map_err(|_| AttestationValidationError::SignatureInvalid)?;
    let sig_array: [u8; 64] = sig_bytes.try_into()
        .map_err(|_| AttestationValidationError::SignatureInvalid)?;
    let signature = ed25519_dalek::Signature::from_bytes(&sig_array);

    // 2. Parse PEM public key to VerifyingKey
    let key_bytes = parse_ed25519_pem(sovereign_public_key_pem)
        .map_err(|_| AttestationValidationError::SignatureInvalid)?;
    let verifying_key = ed25519_dalek::VerifyingKey::from_bytes(&key_bytes)
        .map_err(|_| AttestationValidationError::SignatureInvalid)?;

    // 3. Build canonical payload (deterministic, excludes signature field)
    let canonical = build_canonical_attestation_payload(attestation)
        .map_err(|_| AttestationValidationError::PayloadMalformed)?;

    // 4. Verify signature in strict mode
    verifying_key.verify_strict(canonical.as_bytes(), &signature)
        .map_err(|_| AttestationValidationError::SignatureInvalid)
}

/// Build canonical (deterministic) attestation payload for signature verification.
/// Uses BTreeMap to ensure alphabetical key ordering, excludes signature field.
fn build_canonical_attestation_payload(attestation: &Attestation) -> Result<String, ()> {
    let mut map = BTreeMap::new();

    // Add fields in lexicographic order via BTreeMap
    map.insert(
        "attestation_type",
        serde_json::Value::String(attestation.attestation_type.as_str().to_string()),
    );
    map.insert(
        "format",
        serde_json::Value::String(attestation.format.clone()),
    );
    map.insert(
        "issued_at",
        serde_json::Value::String(attestation.issued_at.to_rfc3339()),
    );
    map.insert(
        "issuer",
        serde_json::Value::String(attestation.issuer.clone()),
    );
    map.insert(
        "payload",
        serde_json::Value::String(attestation.payload.clone()),
    );
    map.insert(
        "valid_until",
        serde_json::Value::String(attestation.valid_until.to_rfc3339()),
    );
    // NOTE: signature field is intentionally excluded

    serde_json::to_string(&map).map_err(|_| ())
}

/// Parse Ed25519 public key from PEM format (PKCS#8 or raw).
/// Extracts the 32-byte public key bytes.
pub fn parse_ed25519_pem(pem_str: &str) -> Result<[u8; 32], ()> {
    use base64::Engine as _;

    // Simple PEM parsing: extract base64 between BEGIN/END markers
    let begin_marker = "-----BEGIN PUBLIC KEY-----";
    let end_marker = "-----END PUBLIC KEY-----";

    let start = pem_str.find(begin_marker)
        .ok_or(())?
        .saturating_add(begin_marker.len());
    let end = pem_str[start..].find(end_marker)
        .ok_or(())?
        .saturating_add(start);

    let b64_str = pem_str[start..end]
        .split_whitespace()
        .collect::<String>();

    let engine = base64::engine::general_purpose::STANDARD;
    let der = engine.decode(&b64_str).map_err(|_| ())?;

    // PKCS#8 format: extract public key from DER (simplified)
    // For Ed25519, the raw key is typically the last 32 bytes after structure overhead
    if der.len() >= 32 {
        let mut key_bytes = [0u8; 32];
        key_bytes.copy_from_slice(&der[der.len() - 32..]);
        Ok(key_bytes)
    } else {
        Err(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;

    #[test]
    fn test_validate_attestation_success() {
        let now = Utc::now();
        let attestation = Attestation {
            attestation_type: super::super::AttestationType::HardwareEnclave,
            format: "sgx_quote".to_string(),
            payload: "payload".to_string(),
            signature: "sig".to_string(),
            issuer: "intel".to_string(),
            issued_at: now,
            valid_until: now + chrono::Duration::hours(1),
        };

        let result = validate_attestation(&attestation, 3600, &["intel".to_string()]);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_attestation_issuer_not_trusted() {
        let now = Utc::now();
        let attestation = Attestation {
            attestation_type: super::super::AttestationType::HardwareEnclave,
            format: "sgx_quote".to_string(),
            payload: "payload".to_string(),
            signature: "sig".to_string(),
            issuer: "untrusted".to_string(),
            issued_at: now,
            valid_until: now + chrono::Duration::hours(1),
        };

        let result = validate_attestation(&attestation, 3600, &["intel".to_string()]);
        assert!(matches!(result, Err(AttestationValidationError::IssuerNotTrusted)));
    }

    #[test]
    fn test_validate_attestation_expired() {
        let now = Utc::now();
        let attestation = Attestation {
            attestation_type: super::super::AttestationType::HardwareEnclave,
            format: "sgx_quote".to_string(),
            payload: "payload".to_string(),
            signature: "sig".to_string(),
            issuer: "intel".to_string(),
            issued_at: now - chrono::Duration::hours(2),
            valid_until: now - chrono::Duration::hours(1),
        };

        let result = validate_attestation(&attestation, 3600, &["intel".to_string()]);
        assert!(matches!(result, Err(AttestationValidationError::Expired)));
    }

    #[test]
    fn test_validate_attestation_too_old() {
        let now = Utc::now();
        let attestation = Attestation {
            attestation_type: super::super::AttestationType::HardwareEnclave,
            format: "sgx_quote".to_string(),
            payload: "payload".to_string(),
            signature: "sig".to_string(),
            issuer: "intel".to_string(),
            issued_at: now - chrono::Duration::hours(2),
            valid_until: now + chrono::Duration::hours(1),
        };

        let result = validate_attestation(&attestation, 60, &["intel".to_string()]);
        assert!(matches!(result, Err(AttestationValidationError::TooOld)));
    }

    #[test]
    fn test_build_attestation_vector_hardware_enclave() {
        let now = Utc::now();
        let attestation = Attestation {
            attestation_type: super::super::AttestationType::HardwareEnclave,
            format: "sgx_quote".to_string(),
            payload: "payload".to_string(),
            signature: "sig".to_string(),
            issuer: "intel".to_string(),
            issued_at: now,
            valid_until: now + chrono::Duration::hours(1),
        };

        let vector = build_attestation_vector(&attestation);

        assert_eq!(vector.attestation_type, super::super::AttestationType::HardwareEnclave);
        assert_eq!(vector.score_contribution, 50);
        assert_eq!(vector.data_sensitivity_allowed, super::super::DataSensitivityLevel::Secret);
        assert_eq!(vector.max_concurrency, 10);
        assert!(vector.hardware_classes_allowed.contains(&"LocalMlx".to_string()));
    }

    #[test]
    fn test_build_attestation_vector_model_integrity() {
        let now = Utc::now();
        let attestation = Attestation {
            attestation_type: super::super::AttestationType::ModelIntegrity,
            format: "signed_manifest".to_string(),
            payload: "manifest".to_string(),
            signature: "sig".to_string(),
            issuer: "anthropic".to_string(),
            issued_at: now,
            valid_until: now + chrono::Duration::days(30),
        };

        let vector = build_attestation_vector(&attestation);

        assert_eq!(vector.attestation_type, super::super::AttestationType::ModelIntegrity);
        assert_eq!(vector.score_contribution, 30);
        assert_eq!(vector.data_sensitivity_allowed, super::super::DataSensitivityLevel::Confidential);
        assert_eq!(vector.max_concurrency, 5);
    }

    #[test]
    fn test_build_attestation_vector_sovereign_origin() {
        let now = Utc::now();
        let attestation = Attestation {
            attestation_type: super::super::AttestationType::SovereignOrigin,
            format: "jurisdiction_cert".to_string(),
            payload: "cert".to_string(),
            signature: "sig".to_string(),
            issuer: "eu-authority".to_string(),
            issued_at: now,
            valid_until: now + chrono::Duration::days(365),
        };

        let vector = build_attestation_vector(&attestation);

        assert_eq!(vector.attestation_type, super::super::AttestationType::SovereignOrigin);
        assert_eq!(vector.score_contribution, 20);
        assert_eq!(vector.data_sensitivity_allowed, super::super::DataSensitivityLevel::Internal);
        assert_eq!(vector.max_concurrency, 5);
    }

    #[test]
    fn test_build_attestation_vector_runtime_integrity() {
        let now = Utc::now();
        let attestation = Attestation {
            attestation_type: super::super::AttestationType::RuntimeIntegrity,
            format: "container_manifest".to_string(),
            payload: "manifest".to_string(),
            signature: "sig".to_string(),
            issuer: "container-platform".to_string(),
            issued_at: now,
            valid_until: now + chrono::Duration::days(7),
        };

        let vector = build_attestation_vector(&attestation);

        assert_eq!(vector.attestation_type, super::super::AttestationType::RuntimeIntegrity);
        assert_eq!(vector.score_contribution, 20);
        assert_eq!(vector.data_sensitivity_allowed, super::super::DataSensitivityLevel::Confidential);
        assert_eq!(vector.max_concurrency, 3);
    }

    #[test]
    fn test_verify_sovereign_origin_signature_valid() {
        use base64::Engine as _;
        use ed25519_dalek::Signer;

        // Generate test keypair
        let mut rng = rand::thread_rng();
        let keypair = ed25519_dalek::SigningKey::generate(&mut rng);
        let verifying_key = keypair.verifying_key();

        // Create PEM string with proper encoding
        let pub_key_bytes = verifying_key.to_bytes();
        let engine = base64::engine::general_purpose::STANDARD;
        let b64_pub_key = engine.encode(&pub_key_bytes);
        let pem = format!(
            "-----BEGIN PUBLIC KEY-----\n{}\n-----END PUBLIC KEY-----",
            b64_pub_key
        );

        let now = Utc::now();
        let mut attestation = Attestation {
            attestation_type: super::super::AttestationType::SovereignOrigin,
            format: "jurisdiction_cert".to_string(),
            payload: r#"{"sovereign_id":"eu-001"}"#.to_string(),
            signature: "".to_string(),
            issuer: "eu-authority".to_string(),
            issued_at: now,
            valid_until: now + chrono::Duration::days(365),
        };

        // Build canonical payload and sign it
        let canonical = build_canonical_attestation_payload(&attestation).unwrap();
        let sig = keypair.sign(canonical.as_bytes());
        attestation.signature = hex::encode(sig.to_bytes());

        // Verify should succeed
        let result = verify_sovereign_origin_signature(&attestation, &pem);
        assert!(result.is_ok());
    }

    #[test]
    fn test_verify_sovereign_origin_signature_invalid_sig() {
        use base64::Engine as _;

        let now = Utc::now();
        let attestation = Attestation {
            attestation_type: super::super::AttestationType::SovereignOrigin,
            format: "jurisdiction_cert".to_string(),
            payload: r#"{"sovereign_id":"eu-001"}"#.to_string(),
            signature: "0000000000000000000000000000000000000000000000000000000000000000\
                       0000000000000000000000000000000000000000000000000000000000000000".to_string(),
            issuer: "eu-authority".to_string(),
            issued_at: now,
            valid_until: now + chrono::Duration::days(365),
        };

        let mut rng = rand::thread_rng();
        let keypair = ed25519_dalek::SigningKey::generate(&mut rng);
        let verifying_key = keypair.verifying_key();
        let pub_key_bytes = verifying_key.to_bytes();
        let engine = base64::engine::general_purpose::STANDARD;
        let b64_pub_key = engine.encode(&pub_key_bytes);
        let pem = format!(
            "-----BEGIN PUBLIC KEY-----\n{}\n-----END PUBLIC KEY-----",
            b64_pub_key
        );

        let result = verify_sovereign_origin_signature(&attestation, &pem);
        assert!(matches!(result, Err(AttestationValidationError::SignatureInvalid)));
    }

    #[test]
    fn test_verify_sovereign_origin_signature_malformed_pem() {
        let now = Utc::now();
        let attestation = Attestation {
            attestation_type: super::super::AttestationType::SovereignOrigin,
            format: "jurisdiction_cert".to_string(),
            payload: r#"{"sovereign_id":"eu-001"}"#.to_string(),
            signature: "deadbeef".to_string(),
            issuer: "eu-authority".to_string(),
            issued_at: now,
            valid_until: now + chrono::Duration::days(365),
        };

        let malformed_pem = "not a valid pem string";
        let result = verify_sovereign_origin_signature(&attestation, malformed_pem);
        assert!(matches!(result, Err(AttestationValidationError::SignatureInvalid)));
    }

    #[test]
    fn test_canonical_payload_excludes_signature_field() {
        let now = Utc::now();
        let attestation = Attestation {
            attestation_type: super::super::AttestationType::SovereignOrigin,
            format: "jurisdiction_cert".to_string(),
            payload: r#"{"sovereign_id":"eu-001"}"#.to_string(),
            signature: "this-signature-should-not-appear".to_string(),
            issuer: "eu-authority".to_string(),
            issued_at: now,
            valid_until: now + chrono::Duration::days(365),
        };

        let canonical = build_canonical_attestation_payload(&attestation).unwrap();
        assert!(!canonical.contains("this-signature-should-not-appear"));
        assert!(canonical.contains("jurisdiction_cert"));
        assert!(canonical.contains("sovereign_origin"));
    }

    #[test]
    fn test_canonical_payload_key_ordering_deterministic() {
        let now = Utc::now();
        let attestation = Attestation {
            attestation_type: super::super::AttestationType::SovereignOrigin,
            format: "jurisdiction_cert".to_string(),
            payload: r#"{"sovereign_id":"eu-001"}"#.to_string(),
            signature: "sig".to_string(),
            issuer: "eu-authority".to_string(),
            issued_at: now,
            valid_until: now + chrono::Duration::days(365),
        };

        // Generate canonical payload twice, should be identical (BTreeMap ensures ordering)
        let canonical1 = build_canonical_attestation_payload(&attestation).unwrap();
        let canonical2 = build_canonical_attestation_payload(&attestation).unwrap();
        assert_eq!(canonical1, canonical2);

        // Verify keys appear in alphabetical order
        let keys_pos = [
            canonical1.find("\"attestation_type\""),
            canonical1.find("\"format\""),
            canonical1.find("\"issued_at\""),
            canonical1.find("\"issuer\""),
            canonical1.find("\"payload\""),
            canonical1.find("\"valid_until\""),
        ];
        assert!(keys_pos[0] < keys_pos[1] && keys_pos[1] < keys_pos[2] &&
                keys_pos[2] < keys_pos[3] && keys_pos[3] < keys_pos[4] &&
                keys_pos[4] < keys_pos[5]);
    }
}
