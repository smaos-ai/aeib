use chrono::{DateTime, Utc};
use ed25519_dalek::{Verifier, VerifyingKey};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DidDocument {
    pub did: String,
    pub verifying_key_bytes: [u8; 32],
    pub specialty_domains: Vec<String>,
    pub registered_at: DateTime<Utc>,
}

pub struct DidRegistry {
    documents: HashMap<String, DidDocument>,
}

impl DidRegistry {
    pub fn new() -> Self {
        DidRegistry {
            documents: HashMap::new(),
        }
    }

    pub fn register(
        &mut self,
        tenant_id: Uuid,
        agent_id: Uuid,
        verifying_key: [u8; 32],
        domains: Vec<String>,
        now: DateTime<Utc>,
    ) -> String {
        let did = format!("did:smaos:{}:{}", tenant_id, agent_id);
        let doc = DidDocument {
            did: did.clone(),
            verifying_key_bytes: verifying_key,
            specialty_domains: domains,
            registered_at: now,
        };
        self.documents.insert(did.clone(), doc);
        did
    }

    pub fn resolve(&self, did: &str) -> Option<&DidDocument> {
        self.documents.get(did)
    }

    pub fn verify_signature(&self, did: &str, payload: &[u8], signature: &[u8]) -> bool {
        let doc = match self.documents.get(did) {
            Some(d) => d,
            None => return false,
        };

        let key = match VerifyingKey::from_bytes(&doc.verifying_key_bytes) {
            Ok(k) => k,
            Err(_) => return false,
        };

        let sig = match ed25519_dalek::Signature::try_from(signature) {
            Ok(s) => s,
            Err(_) => return false,
        };

        key.verify(payload, &sig).is_ok()
    }
}

impl Default for DidRegistry {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_did_format() {
        let mut registry = DidRegistry::new();
        let tenant = Uuid::new_v4();
        let agent = Uuid::new_v4();
        let did = registry.register(tenant, agent, [0u8; 32], vec![], Utc::now());

        assert!(did.starts_with("did:smaos:"));
        assert!(did.contains(&tenant.to_string()));
        assert!(did.contains(&agent.to_string()));
    }

    #[test]
    fn test_resolve_registered_did() {
        let mut registry = DidRegistry::new();
        let did = registry.register(
            Uuid::new_v4(),
            Uuid::new_v4(),
            [42u8; 32],
            vec!["test".to_string()],
            Utc::now(),
        );

        let doc = registry.resolve(&did).unwrap();
        assert_eq!(doc.verifying_key_bytes, [42u8; 32]);
        assert_eq!(doc.specialty_domains, vec!["test".to_string()]);
    }
}
