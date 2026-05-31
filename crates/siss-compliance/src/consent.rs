use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Legal basis for processing personal data under GDPR Article 6
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum PurposeBasis {
    /// Explicit user consent (GDPR Art. 6(1)(a))
    Consent,
    /// Performance of contract (Art. 6(1)(b))
    Contract,
    /// Legal obligation (Art. 6(1)(c))
    Legal,
    /// Vital interests (Art. 6(1)(d))
    Necessity,
    /// Public task (Art. 6(1)(e))
    Public,
    /// Legitimate interests (Art. 6(1)(f))
    Legitimate,
}

/// Represents a data subject (individual) in the compliance system
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DataSubject {
    pub id: Uuid,
    pub email: String,
    pub jurisdiction: String, // 'EU', 'US', 'CH', etc.
    pub created_at: DateTime<Utc>,
}

/// Records consent or legal basis for processing a data subject's information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConsentRecord {
    pub data_subject_id: Uuid,
    pub purpose: PurposeBasis,
    pub scope: Vec<String>, // 'health_data', 'genome', 'cgm_readings', etc.
    pub granted_at: DateTime<Utc>,
    pub expires_at: Option<DateTime<Utc>>,
    pub withdrawn_at: Option<DateTime<Utc>>,
}

impl ConsentRecord {
    /// Checks if consent is currently valid (not withdrawn, not expired)
    pub fn is_valid(&self) -> bool {
        self.withdrawn_at.is_none()
            && (self.expires_at.is_none() || self.expires_at > Some(Utc::now()))
    }

    /// Exercises right to erasure (GDPR Art. 17) by withdrawing consent
    pub fn right_to_erasure(&mut self) {
        self.withdrawn_at = Some(Utc::now());
    }

    /// Exercises right to portability (GDPR Art. 20) by exporting consent record
    pub fn right_to_portability(&self) -> String {
        serde_json::to_string(self).unwrap()
    }

    /// Generates audit trail entry for this consent record
    pub fn consent_audit_trail(&self) -> String {
        format!(
            "DataSubject: {}, Purpose: {:?}, Granted: {}, Valid: {}",
            self.data_subject_id,
            self.purpose,
            self.granted_at.to_rfc3339(),
            self.is_valid()
        )
    }
}
