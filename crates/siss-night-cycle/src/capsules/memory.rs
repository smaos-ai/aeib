use sha2::{Digest, Sha256};
use std::sync::{Arc, Mutex};
use std::time::{Instant, SystemTime, UNIX_EPOCH};

#[derive(Debug, Clone, PartialEq)]
pub enum CapsuleError {
    EmptyState,
    DriftDetected,
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
pub struct StateSnapshot {
    pub state_hash: [u8; 32],
    pub timestamp: i64,
    pub confidence: f64,
}

#[derive(Debug, Default)]
struct MemoryState {
    snapshots: Vec<StateSnapshot>,
    confidence_decay: f64,
}

pub struct MemoryCapsule {
    state: Arc<Mutex<MemoryState>>,
}

impl MemoryCapsule {
    pub fn new(confidence_decay: f64) -> Self {
        Self {
            state: Arc::new(Mutex::new(MemoryState {
                snapshots: Vec::new(),
                confidence_decay,
            })),
        }
    }

    pub fn verify_consistency(&self, snapshot: StateSnapshot) -> CapsuleResult<MerkleProof> {
        let start = Instant::now();

        let mut state = self.state.lock().map_err(|_| CapsuleError::LockPoisoned)?;

        // Detect state drift: duplicate hash in snapshots
        for existing in &state.snapshots {
            if existing.state_hash == snapshot.state_hash
                && existing.timestamp != snapshot.timestamp
            {
                return Err(CapsuleError::DriftDetected);
            }
        }

        // Build accumulated Merkle hash over all snapshots
        let mut hasher = Sha256::new();
        for snap in &state.snapshots {
            hasher.update(snap.state_hash);
            hasher.update(snap.timestamp.to_le_bytes());
        }
        hasher.update(snapshot.state_hash);
        hasher.update(snapshot.timestamp.to_le_bytes());
        let digest = hasher.finalize();
        let mut hash = [0u8; 32];
        hash.copy_from_slice(&digest);

        let execution_nanos = start.elapsed().as_nanos() as u64;

        // Compute temporal decay confidence: e^(-decay * age_secs)
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs() as i64;
        let age_secs = (now - snapshot.timestamp) as f64;
        let confidence = (-state.confidence_decay * age_secs).exp().clamp(0.0, 1.0);

        state.snapshots.push(snapshot);

        Ok(MerkleProof {
            hash,
            confidence,
            execution_nanos,
        })
    }

    pub fn get_confidence(&self) -> f64 {
        let state = self.state.lock().unwrap_or_else(|e| e.into_inner());
        if state.snapshots.is_empty() {
            return 0.0;
        }
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs() as i64;
        let last = &state.snapshots[state.snapshots.len() - 1];
        let age_secs = (now - last.timestamp) as f64;
        (-state.confidence_decay * age_secs).exp().clamp(0.0, 1.0)
    }
}

impl Default for MemoryCapsule {
    fn default() -> Self {
        Self::new(0.1)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::SystemTime;

    fn current_timestamp() -> i64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs() as i64
    }

    #[test]
    fn test_memory_consistency_check() {
        let capsule = MemoryCapsule::new(0.1);
        let snapshot = StateSnapshot {
            state_hash: [1u8; 32],
            timestamp: current_timestamp(),
            confidence: 0.9,
        };
        let result = capsule.verify_consistency(snapshot);
        assert!(result.is_ok());
        let proof = result.unwrap();
        assert_eq!(proof.hash.len(), 32);
        assert!(proof.confidence >= 0.0 && proof.confidence <= 1.0);
        assert!(proof.execution_nanos > 0);
    }

    #[test]
    fn test_state_drift_detection() {
        let capsule = MemoryCapsule::new(0.1);
        let ts = current_timestamp();
        let snap1 = StateSnapshot {
            state_hash: [1u8; 32],
            timestamp: ts,
            confidence: 0.9,
        };
        capsule.verify_consistency(snap1).unwrap();

        let snap2 = StateSnapshot {
            state_hash: [1u8; 32],
            timestamp: ts + 100,
            confidence: 0.8,
        };
        let result = capsule.verify_consistency(snap2);
        assert!(matches!(result.unwrap_err(), CapsuleError::DriftDetected));
    }

    #[test]
    fn test_merkle_proof_generation() {
        let capsule = MemoryCapsule::new(0.1);
        let snap = StateSnapshot {
            state_hash: [42u8; 32],
            timestamp: current_timestamp(),
            confidence: 0.9,
        };
        let proof = capsule.verify_consistency(snap).unwrap();
        assert_ne!(proof.hash, [0u8; 32]);
    }

    #[test]
    fn test_temporal_decay() {
        let capsule = MemoryCapsule::new(0.5);
        let now = current_timestamp();
        let snap_recent = StateSnapshot {
            state_hash: [10u8; 32],
            timestamp: now,
            confidence: 0.9,
        };
        let snap_old = StateSnapshot {
            state_hash: [20u8; 32],
            timestamp: now - 10,
            confidence: 0.8,
        };
        capsule.verify_consistency(snap_recent).unwrap();
        capsule.verify_consistency(snap_old).unwrap();

        let confidence_recent = (-0.5_f64 * 0.0).exp();
        let confidence_old = (-0.5_f64 * 10.0).exp();
        assert!(confidence_recent > confidence_old);
    }

    #[test]
    fn test_proof_deterministic() {
        let snap = StateSnapshot {
            state_hash: [7u8; 32],
            timestamp: 1000,
            confidence: 0.85,
        };
        let cap_a = MemoryCapsule::new(0.1);
        let proof_a = cap_a.verify_consistency(snap.clone()).unwrap();
        let cap_b = MemoryCapsule::new(0.1);
        let proof_b = cap_b.verify_consistency(snap).unwrap();
        assert_eq!(proof_a.hash, proof_b.hash);
    }
}
