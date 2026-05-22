/// Phase 57: Sneakernet Ingress — 4-Gate USB Quarantine Pipeline
/// INVARIANT: signature → frontmatter → dry-run → human-approval gates all fail-closed.

use crate::skill_compiler::SkillCompiler;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum QuarantineError {
    SignatureInvalid,
    FrontmatterMalformed,
    DryRunFailure(String),
    HumanApprovalMissing,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QuarantineRecord {
    pub quarantine_id: Uuid,
    pub skill_pack_id: Uuid,
    pub gate_1_signature_verified: bool,
    pub gate_2_frontmatter_valid: bool,
    pub gate_3_dry_run_passed: bool,
    pub gate_4_human_approved: bool,
    pub promoted_at: Option<chrono::DateTime<chrono::Utc>>,
}

pub struct SneakernetIngress;

impl SneakernetIngress {
    /// Gate 1: Signature verification.
    /// RULE 1: SkillCompiler::verify(pack) → false → Err(SignatureInvalid)
    /// RULE 2: true → Ok(gate_passed=true)
    pub fn gate_1_verify_signature(pack: &crate::skill_compiler::SkillPack) -> Result<bool, QuarantineError> {
        if !SkillCompiler::verify(pack) {
            return Err(QuarantineError::SignatureInvalid);
        }
        Ok(true)
    }

    /// Gate 2: Frontmatter validation.
    /// RULE 3: pack.frontmatter.name.is_empty() → Err(FrontmatterMalformed)
    /// RULE 4: pack.frontmatter.allowed_tools.is_empty() → Err(FrontmatterMalformed)
    /// RULE 5: All checks pass → Ok(gate_passed=true)
    pub fn gate_2_validate_frontmatter(pack: &crate::skill_compiler::SkillPack) -> Result<bool, QuarantineError> {
        if pack.frontmatter.name.is_empty() {
            return Err(QuarantineError::FrontmatterMalformed);
        }
        if pack.frontmatter.allowed_tools.is_empty() {
            return Err(QuarantineError::FrontmatterMalformed);
        }
        Ok(true)
    }

    /// Gate 3: Dry-run verification (mock).
    /// RULE 6: Simulate execution of allowed tools in dry-run sandbox
    /// RULE 7: If any tool invocation fails (mock: always succeed for now) → Err(DryRunFailure)
    /// RULE 8: All tools succeed → Ok(gate_passed=true)
    pub fn gate_3_dry_run(pack: &crate::skill_compiler::SkillPack) -> Result<bool, QuarantineError> {
        // Mock: simulate that all allowed_tools execute without error
        for tool in &pack.frontmatter.allowed_tools {
            if tool.is_empty() {
                return Err(QuarantineError::DryRunFailure(
                    "empty tool name in allowed_tools".to_string(),
                ));
            }
        }
        Ok(true)
    }

    /// Gate 4: Human approval (mock).
    /// RULE 9: In production, this would require a cryptographic signature from a human operator
    /// RULE 10: For MVP, accept a boolean flag. Real implementation uses Ap2Syndication::resolve_did
    pub fn gate_4_human_approval(approved: bool) -> Result<bool, QuarantineError> {
        if !approved {
            return Err(QuarantineError::HumanApprovalMissing);
        }
        Ok(true)
    }

    /// Run all four gates in sequence.
    /// RULE 11: All gates must pass (fail-closed: first failure halts)
    /// RULE 12: Return Ok(QuarantineRecord) if all gates pass
    pub fn quarantine(
        pack: &crate::skill_compiler::SkillPack,
        human_approved: bool,
    ) -> Result<QuarantineRecord, QuarantineError> {
        Self::gate_1_verify_signature(pack)?;
        Self::gate_2_validate_frontmatter(pack)?;
        Self::gate_3_dry_run(pack)?;
        Self::gate_4_human_approval(human_approved)?;

        Ok(QuarantineRecord {
            quarantine_id: Uuid::new_v4(),
            skill_pack_id: pack.pack_id,
            gate_1_signature_verified: true,
            gate_2_frontmatter_valid: true,
            gate_3_dry_run_passed: true,
            gate_4_human_approved: true,
            promoted_at: Some(chrono::Utc::now()),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ed25519_dalek::SigningKey;

    #[test]
    fn test_gate_1_rejects_invalid_signature() {
        let mut pack = crate::skill_compiler::SkillPack {
            pack_id: Uuid::new_v4(),
            creator_public_key: vec![0u8; 32],
            frontmatter: crate::skill_compiler::SkillFrontmatter {
                name: "test".to_string(),
                description: "test".to_string(),
                allowed_tools: vec!["Read".to_string()],
                disallowed_tools: None,
            },
            content_hash: "deadbeef".to_string(),
            signature: vec![0u8; 64],
        };
        pack.signature[0] = 0xFF; // Tamper

        let result = SneakernetIngress::gate_1_verify_signature(&pack);
        assert_eq!(result, Err(QuarantineError::SignatureInvalid));
    }

    #[test]
    fn test_gate_2_rejects_empty_name() {
        let pack = crate::skill_compiler::SkillPack {
            pack_id: Uuid::new_v4(),
            creator_public_key: vec![0u8; 32],
            frontmatter: crate::skill_compiler::SkillFrontmatter {
                name: "".to_string(),
                description: "test".to_string(),
                allowed_tools: vec!["Read".to_string()],
                disallowed_tools: None,
            },
            content_hash: "hash".to_string(),
            signature: vec![0u8; 64],
        };

        let result = SneakernetIngress::gate_2_validate_frontmatter(&pack);
        assert_eq!(result, Err(QuarantineError::FrontmatterMalformed));
    }

    #[test]
    fn test_quarantine_passes_all_gates() {
        let mut rng = rand::thread_rng();
        let signing_key = SigningKey::generate(&mut rng);

        let content = r#"---
name: quarantine_skill
description: USB quarantine test
allowed-tools: [Read]
---
# Test"#;

        let pack = crate::skill_compiler::SkillCompiler::compile(content, &signing_key).unwrap();
        let result = SneakernetIngress::quarantine(&pack, true);
        assert!(result.is_ok());
        let record = result.unwrap();
        assert!(record.gate_1_signature_verified);
        assert!(record.gate_2_frontmatter_valid);
        assert!(record.gate_3_dry_run_passed);
        assert!(record.gate_4_human_approved);
    }
}
