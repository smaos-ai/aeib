/// Phase 51: AoE Telemetry Hub + Kill Switch
/// Agent state tracking + tmux termination for stalled agents.
use crate::ag_ui::AgentState;
use crate::orchestrator::TmuxSpawner;
use crate::swarm_channel::{InMemorySwarmState, SwarmChannel, SwarmMessage};
use chrono::{DateTime, Utc};
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use uuid::Uuid;

#[derive(Debug, Clone)]
pub struct AgentTelemetry {
    pub agent_id: Uuid,
    pub state: AgentState,
    pub progress: u8,
    pub last_updated: DateTime<Utc>,
    pub worktree: String,
    pub tmux_name: String,
}

#[derive(Debug, PartialEq, Eq)]
pub enum TelemetryError {
    AgentNotFound(Uuid),
    KillFailed(String),
}

pub struct AoETelemetryHub<T: TmuxSpawner> {
    tmux: T,
    ledger: Arc<InMemorySwarmState>,
    registry: Arc<Mutex<HashMap<Uuid, AgentTelemetry>>>,
    channel: Arc<SwarmChannel>,
}

impl<T: TmuxSpawner> AoETelemetryHub<T> {
    pub fn new(tmux: T, ledger: Arc<InMemorySwarmState>, channel: Arc<SwarmChannel>) -> Self {
        AoETelemetryHub {
            tmux,
            ledger,
            registry: Arc::new(Mutex::new(HashMap::new())),
            channel,
        }
    }

    /// Register or update an agent's telemetry.
    /// Writes to registry + broadcasts SwarmMessage::StatusUpdate via channel.
    pub fn report(
        &self,
        agent_id: Uuid,
        state: AgentState,
        progress: u8,
        worktree: &str,
        tmux_name: &str,
    ) -> Result<(), TelemetryError> {
        let telemetry = AgentTelemetry {
            agent_id,
            state: state.clone(),
            progress,
            last_updated: Utc::now(),
            worktree: worktree.to_string(),
            tmux_name: tmux_name.to_string(),
        };

        let mut registry = self.registry.lock().unwrap();
        registry.insert(agent_id, telemetry);

        // Broadcast status update
        self.channel.broadcast(SwarmMessage::StatusUpdate {
            agent_id,
            state: state.as_str().to_string(),
            progress_pct: progress,
        });

        Ok(())
    }

    /// Retrieve current telemetry for a specific agent.
    pub fn get(&self, agent_id: Uuid) -> Option<AgentTelemetry> {
        let registry = self.registry.lock().unwrap();
        registry.get(&agent_id).cloned()
    }

    /// Kill switch: terminate the tmux session for the given agent.
    /// RULE A: Agent must be in registry → Err(AgentNotFound) if not
    /// RULE B: call tmux.kill(&telemetry.tmux_name).await
    /// RULE C: Update agent state to AgentState::Error in registry
    pub async fn kill_switch(&self, agent_id: Uuid) -> Result<(), TelemetryError> {
        // RULE A: Agent must be in registry
        let telemetry = {
            let registry = self.registry.lock().unwrap();
            registry.get(&agent_id).cloned()
        };

        let telemetry = telemetry.ok_or(TelemetryError::AgentNotFound(agent_id))?;

        // RULE B: Kill the tmux session
        self.tmux.kill(&telemetry.tmux_name).await;

        // RULE C: Update agent state to Error in registry
        {
            let mut registry = self.registry.lock().unwrap();
            if let Some(entry) = registry.get_mut(&agent_id) {
                entry.state = AgentState::Error;
            }
        }

        Ok(())
    }
}
