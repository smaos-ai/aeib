use uuid::Uuid;
use serde::{Serialize, Deserialize};
use sha2::{Sha256, Digest};
use std::collections::HashMap;

/// A transformation in the ontology graph
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GraphTransformation {
    pub source_entity: Uuid,
    pub target_entity: Uuid,
    pub edge_type: String,
    pub timestamp_utc: String,
    pub metadata: HashMap<String, String>,
}

/// The projection result after applying a transformation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectionResult {
    pub projection_id: Uuid,
    pub confidence: f64,
    pub outcome: String,
    pub justification: String,
}

/// Cryptographic binding for a proof
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProofCryptography {
    pub proof_hash: String,
    pub signing_agent: Uuid,
}

/// A complete π++ proof object
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProofObject {
    pub proof_id: Uuid,
    pub transformation: GraphTransformation,
    pub justification: ProjectionResult,
    pub attestation: String,
    pub cryptography: ProofCryptography,
}

/// The π++ (Pi Plus Plus) proof engine
pub struct PiPlusPlusEngine {
    agent_id: Uuid,
    confidence_threshold: f64,
}

impl PiPlusPlusEngine {
    pub fn new(_signing_key: Vec<u8>, agent_id: Uuid) -> Self {
        PiPlusPlusEngine {
            agent_id,
            confidence_threshold: 0.8,
        }
    }

    /// Compute canonical SHA256 hash over transformation + justification + attestation
    fn compute_proof_hash(
        transformation: &GraphTransformation,
        justification: &ProjectionResult,
        attestation: &str,
    ) -> String {
        let t_json = serde_json::to_string(transformation)
            .expect("transformation serialization must succeed");
        let j_json = serde_json::to_string(justification)
            .expect("justification serialization must succeed");
        let canonical = format!("{}|{}|{}", t_json, j_json, attestation);
        let mut hasher = Sha256::new();
        hasher.update(canonical.as_bytes());
        let result = hasher.finalize();
        hex::encode(result)
    }

    pub fn generate_proof(
        &self,
        transformation: GraphTransformation,
        justification: ProjectionResult,
        attestation: String,
    ) -> Result<ProofObject, String> {
        let hash = Self::compute_proof_hash(&transformation, &justification, &attestation);
        Ok(ProofObject {
            proof_id: Uuid::new_v4(),
            transformation,
            justification,
            attestation,
            cryptography: ProofCryptography {
                proof_hash: hash,
                signing_agent: self.agent_id,
            },
        })
    }

    pub fn validate_proof(&self, proof: &ProofObject) -> Result<(), String> {
        // Check confidence threshold
        if proof.justification.confidence < self.confidence_threshold {
            return Err(format!(
                "CONFIDENCE_TOO_LOW: {} < {}",
                proof.justification.confidence, self.confidence_threshold
            ));
        }

        // Check for future timestamps (temporal coherence)
        let ts = chrono::DateTime::parse_from_rfc3339(&proof.transformation.timestamp_utc)
            .map_err(|e| format!("INVALID_TIMESTAMP: {}", e))?;
        let now = chrono::Utc::now();
        if ts > now + chrono::Duration::seconds(60) {
            return Err(format!(
                "FUTURE_TIMESTAMP: proof timestamp {} is in the future",
                proof.transformation.timestamp_utc
            ));
        }

        // Recompute hash and compare (HASH_MISMATCH detection)
        let recomputed = Self::compute_proof_hash(
            &proof.transformation,
            &proof.justification,
            &proof.attestation,
        );
        if recomputed != proof.cryptography.proof_hash {
            return Err(format!(
                "HASH_MISMATCH: expected {}, got {}",
                proof.cryptography.proof_hash, recomputed
            ));
        }

        Ok(())
    }
}

pub fn create_signing_key() -> Vec<u8> {
    vec![0u8; 32]
}

pub fn create_test_transformation() -> GraphTransformation {
    GraphTransformation {
        source_entity: Uuid::new_v4(),
        target_entity: Uuid::new_v4(),
        edge_type: "permission_grant".to_string(),
        timestamp_utc: chrono::Utc::now().to_rfc3339(),
        metadata: HashMap::new(),
    }
}

pub fn create_test_projection() -> ProjectionResult {
    ProjectionResult {
        projection_id: Uuid::new_v4(),
        confidence: 0.95,
        outcome: "allow".to_string(),
        justification: "ReBAC+AP2+Temporal all passed".to_string(),
    }
}

pub mod batch_verifier;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_corrupted_mesh_hash_mismatch_isolation_trap() {
        let signing_key = create_signing_key();
        let engine = PiPlusPlusEngine::new(signing_key, Uuid::new_v4());
        let transformation = create_test_transformation();
        let projection = create_test_projection();

        let proof = engine.generate_proof(transformation, projection, "allow".to_string())
            .expect("Proof generation must succeed");

        let mut tampered = proof.clone();
        tampered.transformation.source_entity = Uuid::new_v4();

        let result = engine.validate_proof(&tampered);
        assert!(result.is_err(), "Tampered proof must be rejected");
        let err_msg = result.unwrap_err();
        assert!(err_msg.contains("HASH_MISMATCH"), "Error must cite HASH_MISMATCH, got: {}", err_msg);
    }

    #[test]
    fn test_corrupted_mesh_multi_vector_injection_trap() {
        let signing_key = create_signing_key();
        let engine = PiPlusPlusEngine::new(signing_key, Uuid::new_v4());

        // Vector 1: Low confidence
        let low_conf = engine.generate_proof(
            create_test_transformation(),
            {
                let mut proj = create_test_projection();
                proj.confidence = 0.3;
                proj
            },
            "allow".to_string(),
        ).unwrap();
        assert!(engine.validate_proof(&low_conf).is_err(), "Low confidence must reject");

        // Vector 2: Tampered hash
        let valid = engine.generate_proof(
            create_test_transformation(),
            create_test_projection(),
            "allow".to_string(),
        ).unwrap();
        let mut tampered = valid.clone();
        tampered.transformation.edge_type = "evil".to_string();
        assert!(engine.validate_proof(&tampered).is_err(), "Tampered must reject");

        // Vector 3: Future timestamp
        let mut future = engine.generate_proof(
            create_test_transformation(),
            create_test_projection(),
            "allow".to_string(),
        ).unwrap();
        let future_time = chrono::Utc::now() + chrono::Duration::hours(2);
        future.transformation.timestamp_utc = future_time.to_rfc3339();
        assert!(engine.validate_proof(&future).is_err(), "Future timestamp must reject");
    }

    #[test]
    fn test_valid_proof_passes_validation() {
        let engine = PiPlusPlusEngine::new(create_signing_key(), Uuid::new_v4());
        let proof = engine.generate_proof(
            create_test_transformation(),
            create_test_projection(),
            "allow".to_string(),
        ).unwrap();
        assert!(engine.validate_proof(&proof).is_ok(), "Valid proof must pass");
    }
}
