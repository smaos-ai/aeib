use uuid::Uuid;
use std::time::SystemTime;

#[derive(Debug, Clone)]
pub struct AgentMetadata {
    pub agent_id: Uuid,
    pub public_key: [u8; 32],
    pub registered_at: SystemTime,
}

impl AgentMetadata {
    pub fn new(agent_id: Uuid, public_key: [u8; 32]) -> Self {
        Self {
            agent_id,
            public_key,
            registered_at: SystemTime::now(),
        }
    }
}
