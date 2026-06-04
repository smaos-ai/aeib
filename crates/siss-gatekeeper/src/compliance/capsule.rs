use uuid::Uuid;
use serde::{Deserialize, Serialize};

/// Federal compliance proof: cryptographic envelope for every AI inference
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComplianceCapsule {
    /// Unique identifier for this decision/inference
    pub capsule_id: Uuid,

    /// Model identity
    pub model_name: String,
    pub model_version: String,

    /// Governance proof (cryptographic)
    pub merkle_root: String,           // SHA256(lineage)
    pub ed25519_signature: String,     // Architect attestation

    /// Pre-execution constraints
    pub safety_gates: Vec<SafetyGateResult>,
    pub human_gate_required: bool,
    pub approval_level: ApprovalLevel,

    /// Compliance claims
    pub compliance_claims: Vec<String>, // "OMB-M-24-10 § 4.2.1", etc.
    pub audit_trail_hash: String,      // Points to EXEC_LOG

    /// Economic binding (AP2)
    pub creator_fee_bps: u16,          // 100 = 1%
    pub platform_fee_bps: u16,         // 9900 = 99%

    /// Fail-closed fallback
    pub safe_policy_hash: String,

    /// Timestamp
    pub created_at: u64,               // Unix seconds
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ApprovalLevel {
    Low,      // <30% confidence → no human gate
    Medium,   // 30–70% confidence → optional human gate
    High,     // >70% confidence → mandatory human gate
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SafetyGateResult {
    pub gate_type: SafetyGateType,
    pub passed: bool,
    pub confidence: f64,               // 0.0–1.0
    pub reason: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SafetyGateType {
    XSSPrevention,
    SQLInjectionPrevention,
    PromptInjectionPrevention,
    PIIRedaction,
    ToxicityThreshold,
    ConfidentialityClassifier,
}

impl ComplianceCapsule {
    /// Create a new capsule with minimal defaults
    pub fn new(
        model_name: String,
        model_version: String,
        approval_level: ApprovalLevel,
    ) -> Self {
        Self {
            capsule_id: Uuid::new_v4(),
            model_name,
            model_version,
            merkle_root: String::new(),
            ed25519_signature: String::new(),
            safety_gates: vec![],
            human_gate_required: matches!(approval_level, ApprovalLevel::High),
            approval_level,
            compliance_claims: vec![],
            audit_trail_hash: String::new(),
            creator_fee_bps: 100,      // 1%
            platform_fee_bps: 9900,    // 99%
            safe_policy_hash: String::new(),
            created_at: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs(),
        }
    }

    /// Add a safety gate result
    pub fn add_safety_gate(&mut self, result: SafetyGateResult) {
        self.safety_gates.push(result);
    }

    /// Check if all safety gates passed
    pub fn all_gates_passed(&self) -> bool {
        self.safety_gates.iter().all(|g| g.passed)
    }

    /// Set Merkle proof (cryptographic lineage)
    pub fn set_merkle_proof(&mut self, root: String, signature: String) {
        self.merkle_root = root;
        self.ed25519_signature = signature;
    }

    /// Set audit trail hash (links to EXEC_LOG)
    pub fn set_audit_trail(&mut self, hash: String) {
        self.audit_trail_hash = hash;
    }

    /// Verify capsule is ready for execution (all invariants met)
    pub fn is_ready_for_execution(&self) -> Result<(), String> {
        // All gates must pass
        if !self.all_gates_passed() {
            return Err("Not all safety gates passed".to_string());
        }

        // Merkle proof required
        if self.merkle_root.is_empty() || self.ed25519_signature.is_empty() {
            return Err("Merkle proof missing".to_string());
        }

        // Human gate required for High approval level
        if self.human_gate_required && self.audit_trail_hash.is_empty() {
            return Err("Human gate attestation required but not provided".to_string());
        }

        // Safe fallback must be defined
        if self.safe_policy_hash.is_empty() {
            return Err("Safe policy fallback not defined".to_string());
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_capsule_creation() {
        let capsule = ComplianceCapsule::new(
            "Claude".to_string(),
            "3.5-sonnet".to_string(),
            ApprovalLevel::Medium,
        );

        assert_eq!(capsule.model_name, "Claude");
        assert_eq!(capsule.model_version, "3.5-sonnet");
        assert_eq!(capsule.approval_level, ApprovalLevel::Medium);
        assert!(!capsule.human_gate_required); // Medium doesn't require gate
    }

    #[test]
    fn test_capsule_high_approval_requires_human_gate() {
        let capsule = ComplianceCapsule::new(
            "Claude".to_string(),
            "3.5-sonnet".to_string(),
            ApprovalLevel::High,
        );

        assert!(capsule.human_gate_required);
    }

    #[test]
    fn test_add_safety_gate() {
        let mut capsule = ComplianceCapsule::new(
            "Claude".to_string(),
            "3.5-sonnet".to_string(),
            ApprovalLevel::Low,
        );

        capsule.add_safety_gate(SafetyGateResult {
            gate_type: SafetyGateType::XSSPrevention,
            passed: true,
            confidence: 0.99,
            reason: "No HTML/JS detected".to_string(),
        });

        assert_eq!(capsule.safety_gates.len(), 1);
        assert!(capsule.all_gates_passed());
    }

    #[test]
    fn test_gate_failure_blocks_execution() {
        let mut capsule = ComplianceCapsule::new(
            "Claude".to_string(),
            "3.5-sonnet".to_string(),
            ApprovalLevel::Low,
        );

        capsule.add_safety_gate(SafetyGateResult {
            gate_type: SafetyGateType::SQLInjectionPrevention,
            passed: false,
            confidence: 0.95,
            reason: "SQL injection pattern detected".to_string(),
        });

        assert!(!capsule.all_gates_passed());
    }

    #[test]
    fn test_execution_readiness_requires_merkle_proof() {
        let capsule = ComplianceCapsule::new(
            "Claude".to_string(),
            "3.5-sonnet".to_string(),
            ApprovalLevel::Low,
        );

        assert!(capsule.is_ready_for_execution().is_err());
    }

    #[test]
    fn test_execution_readiness_full_capsule() {
        let mut capsule = ComplianceCapsule::new(
            "Claude".to_string(),
            "3.5-sonnet".to_string(),
            ApprovalLevel::Low,
        );

        capsule.add_safety_gate(SafetyGateResult {
            gate_type: SafetyGateType::XSSPrevention,
            passed: true,
            confidence: 0.99,
            reason: "Clean".to_string(),
        });

        capsule.set_merkle_proof(
            "sha256:abc123".to_string(),
            "ed25519:sig456".to_string(),
        );

        capsule.set_audit_trail("sha256:def789".to_string());
        capsule.safe_policy_hash = "sha256:safe".to_string();

        assert!(capsule.is_ready_for_execution().is_ok());
    }
}
