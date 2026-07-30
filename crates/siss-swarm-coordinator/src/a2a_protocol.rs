use uuid::Uuid;
use chrono::{DateTime, Utc};
use sha2::{Sha256, Digest};
use crate::errors::SwarmCoordinatorError;

#[derive(Debug, Clone)]
pub struct A2AMessage {
    pub message_id: Uuid,
    pub from_agent_id: Uuid,
    pub to_agent_id: Uuid,
    pub payload: String,
    pub merkle_hash: [u8; 32],
    pub signature: Vec<u8>,
    pub timestamp: DateTime<Utc>,
}

impl A2AMessage {
    pub fn new(from_agent_id: Uuid, to_agent_id: Uuid, payload: String) -> Self {
        let message_id = Uuid::new_v4();
        let timestamp = Utc::now();
        
        let mut hasher = Sha256::new();
        hasher.update(from_agent_id.as_bytes());
        hasher.update(to_agent_id.as_bytes());
        hasher.update(payload.as_bytes());
        hasher.update(timestamp.to_rfc3339().as_bytes());
        
        let hash_result = hasher.finalize();
        let mut merkle_hash = [0u8; 32];
        merkle_hash.copy_from_slice(&hash_result[..]);

        Self {
            message_id,
            from_agent_id,
            to_agent_id,
            payload,
            merkle_hash,
            signature: vec![],
            timestamp,
        }
    }

    pub fn verify_signature(&self) -> Result<(), SwarmCoordinatorError> {
        // Basic signature verification stub
        // In a real implementation, this would verify Ed25519 signatures
        Ok(())
    }
}
