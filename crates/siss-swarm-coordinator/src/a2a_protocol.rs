use uuid::Uuid;
use sha2::{Sha256, Digest};
use chrono::{DateTime, Utc};
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
    pub fn new(
        from_agent_id: Uuid,
        to_agent_id: Uuid,
        payload: String,
    ) -> Self {
        let message_id = Uuid::new_v4();
        let timestamp = Utc::now();

        // Compute merkle hash of the message
        let merkle_hash = Self::compute_merkle_hash(
            message_id,
            from_agent_id,
            to_agent_id,
            &payload,
            timestamp,
        );

        // Create a dummy signature (in real implementation, would use Ed25519)
        let signature = merkle_hash.to_vec();

        Self {
            message_id,
            from_agent_id,
            to_agent_id,
            payload,
            merkle_hash,
            signature,
            timestamp,
        }
    }

    fn compute_merkle_hash(
        message_id: Uuid,
        from: Uuid,
        to: Uuid,
        payload: &str,
        timestamp: DateTime<Utc>,
    ) -> [u8; 32] {
        let mut hasher = Sha256::new();
        hasher.update(message_id.as_bytes());
        hasher.update(from.as_bytes());
        hasher.update(to.as_bytes());
        hasher.update(payload.as_bytes());
        hasher.update(timestamp.to_rfc3339().as_bytes());

        let result = hasher.finalize();
        let mut hash = [0u8; 32];
        hash.copy_from_slice(&result);
        hash
    }

    pub fn verify_signature(&self) -> Result<(), SwarmCoordinatorError> {
        // Verify that signature matches the merkle hash
        if self.signature == self.merkle_hash.to_vec() {
            Ok(())
        } else {
            Err(SwarmCoordinatorError::InternalError(
                "Signature verification failed".to_string(),
            ))
        }
    }
}
