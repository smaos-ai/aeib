use chrono::{DateTime, Utc};
use uuid::Uuid;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AgentHealth {
    Active,
    Degraded,
    Offline,
}

#[derive(Debug, Clone)]
pub struct AgentMetadata {
    pub agent_id: Uuid,
    pub public_key: [u8; 32],
    pub state_hash: [u8; 32],
    pub last_sync: DateTime<Utc>,
    pub health: AgentHealth,
    pub message_queue_depth: usize,
}

impl AgentMetadata {
    pub fn new(agent_id: Uuid, public_key: [u8; 32]) -> Self {
        Self {
            agent_id,
            public_key,
            state_hash: [0u8; 32],
            last_sync: Utc::now(),
            health: AgentHealth::Active,
            message_queue_depth: 0,
        }
    }
}
