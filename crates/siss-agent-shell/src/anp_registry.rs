/// Phase 58: ANP Registry — DID-authenticated peer discovery
use crate::ap2_syndication::CreatorDid;
use ed25519_dalek::{Signature, Verifier, VerifyingKey};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::Mutex;
use uuid::Uuid;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum AnpError {
    UnauthorizedPeer { reason: String },
    InvalidDidFormat(String),
    PeerNotFound(Uuid),
    AlreadyRegistered(Uuid),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AnpPeer {
    pub peer_id: Uuid,
    pub did: CreatorDid,
    pub endpoint_url: String,
    pub capabilities: Vec<String>,
    pub public_key: [u8; 32],
}

pub struct AnpRegistry {
    peers: Arc<Mutex<HashMap<Uuid, AnpPeer>>>,
}

impl AnpRegistry {
    pub fn new() -> Self {
        AnpRegistry {
            peers: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    /// Register a peer with DID and Ed25519 public key.
    /// RULE 1: resolve_did() must succeed
    /// RULE 2: public_key != [0u8; 32]
    /// RULE 3: No duplicate did.agent_id
    pub async fn register_peer(
        &self,
        did_str: &str,
        endpoint_url: &str,
        capabilities: Vec<String>,
        public_key: [u8; 32],
    ) -> Result<Uuid, AnpError> {
        let creator_did = crate::ap2_syndication::Ap2Syndication::resolve_did(did_str)
            .map_err(|_| AnpError::InvalidDidFormat("invalid DID format".to_string()))?;

        if public_key == [0u8; 32] {
            return Err(AnpError::InvalidDidFormat(
                "placeholder_key: public key must be non-zero".to_string(),
            ));
        }

        let peer_id = Uuid::new_v4();
        let mut peers = self.peers.lock().await;

        if peers
            .values()
            .any(|p| p.did.agent_id == creator_did.agent_id)
        {
            return Err(AnpError::AlreadyRegistered(creator_did.agent_id));
        }

        let peer = AnpPeer {
            peer_id,
            did: creator_did,
            endpoint_url: endpoint_url.to_string(),
            capabilities,
            public_key,
        };

        peers.insert(peer_id, peer);
        Ok(peer_id)
    }

    /// Authenticate a peer using Ed25519 signature verification.
    /// RULE 5: Peer must be registered
    /// RULE 7: Signature must be valid
    pub async fn authenticate_peer(
        &self,
        did_str: &str,
        payload: &[u8],
        signature_bytes: &[u8; 64],
    ) -> Result<AnpPeer, AnpError> {
        let peers = self.peers.lock().await;

        let peer = peers
            .values()
            .find(|p| p.did.did == did_str)
            .cloned()
            .ok_or_else(|| AnpError::UnauthorizedPeer {
                reason: "peer_not_registered".to_string(),
            })?;

        let verifying_key =
            VerifyingKey::from_bytes(&peer.public_key).map_err(|_| AnpError::UnauthorizedPeer {
                reason: "invalid_public_key".to_string(),
            })?;

        let signature = Signature::from_bytes(signature_bytes);
        verifying_key
            .verify(payload, &signature)
            .map_err(|_| AnpError::UnauthorizedPeer {
                reason: "invalid_signature".to_string(),
            })?;

        Ok(peer)
    }

    pub async fn lookup_by_did(&self, did_str: &str) -> Option<AnpPeer> {
        let peers = self.peers.lock().await;
        peers.values().find(|p| p.did.did == did_str).cloned()
    }

    pub async fn deregister_peer(&self, peer_id: Uuid) -> Result<(), AnpError> {
        let mut peers = self.peers.lock().await;
        peers
            .remove(&peer_id)
            .ok_or_else(|| AnpError::PeerNotFound(peer_id))?;
        Ok(())
    }
}

impl Default for AnpRegistry {
    fn default() -> Self {
        AnpRegistry::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_anp_registry_new() {
        let registry = AnpRegistry::new();
        assert_eq!(registry.peers.lock().await.len(), 0);
    }
}
