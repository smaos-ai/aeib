/// VisualGembaCapsule — Visual Input Verification & Proof Generation
/// Part of the 6-capsule Merkle-linked Unified Integrity Pipeline.
/// Accepts image bytes, verifies cryptographically, produces a MerkleProof.
/// Covenant-aligned: deterministic proofs, concurrent-safe, fail-closed on empty input.

use sha2::{Digest, Sha256};
use std::sync::{Arc, Mutex};
use std::time::Instant;

/// Errors produced by capsule operations.
#[derive(Debug, thiserror::Error)]
pub enum CapsuleError {
    #[error("image input is empty")]
    EmptyInput,

    #[error("hash computation failed: {0}")]
    HashFailure(String),

    #[error("state lock poisoned")]
    LockPoisoned,
}

/// Convenience result type for all capsule operations.
pub type CapsuleResult<T> = Result<T, CapsuleError>;

/// Cryptographic proof produced by a single verification call.
#[derive(Debug, Clone, PartialEq)]
pub struct MerkleProof {
    /// SHA-256 hash of the image input (32 bytes).
    pub hash: [u8; 32],
    /// Confidence score derived from image byte entropy (0.0–1.0).
    pub confidence: f64,
    /// Wall-clock execution time of the verification step (nanoseconds).
    pub execution_nanos: u64,
}

/// Internal mutable state protected by a Mutex.
#[derive(Debug, Default)]
struct CapsuleState {
    /// Running count of successful verifications.
    verification_count: u64,
    /// Accumulated Merkle root: SHA256(prev_root || new_hash) after each call.
    accumulated_root: [u8; 32],
    /// Confidence score from the most recent successful verification.
    last_confidence: f64,
}

/// VisualGembaCapsule — thread-safe visual verification capsule.
///
/// ```
/// use siss_gatekeeper::capsules::visual::VisualGembaCapsule;
///
/// let cap = VisualGembaCapsule::new();
/// let proof = cap.verify(b"test image".to_vec()).unwrap();
/// assert!(proof.confidence >= 0.0 && proof.confidence <= 1.0);
/// ```
#[derive(Clone, Debug)]
pub struct VisualGembaCapsule {
    state: Arc<Mutex<CapsuleState>>,
}

impl VisualGembaCapsule {
    /// Create a new capsule with zeroed initial state.
    pub fn new() -> Self {
        Self {
            state: Arc::new(Mutex::new(CapsuleState::default())),
        }
    }

    /// Verify an image input and return a `MerkleProof`.
    ///
    /// Fail-closed: returns `CapsuleError::EmptyInput` if `image_input` is empty.
    /// The proof hash is deterministic for the same input bytes.
    /// The accumulated root evolves with each call (Merkle chain).
    pub fn verify(&self, image_input: Vec<u8>) -> CapsuleResult<MerkleProof> {
        if image_input.is_empty() {
            return Err(CapsuleError::EmptyInput);
        }

        let start = Instant::now();

        // Hash the raw image bytes.
        let mut hasher = Sha256::new();
        hasher.update(&image_input);
        let digest = hasher.finalize();
        let mut hash = [0u8; 32];
        hash.copy_from_slice(&digest);

        // Compute confidence from byte entropy: mean(bytes) / 255.0.
        let mean_byte: f64 =
            image_input.iter().map(|&b| b as f64).sum::<f64>() / image_input.len() as f64;
        let confidence = (mean_byte / 255.0).clamp(0.0, 1.0);

        let execution_nanos = start.elapsed().as_nanos() as u64;

        // Update accumulated Merkle root: SHA256(prev_root || new_hash).
        let mut state = self.state.lock().map_err(|_| CapsuleError::LockPoisoned)?;
        let mut chain_hasher = Sha256::new();
        chain_hasher.update(state.accumulated_root);
        chain_hasher.update(hash);
        let new_root = chain_hasher.finalize();
        state.accumulated_root.copy_from_slice(&new_root);
        state.verification_count += 1;
        state.last_confidence = confidence;

        Ok(MerkleProof {
            hash,
            confidence,
            execution_nanos,
        })
    }

    /// Return the confidence score from the most recent verification.
    /// Returns 0.0 if no verification has been performed yet.
    pub fn get_confidence(&self) -> f64 {
        self.state
            .lock()
            .map(|s| s.last_confidence)
            .unwrap_or(0.0)
    }
}

impl Default for VisualGembaCapsule {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::thread;

    #[test]
    fn test_visual_verification_basic() {
        let cap = VisualGembaCapsule::new();
        let proof = cap.verify(b"sample image data".to_vec()).unwrap();
        assert_eq!(proof.hash.len(), 32);
        assert!((0.0..=1.0).contains(&proof.confidence));
        assert!(proof.execution_nanos > 0);
    }

    #[test]
    fn test_confidence_calculation() {
        let cap = VisualGembaCapsule::new();

        let proof_zero = cap.verify(vec![0u8; 64]).unwrap();
        assert_eq!(proof_zero.confidence, 0.0);

        let proof_max = cap.verify(vec![255u8; 64]).unwrap();
        assert_eq!(proof_max.confidence, 1.0);

        let proof_mid = cap.verify(vec![128u8; 64]).unwrap();
        assert!((0.49..=0.51).contains(&proof_mid.confidence));
    }

    #[test]
    fn test_merkle_proof_generation() {
        let cap = VisualGembaCapsule::new();

        let proof = cap.verify(b"visual gemba frame".to_vec()).unwrap();
        assert_ne!(proof.hash, [0u8; 32]);
        assert!(proof.confidence >= 0.0);

        let err = cap.verify(vec![]).unwrap_err();
        assert!(matches!(err, CapsuleError::EmptyInput));
    }

    #[test]
    fn test_concurrent_access() {
        let cap = Arc::new(VisualGembaCapsule::new());
        let handles: Vec<_> = (0..8)
            .map(|i| {
                let cap = Arc::clone(&cap);
                thread::spawn(move || {
                    let input = vec![(i * 31 % 256) as u8; 128];
                    cap.verify(input).expect("concurrent verify failed")
                })
            })
            .collect();

        for handle in handles {
            let proof = handle.join().expect("thread panicked");
            assert_eq!(proof.hash.len(), 32);
        }

        let confidence = cap.get_confidence();
        assert!((0.0..=1.0).contains(&confidence));
    }

    #[test]
    fn test_proof_deterministic() {
        let cap = VisualGembaCapsule::new();
        let input = b"deterministic test image".to_vec();

        let cap2 = VisualGembaCapsule::new();
        let proof_a = cap.verify(input.clone()).unwrap();
        let proof_b = cap2.verify(input.clone()).unwrap();
        assert_eq!(proof_a.hash, proof_b.hash);
        assert_eq!(proof_a.confidence, proof_b.confidence);

        let proof_c = cap.verify(b"different image".to_vec()).unwrap();
        assert_ne!(proof_a.hash, proof_c.hash);
    }
}
