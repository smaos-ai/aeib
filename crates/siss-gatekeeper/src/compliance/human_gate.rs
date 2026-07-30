use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Request for human approval on high-risk decisions
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HumanGateRequest {
    pub capsule_id: Uuid,
    pub approval_level: super::capsule::ApprovalLevel,
    pub approval_threshold: f64, // 0.7 = 70% required
    pub timeout_secs: u64,       // Time allowed to respond
    pub created_at: u64,         // Unix timestamp
}

/// Cryptographic attestation: human approval with signature
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HumanGateAttestation {
    pub capsule_id: Uuid,
    pub approved: bool,
    pub approver_id: Uuid,            // Identity of human
    pub approver_ed25519_key: String, // Public key for verification
    pub timestamp: u64,               // Unix timestamp of approval
    pub ed25519_signature: String,    // Cryptographic proof
    pub reason: String,               // Why approved/rejected
}

impl HumanGateRequest {
    /// Create a new request for human approval
    pub fn new(
        capsule_id: Uuid,
        approval_level: super::capsule::ApprovalLevel,
        timeout_secs: u64,
    ) -> Self {
        Self {
            capsule_id,
            approval_level,
            approval_threshold: 0.7, // Default: 70% approval
            timeout_secs,
            created_at: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs(),
        }
    }

    /// Check if request is still valid (not timed out)
    pub fn is_valid(&self) -> bool {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();

        now < (self.created_at + self.timeout_secs)
    }

    /// Set custom approval threshold (e.g., 80% instead of default 70%)
    pub fn with_threshold(mut self, threshold: f64) -> Self {
        self.approval_threshold = threshold.clamp(0.0, 1.0);
        self
    }
}

impl HumanGateAttestation {
    /// Create a new attestation with signature
    pub fn new(
        capsule_id: Uuid,
        approved: bool,
        approver_id: Uuid,
        approver_ed25519_key: String,
        ed25519_signature: String,
        reason: String,
    ) -> Self {
        Self {
            capsule_id,
            approved,
            approver_id,
            approver_ed25519_key,
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs(),
            ed25519_signature,
            reason,
        }
    }

    /// Verify that the attestation signature is valid (simplified)
    /// In production, this would use actual Ed25519 verification
    pub fn verify_signature(&self) -> bool {
        // Simplified: just check that signature and key are non-empty
        !self.ed25519_signature.is_empty() && !self.approver_ed25519_key.is_empty()
    }

    /// Check if attestation is approved
    pub fn is_approved(&self) -> bool {
        self.approved && self.verify_signature()
    }

    /// Get human-readable summary
    pub fn summary(&self) -> String {
        format!(
            "Capsule {}: {} by {} at {} UTC ({})",
            self.capsule_id,
            if self.approved {
                "APPROVED"
            } else {
                "REJECTED"
            },
            self.approver_id,
            self.timestamp,
            self.reason
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_human_gate_request_creation() {
        let capsule_id = Uuid::new_v4();
        let request = HumanGateRequest::new(
            capsule_id,
            super::super::capsule::ApprovalLevel::High,
            300, // 5 minute timeout
        );

        assert_eq!(request.capsule_id, capsule_id);
        assert_eq!(request.approval_threshold, 0.7);
        assert_eq!(request.timeout_secs, 300);
    }

    #[test]
    fn test_human_gate_request_valid_immediately_after_creation() {
        let capsule_id = Uuid::new_v4();
        let request =
            HumanGateRequest::new(capsule_id, super::super::capsule::ApprovalLevel::High, 300);

        assert!(request.is_valid());
    }

    #[test]
    fn test_human_gate_request_custom_threshold() {
        let capsule_id = Uuid::new_v4();
        let request =
            HumanGateRequest::new(capsule_id, super::super::capsule::ApprovalLevel::High, 300)
                .with_threshold(0.9);

        assert_eq!(request.approval_threshold, 0.9);
    }

    #[test]
    fn test_human_gate_attestation_creation() {
        let capsule_id = Uuid::new_v4();
        let approver_id = Uuid::new_v4();
        let attestation = HumanGateAttestation::new(
            capsule_id,
            true,
            approver_id,
            "ed25519:pub_key_abc".to_string(),
            "ed25519:signature_xyz".to_string(),
            "Reviewed and approved by architect".to_string(),
        );

        assert_eq!(attestation.capsule_id, capsule_id);
        assert_eq!(attestation.approver_id, approver_id);
        assert!(attestation.approved);
    }

    #[test]
    fn test_human_gate_attestation_verify_signature() {
        let capsule_id = Uuid::new_v4();
        let approver_id = Uuid::new_v4();

        let valid_attestation = HumanGateAttestation::new(
            capsule_id,
            true,
            approver_id,
            "ed25519:pub_key".to_string(),
            "ed25519:sig".to_string(),
            "Approved".to_string(),
        );

        assert!(valid_attestation.verify_signature());
        assert!(valid_attestation.is_approved());
    }

    #[test]
    fn test_human_gate_attestation_rejected() {
        let capsule_id = Uuid::new_v4();
        let approver_id = Uuid::new_v4();

        let rejected = HumanGateAttestation::new(
            capsule_id,
            false,
            approver_id,
            "ed25519:pub_key".to_string(),
            "ed25519:sig".to_string(),
            "Rejected due to security concerns".to_string(),
        );

        assert!(!rejected.is_approved());
    }

    #[test]
    fn test_human_gate_attestation_summary() {
        let capsule_id = Uuid::new_v4();
        let approver_id = Uuid::new_v4();

        let attestation = HumanGateAttestation::new(
            capsule_id,
            true,
            approver_id,
            "ed25519:pub_key".to_string(),
            "ed25519:sig".to_string(),
            "Architect review complete".to_string(),
        );

        let summary = attestation.summary();
        assert!(summary.contains("APPROVED"));
        assert!(summary.contains("Architect review complete"));
    }
}
