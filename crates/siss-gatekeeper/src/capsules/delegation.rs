use sha2::{Digest, Sha256};
use std::sync::{Arc, Mutex};
use std::time::Instant;

#[derive(Debug, Clone, PartialEq)]
pub enum CapsuleError {
    EmptyChain,
    BrokenLink,
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
pub struct DelegationLink {
    pub delegator: String,
    pub delegatee: String,
    pub scope: String,
    pub timestamp: i64,
}

#[derive(Debug, Default)]
struct DelegationState {
    chain: Vec<DelegationLink>,
    root_issuer: String,
    last_hash: [u8; 32],
}

pub struct DelegationCapsule {
    state: Arc<Mutex<DelegationState>>,
}

impl DelegationCapsule {
    pub fn new(root_issuer: String) -> Self {
        Self {
            state: Arc::new(Mutex::new(DelegationState {
                chain: Vec::new(),
                root_issuer,
                last_hash: [0u8; 32],
            })),
        }
    }

    pub fn verify_chain(&self, chain: Vec<DelegationLink>) -> CapsuleResult<MerkleProof> {
        if chain.is_empty() {
            return Err(CapsuleError::EmptyChain);
        }

        let start = Instant::now();

        let mut state = self.state.lock().map_err(|_| CapsuleError::LockPoisoned)?;

        // Verify chain continuity: each link's delegator must match previous delegatee
        for (i, link) in chain.iter().enumerate() {
            if i == 0 {
                if link.delegator != state.root_issuer {
                    return Err(CapsuleError::BrokenLink);
                }
            } else if link.delegator != chain[i - 1].delegatee {
                return Err(CapsuleError::BrokenLink);
            }
        }

        // Compute hash over all fields in order
        let mut hasher = Sha256::new();
        for link in &chain {
            hasher.update(link.delegator.as_bytes());
            hasher.update(b"|");
            hasher.update(link.delegatee.as_bytes());
            hasher.update(b"|");
            hasher.update(link.scope.as_bytes());
            hasher.update(b"|");
            hasher.update(link.timestamp.to_le_bytes());
        }
        let digest = hasher.finalize();
        let mut hash = [0u8; 32];
        hash.copy_from_slice(&digest);

        let execution_nanos = start.elapsed().as_nanos() as u64;
        let chain_length = chain.len() as f64;
        let confidence = chain_length / (chain_length + 1.0);

        state.chain = chain;
        state.last_hash = hash;

        Ok(MerkleProof {
            hash,
            confidence,
            execution_nanos,
        })
    }

    pub fn get_confidence(&self) -> f64 {
        let state = self.state.lock().unwrap_or_else(|e| e.into_inner());
        if state.chain.is_empty() {
            return 0.0;
        }
        let len = state.chain.len() as f64;
        len / (len + 1.0)
    }
}

impl Default for DelegationCapsule {
    fn default() -> Self {
        Self::new("root".to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_delegation_chain_valid() {
        let capsule = DelegationCapsule::new("alice".to_string());
        let chain = vec![
            DelegationLink {
                delegator: "alice".to_string(),
                delegatee: "bob".to_string(),
                scope: "write".to_string(),
                timestamp: 1000,
            },
            DelegationLink {
                delegator: "bob".to_string(),
                delegatee: "charlie".to_string(),
                scope: "read".to_string(),
                timestamp: 2000,
            },
        ];
        let result = capsule.verify_chain(chain);
        assert!(result.is_ok());
        let proof = result.unwrap();
        assert_eq!(proof.hash.len(), 32);
        assert!(proof.confidence > 0.0 && proof.confidence <= 1.0);
        assert!(proof.execution_nanos > 0);
    }

    #[test]
    fn test_chain_broken_link_detected() {
        let capsule = DelegationCapsule::new("alice".to_string());
        let chain = vec![
            DelegationLink {
                delegator: "alice".to_string(),
                delegatee: "bob".to_string(),
                scope: "write".to_string(),
                timestamp: 1000,
            },
            DelegationLink {
                delegator: "eve".to_string(),
                delegatee: "charlie".to_string(),
                scope: "read".to_string(),
                timestamp: 2000,
            },
        ];
        let result = capsule.verify_chain(chain);
        assert!(matches!(result.unwrap_err(), CapsuleError::BrokenLink));
    }

    #[test]
    fn test_merkle_proof_generation() {
        let capsule = DelegationCapsule::new("root".to_string());
        let chain = vec![DelegationLink {
            delegator: "root".to_string(),
            delegatee: "user1".to_string(),
            scope: "admin".to_string(),
            timestamp: 1000,
        }];
        let proof = capsule.verify_chain(chain).unwrap();
        assert_ne!(proof.hash, [0u8; 32]);
        let err = capsule.verify_chain(vec![]).unwrap_err();
        assert_eq!(err, CapsuleError::EmptyChain);
    }

    #[test]
    fn test_concurrent_verifications() {
        let capsule = Arc::new(DelegationCapsule::new("root".to_string()));
        let handles: Vec<_> = (0..4)
            .map(|i| {
                let cap = Arc::clone(&capsule);
                std::thread::spawn(move || {
                    let chain = vec![DelegationLink {
                        delegator: "root".to_string(),
                        delegatee: format!("user{}", i),
                        scope: "read".to_string(),
                        timestamp: 1000 + i as i64,
                    }];
                    cap.verify_chain(chain)
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
        let chain = vec![DelegationLink {
            delegator: "alice".to_string(),
            delegatee: "bob".to_string(),
            scope: "read".to_string(),
            timestamp: 1000,
        }];
        let cap_a = DelegationCapsule::new("alice".to_string());
        let proof_a = cap_a.verify_chain(chain.clone()).unwrap();
        let cap_b = DelegationCapsule::new("alice".to_string());
        let proof_b = cap_b.verify_chain(chain).unwrap();
        assert_eq!(proof_a.hash, proof_b.hash);
    }
}
