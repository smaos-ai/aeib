/// Swarm orchestration primitives: collision resistance, schema validation, state synchronization.
///
/// Invariant 1: WorktreeClaimLedger is atomic first-wins claim/release.
/// Invariant 3: SwarmChannel validates schema before broadcast.
/// Invariant 4: SwarmStateLedger upsert is idempotent via agent_id.
use std::collections::HashMap;
use std::sync::Mutex;
use thiserror::Error;
use tokio::sync::broadcast;
use uuid::Uuid;

/// Error type for claim operations.
#[derive(Debug, Error, PartialEq)]
#[error("file already claimed by agent {held_by}")]
pub struct ClaimError {
    pub held_by: Uuid,
}

impl ClaimError {
    pub fn already_claimed(held_by: Uuid) -> Self {
        ClaimError { held_by }
    }
}

/// Trait for atomic worktree/file claim ledger.
pub trait WorktreeClaimLedger: Send + Sync {
    fn claim(&self, worktree: &str, file: &str, agent_id: Uuid) -> Result<(), ClaimError>;
    fn release(&self, worktree: &str, file: &str, agent_id: Uuid);
    fn is_claimed(&self, worktree: &str, file: &str) -> bool;
}

/// In-memory implementation of WorktreeClaimLedger.
pub struct InMemoryClaimLedger {
    claims: Mutex<HashMap<(String, String), Uuid>>,
}

impl InMemoryClaimLedger {
    pub fn new() -> Self {
        InMemoryClaimLedger {
            claims: Mutex::new(HashMap::new()),
        }
    }
}

impl Default for InMemoryClaimLedger {
    fn default() -> Self {
        Self::new()
    }
}

impl WorktreeClaimLedger for InMemoryClaimLedger {
    fn claim(&self, worktree: &str, file: &str, agent_id: Uuid) -> Result<(), ClaimError> {
        let key = (worktree.to_string(), file.to_string());
        let mut claims = self.claims.lock().unwrap();

        if let Some(&held_by) = claims.get(&key) {
            return Err(ClaimError::already_claimed(held_by));
        }

        claims.insert(key, agent_id);
        Ok(())
    }

    fn release(&self, worktree: &str, file: &str, agent_id: Uuid) {
        let key = (worktree.to_string(), file.to_string());
        let mut claims = self.claims.lock().unwrap();
        if claims.get(&key) == Some(&agent_id) {
            claims.remove(&key);
        }
    }

    fn is_claimed(&self, worktree: &str, file: &str) -> bool {
        let key = (worktree.to_string(), file.to_string());
        self.claims.lock().unwrap().contains_key(&key)
    }
}

/// Error type for swarm channel operations.
#[derive(Debug, Error)]
pub enum ChannelError {
    #[error("schema mismatch: {0}")]
    SchemaMismatch(String),
    #[error("channel closed")]
    ChannelClosed,
}

/// Swarm message envelope with schema validation.
#[derive(Debug, Clone)]
pub enum SwarmMessage {
    StatusUpdate {
        agent_id: Uuid,
        state: String,
        progress_pct: u8,
    },
    ArtifactReady {
        agent_id: Uuid,
        artifact_id: Uuid,
        artifact_type: String,
    },
    CommandDispatch {
        command_id: Uuid,
        target_agent_id: Uuid,
        payload: serde_json::Value,
    },
    PixelProvenance {
        provenance_id: Uuid,
        agent_id: String,
        action_type: String,
        action_x: Option<f64>,
        action_y: Option<f64>,
        token_cost: i64,
        mandate_id: Uuid,
    },
}

