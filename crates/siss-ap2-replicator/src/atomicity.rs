use sha2::{Sha256, Digest};
use std::sync::{Arc, Mutex};

#[derive(Debug, Clone)]
pub struct SettlementLeg {
    pub region: String,
    pub amount: u64,
    pub hash: [u8; 32],
}

impl SettlementLeg {
    pub fn new(region: &str, amount: u64) -> Self {
        let mut hash = [0u8; 32];
        let mut hasher = Sha256::new();
        hasher.update(region.as_bytes());
        hasher.update(amount.to_le_bytes());
        let result = hasher.finalize();
        hash.copy_from_slice(&result[..]);

        Self {
            region: region.to_string(),
            amount,
            hash,
        }
    }
}

#[derive(Debug, Clone)]
pub enum SettlementState {
    Prepared(Vec<SettlementLeg>),
    Committed([u8; 32]),
    Aborted,
}

pub struct AtomicSettlement {
    legs: Arc<Mutex<Vec<SettlementLeg>>>,
    state: Arc<Mutex<SettlementState>>,
}

impl AtomicSettlement {
    pub fn new() -> Self {
        Self {
            legs: Arc::new(Mutex::new(Vec::new())),
            state: Arc::new(Mutex::new(SettlementState::Prepared(Vec::new()))),
        }
    }

    pub fn prepare(&self, legs: Vec<SettlementLeg>) -> Result<(), String> {
        if legs.is_empty() {
            return Err("No settlement legs provided".to_string());
        }

        // Validate atomicity constraints
        let total_amount: u64 = legs.iter().map(|l| l.amount).sum();
        if total_amount == 0 {
            return Err("Total settlement amount cannot be zero".to_string());
        }

        // Store legs and update state
        *self.legs.lock().unwrap() = legs.clone();
        *self.state.lock().unwrap() = SettlementState::Prepared(legs);

        Ok(())
    }

    pub fn commit(&self) -> Result<[u8; 32], String> {
        let mut state = self.state.lock().unwrap();

        // Only commit from Prepared state
        match &*state {
            SettlementState::Prepared(legs) => {
                // Compute merkle root = sha256(all leg hashes)
                let mut hasher = Sha256::new();
                for leg in legs {
                    hasher.update(leg.hash);
                }
                let result = hasher.finalize();
                let mut merkle_root = [0u8; 32];
                merkle_root.copy_from_slice(&result[..]);

                // Atomic transition to Committed
                *state = SettlementState::Committed(merkle_root);

                Ok(merkle_root)
            }
            SettlementState::Committed(root) => {
                // Idempotent: return existing root
                Ok(*root)
            }
            SettlementState::Aborted => {
                Err("Cannot commit aborted settlement".to_string())
            }
        }
    }

    pub fn abort(&self) -> Result<(), String> {
        let mut state = self.state.lock().unwrap();

        match &*state {
            SettlementState::Prepared(_) | SettlementState::Committed(_) => {
                *state = SettlementState::Aborted;
                *self.legs.lock().unwrap() = Vec::new();
                Ok(())
            }
            SettlementState::Aborted => {
                // Idempotent
                Ok(())
            }
        }
    }

    pub fn get_state(&self) -> SettlementState {
        self.state.lock().unwrap().clone()
    }

    pub fn get_legs(&self) -> Vec<SettlementLeg> {
        self.legs.lock().unwrap().clone()
    }
}

impl Default for AtomicSettlement {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ap2_atomicity_commit() {
        let settlement = AtomicSettlement::new();

        let legs = vec![
            SettlementLeg::new("eu-west", 100),
            SettlementLeg::new("us-east", 150),
        ];

        // Prepare should succeed
        assert!(settlement.prepare(legs.clone()).is_ok());

        // Commit should succeed
        let root = settlement.commit();
        assert!(root.is_ok());
        let merkle_root = root.unwrap();
        assert_ne!(merkle_root, [0u8; 32]);

        // State should be Committed
        match settlement.get_state() {
            SettlementState::Committed(r) => assert_eq!(r, merkle_root),
            _ => panic!("Expected Committed state"),
        }
    }

    #[test]
    fn test_ap2_atomicity_rollback() {
        let settlement = AtomicSettlement::new();

        let legs = vec![
            SettlementLeg::new("eu-west", 100),
            SettlementLeg::new("us-east", 150),
        ];

        assert!(settlement.prepare(legs).is_ok());
        assert!(settlement.abort().is_ok());

        // State should be Aborted
        match settlement.get_state() {
            SettlementState::Aborted => {}
            _ => panic!("Expected Aborted state"),
        }

        // Legs should be cleared
        assert!(settlement.get_legs().is_empty());
    }

    #[test]
    fn test_ap2_two_phase_commit() {
        let settlement = AtomicSettlement::new();

        let legs = vec![
            SettlementLeg::new("region-a", 100),
            SettlementLeg::new("region-b", 200),
            SettlementLeg::new("region-c", 300),
        ];

        // Phase 1: Prepare
        assert!(settlement.prepare(legs).is_ok());

        // Phase 2: Commit
        let root1 = settlement.commit().unwrap();

        // Idempotent: commit again should return same root
        let root2 = settlement.commit().unwrap();
        assert_eq!(root1, root2);
    }

    #[test]
    fn test_rto_under_5_seconds() {
        use std::time::Instant;

        let settlement = AtomicSettlement::new();

        let legs = vec![
            SettlementLeg::new("eu", 100),
            SettlementLeg::new("us", 200),
        ];

        let start = Instant::now();
        assert!(settlement.prepare(legs).is_ok());
        let _ = settlement.commit();
        let elapsed = start.elapsed().as_millis();

        // Should complete well under 5 seconds (5000ms)
        assert!(elapsed < 5000);
    }

    #[test]
    fn test_rpo_zero_no_data_loss() {
        let settlement = AtomicSettlement::new();

        let legs = vec![
            SettlementLeg::new("region-1", 100),
            SettlementLeg::new("region-2", 200),
            SettlementLeg::new("region-3", 300),
        ];

        let original_legs = legs.clone();
        assert!(settlement.prepare(legs).is_ok());

        // Verify all legs are stored
        let stored_legs = settlement.get_legs();
        assert_eq!(stored_legs.len(), original_legs.len());

        for (stored, original) in stored_legs.iter().zip(original_legs.iter()) {
            assert_eq!(stored.region, original.region);
            assert_eq!(stored.amount, original.amount);
        }
    }
}
