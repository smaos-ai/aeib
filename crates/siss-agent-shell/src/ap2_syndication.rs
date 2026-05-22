/// Phase 56: AP2 Revenue Routing — Micro-Transaction Syndication to Creator DID
/// Validates IntentMandate and routes agreed-upon revenue to creator's Decentralized Identifier.

use crate::skill_compiler::SkillPack;
use siss_gatekeeper::tokens::IntentMandate;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreatorDid {
    pub did: String,  // "did:sovereign:agent_id" format
    pub agent_id: Uuid,
    pub public_key_bytes: Vec<u8>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyndicationRecord {
    pub pack_id: Uuid,
    pub creator_did: CreatorDid,
    pub mandate_id: Uuid,
    pub micro_transaction_amount: i64,
    pub routed_at: chrono::DateTime<chrono::Utc>,
}

#[derive(Debug, PartialEq, Eq)]
pub enum SyndicationError {
    MandateMissing,
    MandateExhausted { remaining: i64, required: i64 },
    InvalidSignature,
    SkillPackNotVerified,
    DidResolutionFailed(String),
}

pub struct Ap2Syndication;

impl Ap2Syndication {
    /// Validate a SkillPack for network syndication.
    /// RULE 1: pack signature must be valid (SkillCompiler::verify) → Err(SkillPackNotVerified) if not
    /// RULE 2: mandate must be present (Some(IntentMandate)) → Err(MandateMissing) if None
    /// RULE 3: mandate must have budget remaining ≥ micro_transaction_amount → Err(MandateExhausted) if not
    /// RULE 4: Return Ok(SyndicationRecord) with record routed to creator_did via Crafter Economy
    pub fn validate_and_route(
        pack: &SkillPack,
        mandate: Option<&IntentMandate>,
        creator_did: &CreatorDid,
        micro_transaction_amount: i64,
    ) -> Result<SyndicationRecord, SyndicationError> {
        // RULE 1: Verify skill pack signature (fail-closed)
        if !crate::skill_compiler::SkillCompiler::verify(pack) {
            return Err(SyndicationError::SkillPackNotVerified);
        }

        // RULE 2: Check mandate presence (fail-closed)
        let mandate = mandate.ok_or(SyndicationError::MandateMissing)?;

        // RULE 3: Check budget remaining (fail-closed)
        let remaining = mandate.budget_remaining();
        if remaining < micro_transaction_amount {
            return Err(SyndicationError::MandateExhausted {
                remaining,
                required: micro_transaction_amount,
            });
        }

        // RULE 4: Construct syndication record
        Ok(SyndicationRecord {
            pack_id: pack.pack_id,
            creator_did: creator_did.clone(),
            mandate_id: mandate.id,
            micro_transaction_amount,
            routed_at: chrono::Utc::now(),
        })
    }

    /// Resolve a DID to a CreatorDid struct.
    /// For MVP: simply parse "did:sovereign:agent_id" and extract agent_id.
    /// RULE 1: DID format "did:sovereign:<uuid>" → extract uuid
    /// RULE 2: Construct CreatorDid with did + agent_id + placeholder public_key_bytes
    /// RULE 3: Return Err(DidResolutionFailed) if format invalid
    pub fn resolve_did(did_str: &str) -> Result<CreatorDid, SyndicationError> {
        const DID_PREFIX: &str = "did:sovereign:";

        if !did_str.starts_with(DID_PREFIX) {
            return Err(SyndicationError::DidResolutionFailed(
                "invalid DID format".to_string(),
            ));
        }

        let agent_id_str = &did_str[DID_PREFIX.len()..];
        let agent_id = Uuid::parse_str(agent_id_str)
            .map_err(|_| SyndicationError::DidResolutionFailed("invalid UUID in DID".to_string()))?;

        Ok(CreatorDid {
            did: did_str.to_string(),
            agent_id,
            public_key_bytes: vec![0u8; 32], // Placeholder for MVP
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ed25519_dalek::SigningKey;

    #[test]
    fn test_validate_and_route_with_valid_mandate() {
        let mut rng = rand::thread_rng();
        let signing_key = SigningKey::generate(&mut rng);

        let content = r#"---
name: verified_skill
description: Verified and routable
allowed-tools: [Read]
---
# Skill body"#;

        let pack = crate::skill_compiler::SkillCompiler::compile(content, &signing_key).unwrap();

        let mandate = IntentMandate {
            id: Uuid::new_v4(),
            budget_limit: 1000,
            budget_spent: 500,
            risk_class: "LOW".to_string(),
            allowed_tools: vec![],
        };

        let creator_did = CreatorDid {
            did: format!("did:sovereign:{}", Uuid::new_v4()),
            agent_id: Uuid::new_v4(),
            public_key_bytes: vec![0u8; 32],
        };

        let result = Ap2Syndication::validate_and_route(&pack, Some(&mandate), &creator_did, 100);
        assert!(result.is_ok());
        let record = result.unwrap();
        assert_eq!(record.micro_transaction_amount, 100);
    }

    #[test]
    fn test_validate_rejects_missing_mandate() {
        let mut rng = rand::thread_rng();
        let signing_key = SigningKey::generate(&mut rng);

        let content = r#"---
name: unroutable
description: No mandate
allowed-tools: [Read]
---
# Unroutable"#;

        let pack = crate::skill_compiler::SkillCompiler::compile(content, &signing_key).unwrap();

        let creator_did = CreatorDid {
            did: format!("did:sovereign:{}", Uuid::new_v4()),
            agent_id: Uuid::new_v4(),
            public_key_bytes: vec![0u8; 32],
        };

        let result = Ap2Syndication::validate_and_route(&pack, None, &creator_did, 100);
        assert!(matches!(result, Err(SyndicationError::MandateMissing)));
    }

    #[test]
    fn test_resolve_did_valid() {
        let did_str = format!("did:sovereign:{}", Uuid::new_v4());
        let result = Ap2Syndication::resolve_did(&did_str);
        assert!(result.is_ok(), "DID resolution should succeed");
        let creator_did = result.unwrap();
        assert!(creator_did.did.starts_with("did:sovereign:"));
    }

    #[test]
    fn test_resolve_did_invalid() {
        let result = Ap2Syndication::resolve_did("not-a-valid-did");
        assert!(result.is_err(), "Invalid DID should fail");
    }
}
