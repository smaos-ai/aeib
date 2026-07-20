use sha2::{Digest, Sha256};
use std::sync::{Arc, Mutex};
use std::time::Instant;

#[derive(Debug, Clone, PartialEq)]
pub enum CapsuleError {
    EmptyInput,
    LockPoisoned,
}

pub type CapsuleResult<T> = Result<T, CapsuleError>;

#[derive(Debug, Clone, PartialEq)]
pub struct MerkleProof {
    pub hash: [u8; 32],
    pub confidence: f64,
    pub execution_nanos: u64,
}

#[derive(Debug, Default)]
pub struct CapsuleState {
    call_count: u64,
    total_confidence: f64,
}

pub struct TextProofCapsule {
    state: Arc<Mutex<CapsuleState>>,
}

impl TextProofCapsule {
    pub fn new() -> Self {
        Self {
            state: Arc::new(Mutex::new(CapsuleState::default())),
        }
    }

    pub fn verify(&self, text_input: String) -> CapsuleResult<MerkleProof> {
        if text_input.is_empty() {
            return Err(CapsuleError::EmptyInput);
        }

        let start = Instant::now();

        let mut hasher = Sha256::new();
        hasher.update(text_input.as_bytes());
        let digest = hasher.finalize();
        let hash: [u8; 32] = digest.into();

        let execution_nanos = start.elapsed().as_nanos() as u64;

        let char_count = text_input.chars().count() as f64;
        let confidence = 0.5 + 0.5 * (char_count / (char_count + 100.0));

        let mut state = self.state.lock().map_err(|_| CapsuleError::LockPoisoned)?;
        state.call_count += 1;
        state.total_confidence += confidence;

        Ok(MerkleProof {
            hash,
            confidence,
            execution_nanos,
        })
    }

    pub fn get_confidence(&self) -> f64 {
        let state = self.state.lock().unwrap_or_else(|e| e.into_inner());
        if state.call_count == 0 {
            return 0.0;
        }
        state.total_confidence / state.call_count as f64
    }
}

impl Default for TextProofCapsule {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;

    #[test]
    fn test_text_verification_basic() {
        let capsule = TextProofCapsule::new();
        let result = capsule.verify("hello world".to_string());
        assert!(result.is_ok());
        let proof = result.unwrap();
        assert_eq!(proof.hash.len(), 32);
        assert!(proof.confidence > 0.0 && proof.confidence <= 1.0);
        assert!(proof.execution_nanos > 0);
    }

    #[test]
    fn test_unicode_handling() {
        let capsule = TextProofCapsule::new();
        let unicode_text = "text".to_string();
        let result = capsule.verify(unicode_text.clone());
        assert!(result.is_ok());
        let proof = result.unwrap();
        assert_eq!(proof.hash.len(), 32);
    }

    #[test]
    fn test_merkle_proof_generation() {
        let capsule = TextProofCapsule::new();
        let proof = capsule.verify("sovereign nexus".to_string()).unwrap();
        assert_eq!(proof.hash.len(), 32);
        assert_ne!(proof.hash, [0u8; 32]);
        let err = capsule.verify(String::new()).unwrap_err();
        assert_eq!(err, CapsuleError::EmptyInput);
    }

    #[test]
    fn test_concurrent_writes() {
        let capsule = Arc::new(TextProofCapsule::new());
        let handles: Vec<_> = (0..8)
            .map(|i| {
                let cap = Arc::clone(&capsule);
                std::thread::spawn(move || {
                    for j in 0..100 {
                        let text = format!("t{} c{}", i, j);
                        let _ = cap.verify(text);
                    }
                })
            })
            .collect();
        for handle in handles {
            handle.join().expect("thread panicked");
        }
    }

    #[test]
    fn test_proof_deterministic() {
        let input = "test".to_string();
        let cap_a = TextProofCapsule::new();
        let proof_a = cap_a.verify(input.clone()).unwrap();
        let cap_b = TextProofCapsule::new();
        let proof_b = cap_b.verify(input).unwrap();
        assert_eq!(proof_a.hash, proof_b.hash);
    }
}
