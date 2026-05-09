use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

pub mod validators;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum AttestationType {
    #[serde(rename = "hardware_enclave")]
    HardwareEnclave,
    #[serde(rename = "model_integrity")]
    ModelIntegrity,
    #[serde(rename = "sovereign_origin")]
    SovereignOrigin,
    #[serde(rename = "runtime_integrity")]
    RuntimeIntegrity,
}

impl AttestationType {
    pub fn as_str(&self) -> &'static str {
        match self {
            AttestationType::HardwareEnclave => "hardware_enclave",
            AttestationType::ModelIntegrity => "model_integrity",
            AttestationType::SovereignOrigin => "sovereign_origin",
            AttestationType::RuntimeIntegrity => "runtime_integrity",
        }
    }

    pub fn score_contribution(&self) -> u32 {
        match self {
            AttestationType::HardwareEnclave => 50,
            AttestationType::ModelIntegrity => 30,
            AttestationType::SovereignOrigin => 20,
            AttestationType::RuntimeIntegrity => 20,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum DataSensitivityLevel {
    #[serde(rename = "public")]
    Public,
    #[serde(rename = "internal")]
    Internal,
    #[serde(rename = "confidential")]
    Confidential,
    #[serde(rename = "secret")]
    Secret,
}

impl DataSensitivityLevel {
    pub fn as_str(&self) -> &'static str {
        match self {
            DataSensitivityLevel::Public => "public",
            DataSensitivityLevel::Internal => "internal",
            DataSensitivityLevel::Confidential => "confidential",
            DataSensitivityLevel::Secret => "secret",
        }
    }
}

/// AttestationVector: what a single attestation unlocks
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AttestationVector {
    pub attestation_type: AttestationType,
    pub score_contribution: u32,
    pub data_sensitivity_allowed: DataSensitivityLevel,
    pub hardware_classes_allowed: Vec<String>,  // ["LocalMlx", "Hybrid"]
    pub max_concurrency: u32,
    pub max_session_ttl_seconds: Option<u64>,
    pub jurisdiction: Option<String>,
    pub verified_at: DateTime<Utc>,
    pub valid_until: DateTime<Utc>,
}

/// Incoming attestation from external agent
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Attestation {
    pub attestation_type: AttestationType,
    pub format: String,  // "sgx_quote", "tpm2", "signed_manifest", etc.
    pub payload: String,  // base64-encoded
    pub signature: String,
    pub issuer: String,
    pub issued_at: DateTime<Utc>,
    pub valid_until: DateTime<Utc>,
}

impl Attestation {
    pub fn is_fresh(&self, max_age_seconds: u64) -> bool {
        let age = Utc::now()
            .signed_duration_since(self.issued_at)
            .num_seconds() as u64;
        age <= max_age_seconds && Utc::now() < self.valid_until
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_attestation_type_score_contribution() {
        assert_eq!(AttestationType::HardwareEnclave.score_contribution(), 50);
        assert_eq!(AttestationType::ModelIntegrity.score_contribution(), 30);
        assert_eq!(AttestationType::SovereignOrigin.score_contribution(), 20);
        assert_eq!(AttestationType::RuntimeIntegrity.score_contribution(), 20);
    }

    #[test]
    fn test_attestation_freshness_check() {
        let now = Utc::now();
        let fresh_attestation = Attestation {
            attestation_type: AttestationType::HardwareEnclave,
            format: "sgx_quote".to_string(),
            payload: "test".to_string(),
            signature: "sig".to_string(),
            issuer: "intel".to_string(),
            issued_at: now,
            valid_until: now + chrono::Duration::hours(1),
        };
        assert!(fresh_attestation.is_fresh(3600));
    }
}
