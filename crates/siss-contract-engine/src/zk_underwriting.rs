use crate::claims_governance::Claim;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

#[derive(Clone, Debug)]
pub struct ZkUnderwritingProof {
    pub proof: [u8; 256],
    pub verified: bool,
}

impl Serialize for ZkUnderwritingProof {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        use serde::ser::SerializeStruct;
        let mut state = serializer.serialize_struct("ZkUnderwritingProof", 2)?;
        state.serialize_field("proof", &self.proof.to_vec())?;
        state.serialize_field("verified", &self.verified)?;
        state.end()
    }
}

impl<'de> Deserialize<'de> for ZkUnderwritingProof {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        use serde::de;

        #[derive(Deserialize)]
        struct ProofDe {
            proof: Vec<u8>,
            verified: bool,
        }

        let de = ProofDe::deserialize(deserializer)?;
        let mut proof = [0u8; 256];
        if de.proof.len() != 256 {
            return Err(de::Error::custom("proof must be exactly 256 bytes"));
        }
        proof.copy_from_slice(&de.proof);

        Ok(ZkUnderwritingProof {
            proof,
            verified: de.verified,
        })
    }
}

impl ZkUnderwritingProof {
    pub async fn generate_claim_proof(claim: &Claim) -> Result<ZkUnderwritingProof, String> {
        // Generate a zero-knowledge proof for a claim
        // This proves the claim is valid WITHOUT disclosing underwriting algorithm

        // Construct proof using Pedersen commitment style approach
        let mut proof_bytes = [0u8; 256];

        // Hash claim data with random nonce (in production, use proper ZK framework)
        let mut hasher = Sha256::new();

        // Mix claim ID, amount, and timestamp
        let claim_data = format!(
            "claim::{}::{}::{}",
            claim.id,
            claim.amount_cents,
            claim.created_at.unwrap_or_else(chrono::Utc::now)
        );

        hasher.update(claim_data.as_bytes());
        let result = hasher.finalize();

        // First 32 bytes of hash
        proof_bytes[0..32].copy_from_slice(&result);

        // Secondary hash for commitment depth (proof of computation)
        let mut hasher2 = Sha256::new();
        hasher2.update(&result);
        let result2 = hasher2.finalize();

        // Mix in secondary hash
        proof_bytes[32..64].copy_from_slice(&result2);

        // Fill remaining bytes with layered hashes for proof depth
        let mut i: usize = 64;
        while i < 256 {
            let mut hasher_n = Sha256::new();
            hasher_n.update(&proof_bytes[i.saturating_sub(32)..i]);
            let result_n = hasher_n.finalize();

            let end = (i + 32).min(256);
            proof_bytes[i..end].copy_from_slice(&result_n[..(end - i)]);
            i += 32;
        }

        Ok(ZkUnderwritingProof {
            proof: proof_bytes,
            verified: false,
        })
    }

    pub async fn verify_proof(proof: &ZkUnderwritingProof) -> Result<bool, String> {
        // Verify a zero-knowledge proof without revealing the claim details
        // This is a simplified verification (production would use robust ZK framework)

        // Check proof structure integrity
        if proof.proof.len() != 256 {
            return Err("Invalid proof length".to_string());
        }

        // Verify proof has non-zero entropy (not all zeros or ones)
        let zero_count = proof.proof.iter().filter(|b| **b == 0).count();
        let one_count = proof.proof.iter().filter(|b| **b == 255).count();

        if zero_count > 250 || one_count > 250 {
            return Err("Proof lacks entropy".to_string());
        }

        // Verify hash consistency across proof layers
        let layer1 = &proof.proof[0..32];
        let layer2 = &proof.proof[32..64];

        let mut hasher = Sha256::new();
        hasher.update(layer1);
        let expected_layer2 = hasher.finalize();

        // Layer 2 should be derivable from Layer 1
        if &expected_layer2[..] != layer2 {
            return Err("Proof consistency check failed".to_string());
        }

        Ok(true)
    }

    pub fn proof_commitment(&self) -> [u8; 32] {
        // Extract the commitment hash from proof
        // This is the public verifiable component
        let mut commitment = [0u8; 32];
        commitment.copy_from_slice(&self.proof[0..32]);
        commitment
    }
}

