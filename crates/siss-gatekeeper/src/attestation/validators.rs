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
