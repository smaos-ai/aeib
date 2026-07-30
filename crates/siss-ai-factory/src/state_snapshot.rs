use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sha2::{Sha256, Digest};
use std::collections::HashMap;
use uuid::Uuid;

/// Agent state at a point in time
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AgentState {
    pub agent_id: Uuid,
    pub state_hash: [u8; 32],  // sha256 of agent state
    pub message_count: usize,   // messages processed
    pub last_execution: DateTime<Utc>,
}

/// Immutable state snapshot with merkle root commitment
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StateSnapshot {
    pub timestamp: DateTime<Utc>,
    pub agent_states: HashMap<Uuid, AgentState>,
    pub merkle_root: [u8; 32],  // deterministic root for all agents
}

impl StateSnapshot {
    /// Create a new snapshot with given agent states
    pub fn new(agent_states: HashMap<Uuid, AgentState>) -> Self {
        let merkle_root = Self::compute_merkle_root(&agent_states);
        Self {
            timestamp: Utc::now(),
            agent_states,
            merkle_root,
        }
    }

    /// Compute deterministic merkle root from agent states
    pub fn compute_merkle_root(agent_states: &HashMap<Uuid, AgentState>) -> [u8; 32] {
        let mut hasher = Sha256::new();

        // Sort by agent ID for deterministic ordering
        let mut sorted_states: Vec<_> = agent_states.iter().collect();
        sorted_states.sort_by_key(|(id, _)| *id);

        for (agent_id, state) in sorted_states {
            hasher.update(agent_id.as_bytes());
            hasher.update(state.state_hash);
            hasher.update(state.message_count.to_le_bytes());
            hasher.update(state.last_execution.timestamp().to_le_bytes());
        }

        let mut root = [0u8; 32];
        root.copy_from_slice(&hasher.finalize());
        root
    }

    /// Verify merkle root consistency (no tampering)
    pub fn verify_merkle_root(&self) -> bool {
        let computed_root = Self::compute_merkle_root(&self.agent_states);
        computed_root == self.merkle_root
    }

    /// Recompute merkle root (used after recovery to verify state consistency)
    pub fn recompute_merkle_root(&mut self) {
        self.merkle_root = Self::compute_merkle_root(&self.agent_states);
    }

    /// Check if snapshot is empty (no agents)
    pub fn is_empty(&self) -> bool {
        self.agent_states.is_empty()
    }

    /// Get number of agents in snapshot
    pub fn agent_count(&self) -> usize {
        self.agent_states.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_snapshot_empty() {
        let snapshot = StateSnapshot::new(HashMap::new());
        assert!(snapshot.is_empty());
        assert_eq!(snapshot.agent_count(), 0);
    }

    #[test]
    fn test_snapshot_merkle_root_deterministic() {
        let agent_id = Uuid::new_v4();
        let mut agents = HashMap::new();
        agents.insert(
            agent_id,
            AgentState {
                agent_id,
                state_hash: [0u8; 32],
                message_count: 42,
                last_execution: Utc::now(),
            },
        );

        let snap1 = StateSnapshot::new(agents.clone());
        let snap2 = StateSnapshot::new(agents);

        // Same state should produce same merkle root
        assert_eq!(snap1.merkle_root, snap2.merkle_root);
    }

    #[test]
    fn test_snapshot_merkle_root_differs_with_state_change() {
        let agent_id = Uuid::new_v4();
        let mut agents1 = HashMap::new();
        agents1.insert(
            agent_id,
            AgentState {
                agent_id,
                state_hash: [0u8; 32],
                message_count: 42,
                last_execution: Utc::now(),
            },
        );

        let mut agents2 = HashMap::new();
        agents2.insert(
            agent_id,
            AgentState {
                agent_id,
                state_hash: [1u8; 32],  // Different state
                message_count: 42,
                last_execution: Utc::now(),
            },
        );

        let snap1 = StateSnapshot::new(agents1);
        let snap2 = StateSnapshot::new(agents2);

        // Different states should produce different roots
        assert_ne!(snap1.merkle_root, snap2.merkle_root);
    }

    #[test]
    fn test_snapshot_verify_merkle_root() {
        let agent_id = Uuid::new_v4();
        let mut agents = HashMap::new();
        agents.insert(
            agent_id,
            AgentState {
                agent_id,
                state_hash: [42u8; 32],
                message_count: 100,
                last_execution: Utc::now(),
            },
        );

        let snapshot = StateSnapshot::new(agents);
        assert!(snapshot.verify_merkle_root());
    }
}