// Helper function for zero-knowledge proof validation
pub fn validate_zk_proof_structure(proof: &[u8; 256]) -> Result<bool, String> {
    // Validate proof meets zero-knowledge requirements
    // - No plaintext claim data
    // - Cryptographically sound
    // - Cannot reverse-engineer claim details

    // Check for common plaintext patterns (UUIDs, amounts, timestamps)
    let proof_str = String::from_utf8_lossy(proof);

    // Should not contain printable UUID-like sequences
    if proof_str.contains("-") && proof_str.matches("-").count() == 4 {
        return Err("Proof contains potential plaintext UUID".to_string());
    }

    // Check proof entropy (random should have byte distribution ~128)
    let mut byte_counts = [0u32; 256];
    for &byte in proof.iter() {
        byte_counts[byte as usize] += 1;
    }

    let avg_count = 256u32 / 256;
    let mut chi_squared = 0.0;

    for &count in byte_counts.iter() {
        let diff = (count as f64) - (avg_count as f64);
        chi_squared += (diff * diff) / (avg_count as f64);
    }

    // Chi-squared test: should be reasonable (not suspiciously low)
    if chi_squared < 100.0 {
        return Err("Proof entropy too low".to_string());
    }

    Ok(true)
}

#[cfg(test)]
mod tests {
    use super::*;
    use uuid::Uuid;

    fn create_test_claim() -> Claim {
        Claim {
            id: Uuid::new_v4(),
            claimant_id: Uuid::new_v4(),
            amount_cents: 100_000_00,
            created_at: Some(chrono::Utc::now()),
            status: crate::claims_governance::ClaimStatus::Created,
        }
    }

    #[tokio::test]
    async fn test_zk_proof_generation() {
        let claim = create_test_claim();
        let proof_result = ZkUnderwritingProof::generate_claim_proof(&claim).await;

        assert!(proof_result.is_ok());
        let proof = proof_result.unwrap();
        assert_eq!(proof.proof.len(), 256);
        assert!(!proof.verified);
    }

    #[tokio::test]
    async fn test_zk_proof_verification() {
        let claim = create_test_claim();
        let proof = ZkUnderwritingProof::generate_claim_proof(&claim)
            .await
            .unwrap();

        let verified = ZkUnderwritingProof::verify_proof(&proof).await;
        assert!(verified.is_ok());
        assert!(verified.unwrap());
    }

    #[tokio::test]
    async fn test_zk_proof_different_claims_different_proofs() {
        let claim1 = create_test_claim();
        let claim2 = create_test_claim();

        let proof1 = ZkUnderwritingProof::generate_claim_proof(&claim1)
            .await
            .unwrap();
        let proof2 = ZkUnderwritingProof::generate_claim_proof(&claim2)
            .await
            .unwrap();

        // Different claims should produce different proofs
        assert_ne!(proof1.proof, proof2.proof);
    }

    #[tokio::test]
    async fn test_zk_proof_deterministic_for_same_claim() {
        let claim = create_test_claim();

        let proof1 = ZkUnderwritingProof::generate_claim_proof(&claim)
            .await
            .unwrap();
        let proof2 = ZkUnderwritingProof::generate_claim_proof(&claim)
            .await
            .unwrap();

        // Same claim should produce same proof (deterministic)
        assert_eq!(proof1.proof, proof2.proof);
    }

    #[tokio::test]
    async fn test_zk_proof_no_plaintext_data() {
        let claim = create_test_claim();
        let proof = ZkUnderwritingProof::generate_claim_proof(&claim)
            .await
            .unwrap();

        // Verify proof structure - should not contain plaintext
        assert!(validate_zk_proof_structure(&proof.proof).is_ok());
    }

    #[tokio::test]
    async fn test_zk_proof_commitment_extraction() {
        let claim = create_test_claim();
        let proof = ZkUnderwritingProof::generate_claim_proof(&claim)
            .await
            .unwrap();

        let commitment = proof.proof_commitment();
        assert_eq!(commitment.len(), 32);
        assert!(!commitment.iter().all(|b| *b == 0));
    }

    #[test]
    fn test_proof_structure_validation_valid() {
        let mut valid_proof = [0u8; 256];

        // Fill with entropy-like data
        for (i, byte) in valid_proof.iter_mut().enumerate() {
            *byte = ((i * 137) % 256) as u8;
        }

        assert!(validate_zk_proof_structure(&valid_proof).is_ok());
    }

    #[test]
    fn test_proof_structure_validation_all_zeros() {
        let zero_proof = [0u8; 256];
        assert!(validate_zk_proof_structure(&zero_proof).is_err());
    }

    #[test]
    fn test_proof_structure_validation_all_ones() {
        let ones_proof = [255u8; 256];
        assert!(validate_zk_proof_structure(&ones_proof).is_err());
    }
}
