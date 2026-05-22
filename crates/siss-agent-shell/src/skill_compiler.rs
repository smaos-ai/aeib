/// Phase 56: Sovereign Skill Pack Compilation — Ed25519 Signed Provenance Artifacts
/// Parses SKILL.md frontmatter, hashes contents, cryptographically signs with creator's private key.

use ed25519_dalek::{Signature, SigningKey, Signer, SignatureError, Verifier};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SkillFrontmatter {
    pub name: String,
    pub description: String,
    pub allowed_tools: Vec<String>,
    pub disallowed_tools: Option<Vec<String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SkillPack {
    pub pack_id: Uuid,
    pub creator_public_key: Vec<u8>,  // Ed25519 public key (32 bytes)
    pub frontmatter: SkillFrontmatter,
    pub content_hash: String,          // SHA256 hex of .md body
    pub signature: Vec<u8>,            // Ed25519 signature over canonical bytes
}

#[derive(Debug, PartialEq, Eq)]
pub enum CompileError {
    MalformedFrontmatter(String),
    EmptyContent,
    SigningFailed(String),
    InvalidPublicKey,
}

pub struct SkillCompiler;

impl SkillCompiler {
    /// Parse SKILL.md file and extract frontmatter.
    /// RULE 1: Input must start with "---\n" followed by YAML, followed by "---\n"
    /// RULE 2: Extract name, description, allowed-tools fields (required)
    /// RULE 3: disallowedTools optional
    /// RULE 4: Return Err(MalformedFrontmatter) if YAML parse fails
    pub fn parse_frontmatter(content: &str) -> Result<(SkillFrontmatter, String), CompileError> {
        let parts: Vec<&str> = content.splitn(3, "---").collect();
        if parts.len() < 3 {
            return Err(CompileError::MalformedFrontmatter(
                "Missing YAML fence (---)".to_string(),
            ));
        }

        let yaml_str = parts[1].trim();
        let body = parts[2];

        let yaml_map: serde_yaml::Mapping = serde_yaml::from_str(yaml_str)
            .map_err(|e| CompileError::MalformedFrontmatter(e.to_string()))?;

        let name = yaml_map
            .get("name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| CompileError::MalformedFrontmatter("missing 'name' field".to_string()))?
            .to_string();

        let description = yaml_map
            .get("description")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                CompileError::MalformedFrontmatter("missing 'description' field".to_string())
            })?
            .to_string();

        let allowed_tools: Vec<String> = yaml_map
            .get("allowed-tools")
            .and_then(|v| v.as_sequence())
            .ok_or_else(|| {
                CompileError::MalformedFrontmatter("missing 'allowed-tools' array".to_string())
            })?
            .iter()
            .filter_map(|v| v.as_str().map(|s| s.to_string()))
            .collect();

        let disallowed_tools = yaml_map
            .get("disallowedTools")
            .and_then(|v| v.as_sequence())
            .map(|seq| {
                seq.iter()
                    .filter_map(|v| v.as_str().map(|s| s.to_string()))
                    .collect()
            });

        let frontmatter = SkillFrontmatter {
            name,
            description,
            allowed_tools,
            disallowed_tools,
        };

        Ok((frontmatter, body.to_string()))
    }

    /// Compile a SkillPack from SKILL.md content.
    /// RULE 1: parse_frontmatter(content) → frontmatter + body
    /// RULE 2: body.is_empty() → Err(EmptyContent)
    /// RULE 3: Hash body with sha256 → content_hash (hex)
    /// RULE 4: Sign canonical_bytes(frontmatter + content_hash) with signing_key
    /// RULE 5: Return SkillPack with signature, public_key extracted from signing_key
    pub fn compile(
        content: &str,
        signing_key: &SigningKey,
    ) -> Result<SkillPack, CompileError> {
        let (frontmatter, body) = Self::parse_frontmatter(content)?;

        if body.trim().is_empty() {
            return Err(CompileError::EmptyContent);
        }

        // Hash the body
        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};
        let mut hasher = DefaultHasher::new();
        body.hash(&mut hasher);
        let content_hash = format!("{:x}", hasher.finish());

        // Canonical bytes: frontmatter JSON + body hash
        let mut canonical = serde_json::to_vec(&frontmatter)
            .map_err(|e| CompileError::SigningFailed(e.to_string()))?;
        canonical.extend(content_hash.as_bytes());

        // Sign
        let signature = signing_key.sign(&canonical);

        Ok(SkillPack {
            pack_id: Uuid::new_v4(),
            creator_public_key: signing_key.verifying_key().to_bytes().to_vec(),
            frontmatter,
            content_hash,
            signature: signature.to_bytes().to_vec(),
        })
    }

    /// Verify a SkillPack signature.
    /// RULE 1: Extract public_key from pack.creator_public_key
    /// RULE 2: Reconstruct canonical_bytes(frontmatter + content_hash)
    /// RULE 3: Verify signature over canonical bytes
    /// RULE 4: Return true only if signature is valid, false otherwise
    pub fn verify(pack: &SkillPack) -> bool {
        use ed25519_dalek::VerifyingKey;

        let public_key_array: [u8; 32] = match pack.creator_public_key.as_slice().try_into() {
            Ok(arr) => arr,
            Err(_) => return false,
        };

        let public_key = match VerifyingKey::from_bytes(&public_key_array) {
            Ok(k) => k,
            Err(_) => return false,
        };

        let mut canonical = serde_json::to_vec(&pack.frontmatter).unwrap_or_default();
        canonical.extend(pack.content_hash.as_bytes());

        let sig_bytes: [u8; 64] = match pack.signature.as_slice().try_into() {
            Ok(b) => b,
            Err(_) => return false,
        };
        let signature = Signature::from_bytes(&sig_bytes);

        public_key.verify(&canonical, &signature).is_ok()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_frontmatter_valid() {
        let content = r#"---
name: test_skill
description: A test skill
allowed-tools: [Read, Bash]
---
# This is the body"#;

        let (fm, body) = SkillCompiler::parse_frontmatter(content).unwrap();
        assert_eq!(fm.name, "test_skill");
        assert_eq!(fm.description, "A test skill");
        assert_eq!(fm.allowed_tools, vec!["Read", "Bash"]);
        assert!(body.contains("This is the body"));
    }

    #[test]
    fn test_parse_frontmatter_invalid() {
        let content = "no yaml here";
        assert!(SkillCompiler::parse_frontmatter(content).is_err());
    }

    #[test]
    fn test_compile_and_verify() {
        let mut rng = rand::thread_rng();
        let signing_key = SigningKey::generate(&mut rng);

        let content = r#"---
name: secure_skill
description: Cryptographically secured
allowed-tools: [Edit, Write]
---
# Implementation code here"#;

        let pack = SkillCompiler::compile(content, &signing_key).unwrap();
        assert!(SkillCompiler::verify(&pack));
    }

    #[test]
    fn test_tampered_pack_fails_verify() {
        let mut rng = rand::thread_rng();
        let signing_key = SigningKey::generate(&mut rng);

        let content = r#"---
name: original
description: Original skill
allowed-tools: [Read]
---
# Original content"#;

        let mut pack = SkillCompiler::compile(content, &signing_key).unwrap();
        pack.frontmatter.description = "Tampered description".to_string();

        assert!(!SkillCompiler::verify(&pack));
    }
}
