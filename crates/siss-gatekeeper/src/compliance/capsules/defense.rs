use uuid::Uuid;
use serde::{Deserialize, Serialize};

/// Classification levels in ascending clearance order.
/// Derived Ord uses declaration order: Unclassified=0 < CUI=1 < Secret=2 < TopSecret=3 < TopSecretSCI=4
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum ClassificationLevel {
    Unclassified,
    CUI,
    Secret,
    TopSecret,
    TopSecretSCI,
}

/// Defense-domain compliance capsule with export-control enforcement.
pub struct DefenseCapsule {
    capsule_id: Uuid,
    classification_level: ClassificationLevel,
    pub export_control_passed: bool,
    model_provenance_hash: String,
    merkle_root: String,
    ed25519_signature: String,
    compliance_claims: Vec<String>,
}

impl DefenseCapsule {
    pub fn new(classification_level: ClassificationLevel) -> Self {
        Self {
            capsule_id: Uuid::new_v4(),
            classification_level,
            export_control_passed: false,
            model_provenance_hash: String::new(),
            merkle_root: String::new(),
            ed25519_signature: String::new(),
            compliance_claims: vec![],
        }
    }

    /// Returns Ok if user holds clearance >= capsule classification.
    pub fn verify_clearance(&self, user_clearance: ClassificationLevel) -> Result<(), String> {
        if user_clearance >= self.classification_level {
            Ok(())
        } else {
            Err(format!(
                "Insufficient clearance: user={:?}, required={:?}",
                user_clearance, self.classification_level
            ))
        }
    }

    /// Returns Ok only if export control check has passed.
    pub fn check_export_control(&self) -> Result<(), String> {
        if self.export_control_passed {
            Ok(())
        } else {
            Err("Export control not cleared (ITAR/EAR violation risk)".to_string())
        }
    }

    /// Returns Ok only when all execution pre-conditions are satisfied:
    /// clearance irrelevant here — caller must invoke verify_clearance separately.
    /// Checks: export control passed, merkle_root set, ed25519_signature set.
    pub fn is_ready_for_execution(&self) -> Result<(), String> {
        self.check_export_control()?;

        if self.merkle_root.is_empty() {
            return Err("Merkle root not set".to_string());
        }

        if self.ed25519_signature.is_empty() {
            return Err("ed25519 signature not set".to_string());
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_classification_ordering() {
        assert!(ClassificationLevel::Unclassified < ClassificationLevel::CUI);
        assert!(ClassificationLevel::CUI < ClassificationLevel::Secret);
        assert!(ClassificationLevel::Secret < ClassificationLevel::TopSecret);
        assert!(ClassificationLevel::TopSecret < ClassificationLevel::TopSecretSCI);
    }

    #[test]
    fn test_insufficient_clearance_blocks() {
        let capsule = DefenseCapsule::new(ClassificationLevel::Secret);
        let result = capsule.verify_clearance(ClassificationLevel::CUI);
        assert!(result.is_err());
    }

    #[test]
    fn test_sufficient_clearance_passes() {
        let capsule = DefenseCapsule::new(ClassificationLevel::Secret);
        let result = capsule.verify_clearance(ClassificationLevel::TopSecret);
        assert!(result.is_ok());
    }

    #[test]
    fn test_export_control_violation() {
        let capsule = DefenseCapsule::new(ClassificationLevel::Unclassified);
        assert!(capsule.check_export_control().is_err());
    }

    #[test]
    fn test_ready_requires_merkle() {
        let mut capsule = DefenseCapsule::new(ClassificationLevel::Unclassified);
        capsule.export_control_passed = true;
        assert!(capsule.is_ready_for_execution().is_err());
    }
}
