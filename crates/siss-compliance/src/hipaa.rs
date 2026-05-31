use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// PHI (Protected Health Information) classification categories
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum PhiClassification {
    /// Names, addresses, dates, contact info
    Identifier,
    /// Clinical notes, diagnosis codes, treatment records
    MedicalRecord,
    /// DNA sequences, fingerprints, iris scans
    Biometric,
    /// CGM readings, HRV, blood pressure, oxygen saturation
    HealthData,
    /// Genomic sequences, SNP arrays, pathogenic variants
    Genetic,
}

/// Business Associate Agreement - HIPAA compliance contract
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BusinessAssociateAgreement {
    pub baa_id: Uuid,
    pub covered_entity: String,
    pub business_associate: String,
    pub phi_types: Vec<PhiClassification>,
    pub safeguards_implemented: Vec<String>, // Encryption, access controls, etc.
    pub breach_notification_days: u32,       // Default: 30 days per HIPAA
}

/// Access log for PHI - tracks who accessed what PHI and when
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PhiAccessLog {
    pub who: Uuid,                     // Who accessed
    pub what: Vec<PhiClassification>,  // What PHI types
    pub when: DateTime<Utc>,
    pub why: String,                   // Purpose (treatment, payment, operations)
}