impl SwarmMessage {
    /// Validate schema constraints before broadcast.
    fn validate(&self) -> Result<(), ChannelError> {
        match self {
            SwarmMessage::StatusUpdate { progress_pct, .. } => {
                if *progress_pct > 100 {
                    return Err(ChannelError::SchemaMismatch(format!(
                        "progress_pct {} exceeds max 100",
                        progress_pct
                    )));
                }
                Ok(())
            }
            SwarmMessage::ArtifactReady { .. } => Ok(()),
            SwarmMessage::CommandDispatch { payload, .. } => {
                if !payload.is_object() {
                    return Err(ChannelError::SchemaMismatch(
                        "CommandDispatch.payload must be JSON object".to_string(),
                    ));
                }
                Ok(())
            }
            SwarmMessage::PixelProvenance { mandate_id, .. } => {
                if *mandate_id == Uuid::nil() {
                    return Err(ChannelError::SchemaMismatch(
                        "PixelProvenance.mandate_id cannot be nil".to_string(),
                    ));
                }
                Ok(())
            }
        }
    }
}

/// Broadcast channel for swarm-wide messaging.
pub struct SwarmChannel {
    sender: broadcast::Sender<SwarmMessage>,
}

impl SwarmChannel {
    pub fn new() -> Self {
        let (sender, _) = broadcast::channel(256);
        SwarmChannel { sender }
    }

    pub fn with_capacity(capacity: usize) -> Self {
        let (sender, _) = broadcast::channel(capacity);
        SwarmChannel { sender }
    }

    pub fn broadcast(&self, msg: SwarmMessage) -> Result<usize, ChannelError> {
        msg.validate()?;
        self.sender
            .send(msg)
            .map_err(|_| ChannelError::ChannelClosed)
    }

    pub fn subscribe(&self) -> broadcast::Receiver<SwarmMessage> {
        self.sender.subscribe()
    }
}

/// Snapshot of agent state at a point in time.
pub struct AgentStateSnapshot {
    pub agent_id: Uuid,
    pub state: String,
    pub progress: u8,
}

/// Error type for state operations.
#[derive(Debug, Error)]
pub enum StateError {
    #[error("database error: {0}")]
    DatabaseError(String),
}

/// Trait for swarm state ledger (database-backed).
pub trait SwarmStateLedger: Send + Sync {
    fn update_state(&self, agent_id: Uuid, state: &str, progress: u8) -> Result<(), StateError>;
    fn get_state(&self, agent_id: Uuid) -> Option<AgentStateSnapshot>;
}

/// In-memory implementation of SwarmStateLedger with idempotent upsert.
pub struct InMemorySwarmState {
    states: Mutex<HashMap<Uuid, AgentStateSnapshot>>,
}

impl InMemorySwarmState {
    pub fn new() -> Self {
        InMemorySwarmState {
            states: Mutex::new(HashMap::new()),
        }
    }
}

impl Default for InMemorySwarmState {
    fn default() -> Self {
        Self::new()
    }
}

impl SwarmStateLedger for InMemorySwarmState {
    fn update_state(&self, agent_id: Uuid, state: &str, progress: u8) -> Result<(), StateError> {
        let mut states = self.states.lock().unwrap();
        states.insert(
            agent_id,
            AgentStateSnapshot {
                agent_id,
                state: state.to_string(),
                progress,
            },
        );
        Ok(())
    }

    fn get_state(&self, agent_id: Uuid) -> Option<AgentStateSnapshot> {
        let states = self.states.lock().unwrap();
        states.get(&agent_id).map(|snapshot| AgentStateSnapshot {
            agent_id: snapshot.agent_id,
            state: snapshot.state.clone(),
            progress: snapshot.progress,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_swarm_message_valid_progress() {
        let msg = SwarmMessage::StatusUpdate {
            agent_id: Uuid::new_v4(),
            state: "running".to_string(),
            progress_pct: 100,
        };
        assert!(msg.validate().is_ok());
    }

    #[test]
    fn test_swarm_message_invalid_progress() {
        let msg = SwarmMessage::StatusUpdate {
            agent_id: Uuid::new_v4(),
            state: "running".to_string(),
            progress_pct: 101,
        };
        assert!(msg.validate().is_err());
    }

    #[test]
    fn test_claim_ledger_release() {
        let ledger = InMemoryClaimLedger::new();
        let agent = Uuid::new_v4();

        ledger.claim("wt", "file.rs", agent).unwrap();
        assert!(ledger.is_claimed("wt", "file.rs"));

        ledger.release("wt", "file.rs", agent);
        assert!(!ledger.is_claimed("wt", "file.rs"));
    }
}
