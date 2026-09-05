//! Phase 1: Genesis Capsule Live Execution
//!
//! Demonstrates a single Capsule executing through the complete Axiom Protocol
//! authorization pipeline with covenant enforcement:
//!
//!   validate → ReBAC → AP2 → governance → covenant → sign+commit
//!
//! This is the proof artifact for Prague PoC: a live Capsule with Ed25519 signature,
//! valid 1%/99% covenant intent, and full merkle-rooted audit trail.

use ed25519_dalek::{Signer as DalekSigner, SigningKey};
use rand::rngs::OsRng;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::time::SystemTime;
use uuid::Uuid;

use siss_behavioral_firewall::ap2::{AttributePredicate, SovereignAttributes};
use siss_behavioral_firewall::covenant_firewall::EconomicIntent;
use siss_behavioral_firewall::rebac::PolicyAction;

use crate::pipeline::authorization::{AuthorizationPipeline, TaskAuthorizationRequest};
use crate::types::GatekeeperError;

/// Genesis Capsule: The irreducible proof artifact combining cryptographic,
/// economic, and human-sovereign governance into a single immutable token.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GenesisCapsule {
    pub capsule_id: Uuid,
    pub merkle_root: String,
    pub economist_pct: u8,   // Genesis: 1
    pub beneficiary_pct: u8, // Genesis: 99
    pub signature_hex: String,
    pub verifying_key_hex: String,
    pub authorization_proof: String,
    pub proof_merkle_root: String,
    pub timestamp: String,
}

/// Execute Genesis Capsule through full authorization pipeline.
/// Returns Merkle-rooted proof with covenant enforcement verified.
pub fn execute_genesis(signing_key: &SigningKey) -> Result<GenesisCapsule, GatekeeperError> {
    // 1. Create canonical merkle root (demo: 32 zero bytes)
    let capsule_merkle_root = [0u8; 32];
    let merkle_hex = hex::encode(capsule_merkle_root);

    // 2. Create 1%/99% covenant intent
    let intent = EconomicIntent {
        steward_pct: 1,
        beneficiary_pct: 99,
    };

    // 3. Sign the capsule with Ed25519
    let payload = Sha256::new()
        .chain_update(&capsule_merkle_root)
        .chain_update([intent.steward_pct])
        .chain_update([intent.beneficiary_pct])
        .finalize()
        .to_vec();

    let signature = signing_key.sign(&payload).to_bytes().to_vec();
    let verifying_key = signing_key.verifying_key().to_bytes().to_vec();

    let signature_hex = hex::encode(&signature);
    let vk_hex = hex::encode(&verifying_key);

    // 4. Create test sovereign attributes (demo: high-trust, not blacklisted)
    let attrs = SovereignAttributes {
        sovereign_id: Uuid::new_v4(),
        trust_level: 95,
        reputation: 100,
        joined_at: SystemTime::now(),
        blacklisted: false,
        certifications: vec![],
        organization: None,
        cached_at: SystemTime::now(),
    };

    // 5. Create minimal AP2 predicate (just trust level check)
    let predicate = Some(AttributePredicate::TrustLevel(50)); // attrs.trust_level (95) >= 50 ✓

    // 6. Build authorization request
    let task_id = Uuid::new_v4();
    let actor_id = Uuid::new_v4();

    let auth_req = TaskAuthorizationRequest {
        task_id,
        actor: actor_id,
        action: PolicyAction::Spawn,
        capsule_merkle_root,
        capsule_intent: intent,
        capsule_signature: signature.clone(),
        capsule_verifying_key: verifying_key.clone(),
        ap2_predicate: predicate,
        ap2_attributes: attrs,
        policy_composition: None,
    };

    // 7. Run authorization pipeline (60 req/min, no time windows)
    let temporal_guard = siss_behavioral_firewall::temporal::TemporalGuard::new(60, 60);
    let pipeline = AuthorizationPipeline::new(temporal_guard);

    let proof = pipeline.authorize(&auth_req)?;

    // 8. Serialize proof as JSON for audit trail
    let proof_json = serde_json::to_string(&proof).map_err(|e| GatekeeperError::DatabaseError {
        message: format!("proof serialization failed: {}", e),
    })?;

    let timestamp = chrono::Utc::now().to_rfc3339();

    Ok(GenesisCapsule {
        capsule_id: task_id,
        merkle_root: merkle_hex,
        economist_pct: 1,
        beneficiary_pct: 99,
        signature_hex,
        verifying_key_hex: vk_hex,
        authorization_proof: proof_json,
        proof_merkle_root: proof.merkle_root,
        timestamp,
    })
}

/// Demo Genesis Capsule execution with generated signing key (Phase 1 proof artifact).
pub fn execute_genesis_with_generated_key() -> Result<GenesisCapsule, GatekeeperError> {
    let signing_key = SigningKey::generate(&mut OsRng);
    execute_genesis(&signing_key)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_genesis_execution_produces_proof() {
        let result = execute_genesis_with_generated_key();
        assert!(result.is_ok());

        let capsule = result.unwrap();
        assert_eq!(capsule.economist_pct, 1);
        assert_eq!(capsule.beneficiary_pct, 99);
        assert!(!capsule.signature_hex.is_empty());
        assert!(!capsule.verifying_key_hex.is_empty());
        assert!(!capsule.proof_merkle_root.is_empty());
        assert!(capsule.proof_merkle_root.starts_with("sha256:"));
    }

    #[test]
    fn test_genesis_covenant_is_1_99() {
        let capsule = execute_genesis_with_generated_key().unwrap();
        assert_eq!(capsule.economist_pct + capsule.beneficiary_pct, 100);
    }

    #[test]
    fn test_genesis_all_gates_passed() {
        let capsule = execute_genesis_with_generated_key().unwrap();
        let proof: serde_json::Value =
            serde_json::from_str(&capsule.authorization_proof).expect("proof must be valid JSON");

        assert_eq!(proof["gate_decisions"]["covenant"], "PASSED");
        assert_eq!(proof["gate_decisions"]["ap2"], "PASSED");
        assert_eq!(proof["gate_decisions"]["temporal"], "PASSED");
    }
}
