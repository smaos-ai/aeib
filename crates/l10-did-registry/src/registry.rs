use crate::did::{DID, DidDocument, PublicKey};
use crate::error::DidError;
use crate::verification::DidVerifier;
use std::collections::HashMap;

pub struct DidRegistry {
    documents: HashMap<String, DidDocument>,
    tenant_dids: HashMap<String, Vec<String>>, // tenant_id -> DID strings
}

impl DidRegistry {
    pub fn new() -> Self {
        Self {
            documents: HashMap::new(),
            tenant_dids: HashMap::new(),
        }
    }

    pub fn register_did(
        &mut self,
        did: DID,
        controller: Option<String>,
        tenant_id: String,
    ) -> Result<DidDocument, DidError> {
        let did_str = did.to_string();

        if self.documents.contains_key(&did_str) {
            return Err(DidError::RegistryError(format!("DID already exists: {}", did_str)));
        }

        let mut doc = DidDocument::new(did.clone(), controller);
        let hash = DidVerifier::compute_did_hash(&did);
        doc.proof = Some(hash);

        self.documents.insert(did_str.clone(), doc.clone());

        self.tenant_dids
            .entry(tenant_id)
            .or_insert_with(Vec::new)
            .push(did_str);

        Ok(doc)
    }

    pub fn resolve_did(&self, did: &DID) -> Result<DidDocument, DidError> {
        self.documents
            .get(&did.to_string())
            .cloned()
            .ok_or_else(|| DidError::NotFound(did.to_string()))
    }

    pub fn add_public_key(
        &mut self,
        did: &DID,
        pub_key: PublicKey,
    ) -> Result<DidDocument, DidError> {
        let did_str = did.to_string();
        if let Some(doc) = self.documents.get_mut(&did_str) {
            doc.add_public_key(pub_key);
            Ok(doc.clone())
        } else {
            Err(DidError::NotFound(did_str))
        }
    }

    pub fn list_tenant_dids(&self, tenant_id: &str) -> Vec<DidDocument> {
        self.tenant_dids
            .get(tenant_id)
            .map(|dids| {
                dids.iter()
                    .filter_map(|did_str| self.documents.get(did_str).cloned())
                    .collect()
            })
            .unwrap_or_default()
    }

    pub fn verify_did_ownership(
        &self,
        did: &DID,
        tenant_id: &str,
    ) -> Result<bool, DidError> {
        if let Some(owned_dids) = self.tenant_dids.get(tenant_id) {
            Ok(owned_dids.contains(&did.to_string()))
        } else {
            Ok(false) // Tenant doesn't exist or doesn't own this DID
        }
    }

    pub fn count_dids(&self) -> usize {
        self.documents.len()
    }

    pub fn count_tenant_dids(&self, tenant_id: &str) -> usize {
        self.tenant_dids
            .get(tenant_id)
            .map(|dids| dids.len())
            .unwrap_or(0)
    }
}

impl Default for DidRegistry {
    fn default() -> Self {
        Self::new()
    }
}
