use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum PhiClassification {
    PublicHealth,
    ProtectedHealth,
    SensitiveHealth,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PhiAccessEvent {
    pub timestamp: u64,
    pub accessor_id: String,
    pub reason: String,
    pub merkle_hash: String,
}

pub struct HHSCapsule {
    capsule_id: Uuid,
    phi_classification: PhiClassification,
    minimum_necessary_enforced: bool,
    access_log: Vec<PhiAccessEvent>,
    merkle_root: String,
    ed25519_signature: String,
}

impl HHSCapsule {
    pub fn new(phi_classification: PhiClassification) -> Self {
        Self {
            capsule_id: Uuid::new_v4(),
            phi_classification,
            minimum_necessary_enforced: false,
            access_log: vec![],
            merkle_root: String::new(),
            ed25519_signature: String::new(),
        }
    }

    pub fn enforce_minimum_necessary(&self) -> Result<(), String> {
        if self.minimum_necessary_enforced {
            Ok(())
        } else {
            Err("Minimum-necessary standard not enforced (HIPAA §164.502(b))".to_string())
        }
    }

    pub fn log_access(&mut self, accessor: String, reason: String) {
        let event = PhiAccessEvent {
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs(),
            accessor_id: accessor,
            reason,
            merkle_hash: String::new(),
        };
        self.access_log.push(event);
    }

    pub fn audit_trail(&self) -> &[PhiAccessEvent] {
        &self.access_log
    }

    pub fn is_ready_for_execution(&self) -> Result<(), String> {
        self.enforce_minimum_necessary()?;
        if self.merkle_root.is_empty() {
            return Err("Merkle root not set".to_string());
        }
        if self.ed25519_signature.is_empty() {
            return Err("ed25519 signature not set".to_string());
        }
        Ok(())
    }

    pub fn set_minimum_necessary_enforced(&mut self, value: bool) {
        self.minimum_necessary_enforced = value;
    }

    pub fn set_merkle_root(&mut self, root: String) {
        self.merkle_root = root;
    }

    pub fn set_ed25519_signature(&mut self, sig: String) {
        self.ed25519_signature = sig;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_phi_classification_ordering() {
        assert!(PhiClassification::PublicHealth < PhiClassification::ProtectedHealth);
        assert!(PhiClassification::ProtectedHealth < PhiClassification::SensitiveHealth);
    }

    #[test]
    fn test_minimum_necessary_enforcement() {
        let capsule = HHSCapsule::new(PhiClassification::ProtectedHealth);
        assert!(capsule.enforce_minimum_necessary().is_err());
    }

    #[test]
    fn test_access_logging() {
        let mut capsule = HHSCapsule::new(PhiClassification::ProtectedHealth);
        assert_eq!(capsule.audit_trail().len(), 0);
        capsule.log_access("user-123".to_string(), "Treatment".to_string());
        assert_eq!(capsule.audit_trail().len(), 1);
    }

    #[test]
    fn test_audit_trail_returns_immutable_log() {
        let mut capsule = HHSCapsule::new(PhiClassification::SensitiveHealth);
        capsule.log_access("auditor-1".to_string(), "Audit".to_string());
        let trail: &[PhiAccessEvent] = capsule.audit_trail();
        assert_eq!(trail.len(), 1);
        assert_eq!(trail[0].accessor_id, "auditor-1");
    }

    #[test]
    fn test_ready_requires_minimum_necessary() {
        let capsule = HHSCapsule::new(PhiClassification::ProtectedHealth);
        assert!(capsule.is_ready_for_execution().is_err());
    }
}
