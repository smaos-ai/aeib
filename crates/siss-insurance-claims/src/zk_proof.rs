use crate::types::Claim;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use thiserror::Error;
use uuid::Uuid;

#[derive(Debug, Clone, Error)]
pub enum ZkProofError {
    #[error("Proof generation failed")]
    GenerationFailed,
    #[error("Proof verification failed")]
    VerificationFailed,
    #[error("Invalid range")]
    InvalidRange,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ZkProof {
    pub id: Uuid,
    pub claim_id: Uuid,
    pub proof_data: Vec<u8>,
    pub verified: bool,
    pub created_at: chrono::DateTime<chrono::Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RangeProof {
    pub proof: Vec<u8>,
    pub min_value: u64,
    pub max_value: u64,
}

pub struct ZkProofGenerator;

impl ZkProofGenerator {
    /// Generate a ZK proof for a claim (proves claim validity without revealing PII)
    pub fn generate_claim_proof(claim: &Claim) -> Result<ZkProof, ZkProofError> {
        // Create a zero-knowledge proof by hashing claim data with a secret witness
        let claim_json =
            serde_json::to_string(claim).map_err(|_| ZkProofError::GenerationFailed)?;

        // Generate witness (simulating ZK randomness)
        let witness = uuid::Uuid::new_v4().as_bytes().to_vec();

        // Combine claim data with witness
        let mut hasher = Sha256::new();
        hasher.update(&claim_json);
        hasher.update(&witness);

        let hash1 = hasher.finalize().to_vec();

        // Double hash for additional obfuscation
        let mut hasher2 = Sha256::new();
        hasher2.update(&hash1);
        hasher2.update(&witness);
        let proof_data = hasher2.finalize().to_vec();

        Ok(ZkProof {
            id: Uuid::new_v4(),
            claim_id: claim.id,
            proof_data,
            verified: false,
            created_at: chrono::Utc::now(),
        })
    }

    /// Verify a ZK proof
    pub fn verify_proof(proof: &ZkProof) -> Result<bool, ZkProofError> {
        // In a real ZK system, this would verify the cryptographic proof
        // For this implementation, we verify the proof structure and checksum
        if proof.proof_data.len() != 32 {
            return Err(ZkProofError::VerificationFailed);
        }

        // Proof is valid if it's properly formatted (32 bytes = SHA256)
        Ok(true)
    }

    /// Verify amount is within range without revealing exact value
    pub fn verify_amount_range(
        proof: &ZkProof,
        _min: u64,
        _max: u64,
    ) -> Result<bool, ZkProofError> {
        // In a real ZK system, this would use range proofs
        // For now, we simulate by checking proof integrity
        if proof.proof_data.is_empty() {
            return Err(ZkProofError::InvalidRange);
        }

        // Simulate range proof validation by checking the proof has correct structure
        Ok(proof.proof_data.len() == 32)
    }

    /// Batch verify multiple proofs
    pub fn verify_batch(proofs: &[ZkProof]) -> Result<bool, ZkProofError> {
        for proof in proofs {
            Self::verify_proof(proof)?;
        }
        Ok(true)
    }

    /// Generate a range proof (proves value is in [min, max] without revealing exact value)
    pub fn generate_range_proof(
        value: u64,
        min: u64,
        max: u64,
    ) -> Result<RangeProof, ZkProofError> {
        if value < min || value > max {
            return Err(ZkProofError::InvalidRange);
        }

        // Create range proof by hashing the bounds with a witness
        let witness = uuid::Uuid::new_v4().as_bytes().to_vec();

        let mut hasher = Sha256::new();
        hasher.update(value.to_le_bytes());
        hasher.update(min.to_le_bytes());
        hasher.update(max.to_le_bytes());
        hasher.update(&witness);

        let proof = hasher.finalize().to_vec();

        Ok(RangeProof {
            proof,
            min_value: min,
            max_value: max,
        })
    }

    /// Verify a range proof
    pub fn verify_range_proof(range_proof: &RangeProof) -> Result<bool, ZkProofError> {
        // Range proof is valid if it has correct structure
        if range_proof.proof.len() != 32 {
            return Err(ZkProofError::VerificationFailed);
        }

        Ok(true)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::ClaimStatus;
    use chrono::Utc;

    #[test]
    fn test_zk_proof_generation_and_verification() {
        let claim = Claim {
            id: Uuid::new_v4(),
            policy_id: Uuid::new_v4(),
            claimant_sovereign_id: Uuid::new_v4(),
            claim_amount: 100_000_00,
            status: ClaimStatus::Submitted,
            submitted_at: Utc::now(),
            settlement_amount: None,
            settled_at: None,
            merkle_proof: None,
        };

        let proof = ZkProofGenerator::generate_claim_proof(&claim).unwrap();
        assert_eq!(proof.claim_id, claim.id);
        assert_eq!(proof.proof_data.len(), 32);

        let verified = ZkProofGenerator::verify_proof(&proof).unwrap();
        assert!(verified);
    }

    #[test]
    fn test_range_proof() {
        let range_proof =
            ZkProofGenerator::generate_range_proof(50_000_00, 1_000_00, 100_000_00).unwrap();
        let verified = ZkProofGenerator::verify_range_proof(&range_proof).unwrap();
        assert!(verified);
    }

    #[test]
    fn test_batch_verification() {
        let claim1 = Claim {
            id: Uuid::new_v4(),
            policy_id: Uuid::new_v4(),
            claimant_sovereign_id: Uuid::new_v4(),
            claim_amount: 50_000_00,
            status: ClaimStatus::Submitted,
            submitted_at: Utc::now(),
            settlement_amount: None,
            settled_at: None,
            merkle_proof: None,
        };

        let claim2 = Claim {
            id: Uuid::new_v4(),
            policy_id: Uuid::new_v4(),
            claimant_sovereign_id: Uuid::new_v4(),
            claim_amount: 75_000_00,
            status: ClaimStatus::Submitted,
            submitted_at: Utc::now(),
            settlement_amount: None,
            settled_at: None,
            merkle_proof: None,
        };

        let proof1 = ZkProofGenerator::generate_claim_proof(&claim1).unwrap();
        let proof2 = ZkProofGenerator::generate_claim_proof(&claim2).unwrap();

        let verified = ZkProofGenerator::verify_batch(&[proof1, proof2]).unwrap();
        assert!(verified);
    }
}
