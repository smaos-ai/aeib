use super::{Attestation, AttestationVector, DataSensitivityLevel};
use chrono::Utc;

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
        jurisdiction: None,
        verified_at: Utc::now(),
        valid_until: attestation.valid_until,
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
}
