use crate::agent::AgentState;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Snapshot of agent state for migration
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct StateSnapshot {
    pub agent_id: Uuid,
    pub state: AgentState,
    pub timestamp: i64,
    /// Checksum for integrity verification
    pub checksum: Vec<u8>,
}

impl StateSnapshot {
    /// Create snapshot from agent state
    pub fn new(agent_id: Uuid, state: AgentState) -> Self {
        let checksum = Self::compute_checksum(&state);
        Self {
            agent_id,
            state,
            timestamp: chrono::Utc::now().timestamp(),
            checksum,
        }
    }

    /// Compute checksum for state integrity
    fn compute_checksum(state: &AgentState) -> Vec<u8> {
        use sha2::{Digest, Sha256};
        let mut hasher = Sha256::new();
        hasher.update(state.decisions_made.to_le_bytes());
        hasher.update(state.tokens_consumed.to_le_bytes());
        hasher.finalize().to_vec()
    }

    /// Verify snapshot integrity
    pub fn verify(&self) -> bool {
        Self::compute_checksum(&self.state) == self.checksum
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_snapshot_creation() {
        let agent_id = Uuid::new_v4();
        let state = AgentState::default();
        let snap = StateSnapshot::new(agent_id, state);

        assert_eq!(snap.agent_id, agent_id);
        assert!(snap.verify());
    }

    #[test]
    fn test_snapshot_integrity() {
        let agent_id = Uuid::new_v4();
        let state = AgentState {
            decisions_made: 100,
            tokens_consumed: 500,
            context_window: vec!["test".to_string()],
        };
        let snap = StateSnapshot::new(agent_id, state);

        assert!(snap.verify());
    }
}
