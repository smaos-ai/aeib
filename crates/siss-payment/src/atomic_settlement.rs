use crate::settlement_builder::SettlementLeg;
use parking_lot::RwLock;
use sha2::{Digest, Sha256};
use std::sync::Arc;

#[derive(Debug, Clone)]
pub struct AtomicSettlement {
    pub legs: Arc<RwLock<Vec<SettlementLeg>>>,
    pub merkle_root: [u8; 32],
    pub committed: Arc<RwLock<bool>>,
}

impl AtomicSettlement {
    pub fn new(legs: Vec<SettlementLeg>) -> Result<Self, String> {
        let merkle_root = Self::compute_merkle_root(&legs);
        Ok(AtomicSettlement {
            legs: Arc::new(RwLock::new(legs)),
            merkle_root,
            committed: Arc::new(RwLock::new(false)),
        })
    }

    pub fn compute_merkle_root(legs: &[SettlementLeg]) -> [u8; 32] {
        let mut hasher = Sha256::new();
        for leg in legs {
            let leg_bytes = format!(
                "{}{}{}{}",
                leg.id, leg.from_currency, leg.to_currency, leg.amount_cents
            );
            hasher.update(leg_bytes.as_bytes());
        }
        let result = hasher.finalize();
        let mut root = [0u8; 32];
        root.copy_from_slice(&result);
        root
    }

    pub fn commit(&self) -> Result<(), String> {
        let mut committed = self.committed.write();
        if *committed {
            return Err("Already committed".to_string());
        }

        // Verify integrity before committing
        if !self.verify_integrity() {
            return Err("Integrity check failed".to_string());
        }

        *committed = true;
        Ok(())
    }

    pub fn verify_integrity(&self) -> bool {
        let legs = self.legs.read();
        let computed_root = Self::compute_merkle_root(&legs);
        computed_root == self.merkle_root
    }

    pub fn is_committed(&self) -> bool {
        *self.committed.read()
    }

    pub fn get_legs(&self) -> Vec<SettlementLeg> {
        self.legs.read().clone()
    }

    pub fn rollback(&self) -> Result<(), String> {
        let mut committed = self.committed.write();
        if !*committed {
            return Err("Not committed yet".to_string());
        }
        *committed = false;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use uuid::Uuid;

    #[test]
    fn test_merkle_root_computed() {
        let legs = vec![SettlementLeg {
            id: Uuid::new_v4(),
            from_currency: "EUR".to_string(),
            to_currency: "USD".to_string(),
            amount_cents: 10000,
            status: "pending".to_string(),
        }];

        let settlement = AtomicSettlement::new(legs).unwrap();
        assert_ne!(settlement.merkle_root, [0u8; 32]);
    }

    #[test]
    fn test_commitment() {
        let legs = vec![SettlementLeg {
            id: Uuid::new_v4(),
            from_currency: "EUR".to_string(),
            to_currency: "USD".to_string(),
            amount_cents: 10000,
            status: "pending".to_string(),
        }];

        let settlement = AtomicSettlement::new(legs).unwrap();
        assert!(!settlement.is_committed());

        settlement.commit().ok();
        assert!(settlement.is_committed());
    }

    #[test]
    fn test_merkle_root_uniqueness() {
        // TODO: Different legs produce different merkle roots
    }

    #[test]
    fn test_atomic_rollback_on_invalid() {
        // TODO: Invalid leg triggers full rollback
    }

    #[test]
    fn test_concurrent_settlements() {
        // TODO: 10 concurrent settlements, no corruption
    }
}
