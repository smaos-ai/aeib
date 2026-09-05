use sha2::{Digest, Sha256};
use std::sync::{Arc, Mutex};
use std::time::Instant;

#[derive(Debug, Clone, PartialEq)]
pub enum CapsuleError {
    InvalidSettlement,
    AP2ViolationError,
    LockPoisoned,
}

pub type CapsuleResult<T> = Result<T, CapsuleError>;

#[derive(Debug, Clone, PartialEq)]
pub struct MerkleProof {
    pub hash: [u8; 32],
    pub confidence: f64,
    pub execution_nanos: u64,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Settlement {
    pub creator_id: String,
    pub amount: u64,
    pub timestamp: i64,
    pub proof_hash: [u8; 32],
}

#[derive(Debug, Default)]
struct EconomicState {
    ledger: Vec<Settlement>,
    total_value: u64,
    ai_total: u64,
    human_total: u64,
}

pub struct EconomicCapsule {
    state: Arc<Mutex<EconomicState>>,
}

impl EconomicCapsule {
    pub fn new() -> Self {
        Self {
            state: Arc::new(Mutex::new(EconomicState::default())),
        }
    }

    pub fn verify_settlement(&self, settlement: Settlement) -> CapsuleResult<MerkleProof> {
        let start = Instant::now();

        let mut state = self.state.lock().map_err(|_| CapsuleError::LockPoisoned)?;

        let amount = settlement.amount;
        if amount == 0 {
            return Err(CapsuleError::InvalidSettlement);
        }

        // Hash: creator_id || amount_le || timestamp_le || proof_hash
        let mut hasher = Sha256::new();
        hasher.update(settlement.creator_id.as_bytes());
        hasher.update(b"|");
        hasher.update(amount.to_le_bytes());
        hasher.update(b"|");
        hasher.update(settlement.timestamp.to_le_bytes());
        hasher.update(b"|");
        hasher.update(settlement.proof_hash);
        let digest = hasher.finalize();
        let mut hash = [0u8; 32];
        hash.copy_from_slice(&digest);

        let execution_nanos = start.elapsed().as_nanos() as u64;

        // AP2 enforcement: 1%/99% split (AI gets 1%, human gets 99%)
        let ai_share = amount / 100;
        let human_share = amount - ai_share;

        state.total_value += amount;
        state.ledger.push(settlement);
        state.ai_total += ai_share;
        state.human_total += human_share;

        // Validate AP2 split invariant
        if state.ai_total + state.human_total != state.total_value {
            return Err(CapsuleError::AP2ViolationError);
        }

        let confidence = if state.ledger.is_empty() {
            0.0
        } else {
            1.0 - (state.ledger.len() as f64 * 0.01).min(1.0)
        };

        Ok(MerkleProof {
            hash,
            confidence,
            execution_nanos,
        })
    }

    pub fn validate_ap2_split(&self) -> CapsuleResult<()> {
        let state = self.state.lock().map_err(|_| CapsuleError::LockPoisoned)?;
        if state.ai_total + state.human_total == state.total_value {
            Ok(())
        } else {
            Err(CapsuleError::AP2ViolationError)
        }
    }

    pub fn get_confidence(&self) -> f64 {
        let state = self.state.lock().unwrap_or_else(|e| e.into_inner());
        if state.ledger.is_empty() {
            return 0.0;
        }
        1.0 - (state.ledger.len() as f64 * 0.01).min(1.0)
    }
}

impl Default for EconomicCapsule {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::SystemTime;

    fn current_timestamp() -> i64 {
        SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs() as i64
    }

    #[test]
    fn test_settlement_verification() {
        let capsule = EconomicCapsule::new();
        let settlement = Settlement {
            creator_id: "alice".to_string(),
            amount: 10000,
            timestamp: current_timestamp(),
            proof_hash: [42u8; 32],
        };
        let result = capsule.verify_settlement(settlement);
        assert!(result.is_ok());
        let proof = result.unwrap();
        assert_eq!(proof.hash.len(), 32);
        assert!(proof.confidence >= 0.0 && proof.confidence <= 1.0);
    }

    #[test]
    fn test_ap2_split_enforcement() {
        let capsule = EconomicCapsule::new();
        let settlement = Settlement {
            creator_id: "bob".to_string(),
            amount: 10000,
            timestamp: current_timestamp(),
            proof_hash: [11u8; 32],
        };
        capsule.verify_settlement(settlement).unwrap();
        let validation = capsule.validate_ap2_split();
        assert!(validation.is_ok());
    }

    #[test]
    fn test_merkle_proof_generation() {
        let capsule = EconomicCapsule::new();
        let settlement = Settlement {
            creator_id: "charlie".to_string(),
            amount: 5000,
            timestamp: current_timestamp(),
            proof_hash: [99u8; 32],
        };
        let proof = capsule.verify_settlement(settlement).unwrap();
        assert_ne!(proof.hash, [0u8; 32]);
    }

    #[test]
    fn test_concurrent_settlements() {
        let capsule = Arc::new(EconomicCapsule::new());
        let handles: Vec<_> = (0..4)
            .map(|i| {
                let cap = Arc::clone(&capsule);
                std::thread::spawn(move || {
                    let settlement = Settlement {
                        creator_id: format!("creator_{}", i),
                        amount: 1000 + i as u64 * 100,
                        timestamp: current_timestamp(),
                        proof_hash: [i as u8; 32],
                    };
                    cap.verify_settlement(settlement)
                })
            })
            .collect();

        for handle in handles {
            let result = handle.join().expect("thread panicked");
            assert!(result.is_ok());
        }
    }

    #[test]
    fn test_proof_deterministic() {
        let settlement = Settlement {
            creator_id: "dave".to_string(),
            amount: 2000,
            timestamp: 1000,
            proof_hash: [77u8; 32],
        };
        let cap_a = EconomicCapsule::new();
        let proof_a = cap_a.verify_settlement(settlement.clone()).unwrap();

        let cap_b = EconomicCapsule::new();
        let proof_b = cap_b.verify_settlement(settlement).unwrap();

        assert_eq!(proof_a.hash, proof_b.hash);
    }
}
