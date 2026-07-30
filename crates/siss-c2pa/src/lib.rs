pub mod c2pa;
pub mod signer;

pub use c2pa::{ResearchResult, c2pa_manifest_to_capsule, capsule_to_c2pa_manifest};
pub use signer::Ed25519C2PASigner;

#[cfg(test)]
mod tests {
    use crate::{
        Ed25519C2PASigner, ResearchResult, c2pa_manifest_to_capsule, capsule_to_c2pa_manifest,
    };
    use ed25519_dalek::SigningKey;
    use rand::thread_rng;

    #[test]
    fn test_ed25519_c2pa_signer_creation() {
        let mut rng = thread_rng();
        let signing_key = SigningKey::generate(&mut rng);
        let signer = Ed25519C2PASigner::new(signing_key);

        let pubkey_hex = signer.public_key_hex();
        assert_eq!(pubkey_hex.len(), 64); // 32 bytes = 64 hex chars
    }

    #[test]
    fn test_capsule_to_manifest_roundtrip() {
        let capsule = ResearchResult {
            query: "What is sovereign AI?".to_string(),
            answer: "SMAOS is a sovereign multi-agent OS...".to_string(),
            source: "local_cache".to_string(),
            timestamp: "2026-05-31T12:00:00Z".to_string(),
            merkle_hash: "abc123def456".to_string(),
        };

        // Convert capsule → manifest
        let manifest_bytes =
            capsule_to_c2pa_manifest(&capsule).expect("Failed to create C2PA manifest");
        assert!(!manifest_bytes.is_empty());

        // Convert manifest → capsule
        let recovered =
            c2pa_manifest_to_capsule(&manifest_bytes).expect("Failed to parse manifest");

        assert_eq!(recovered.query, capsule.query);
        assert_eq!(recovered.answer, capsule.answer);
        assert_eq!(recovered.source, capsule.source);
    }

    #[test]
    fn test_manifest_invalid_json() {
        let invalid_json = b"not a valid json";
        let result = c2pa_manifest_to_capsule(invalid_json);
        assert!(result.is_err());
    }

    #[test]
    fn test_manifest_missing_assertion() {
        let manifest_json = serde_json::json!({
            "claims": [
                {
                    "assertions": [
                        {
                            "kind": "c2pa:hash",
                            "data": "..."
                        }
                    ]
                }
            ]
        });

        let result = c2pa_manifest_to_capsule(&serde_json::to_vec(&manifest_json).unwrap());
        // Should fail because smaos:research_result not present
        assert!(result.is_err());
    }
}
