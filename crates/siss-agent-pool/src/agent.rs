use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Agent status
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum AgentStatus {
    Idle,
    Running,
    Draining,
    Shutdown,
}

/// Agent state (for migration)
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AgentState {
    pub decisions_made: u64,
    pub tokens_consumed: u64,
    pub context_window: Vec<String>,
}

impl Default for AgentState {
    fn default() -> Self {
        Self {
            decisions_made: 0,
            tokens_consumed: 0,
            context_window: Vec::new(),
        }
    }
}

/// Agent in pool
#[derive(Clone, Debug)]
pub struct Agent {
    pub id: Uuid,
    pub status: AgentStatus,
    pub state: AgentState,
    pub created_at: i64,
    pub last_activity: i64,
}

impl Agent {
    /// Create new agent
    pub fn new() -> Self {
        let now = chrono::Utc::now().timestamp();
        Self {
            id: Uuid::new_v4(),
            status: AgentStatus::Idle,
            state: AgentState::default(),
            created_at: now,
            last_activity: now,
        }
    }

    /// Mark agent as running
    pub fn start_running(&mut self) {
        self.status = AgentStatus::Running;
        self.last_activity = chrono::Utc::now().timestamp();
    }

    /// Mark agent as idle
    pub fn become_idle(&mut self) {
        self.status = AgentStatus::Idle;
        self.last_activity = chrono::Utc::now().timestamp();
    }

    /// Start draining agent
    pub fn start_drain(&mut self) {
        self.status = AgentStatus::Draining;
        self.last_activity = chrono::Utc::now().timestamp();
    }

    /// Shutdown agent
    pub fn shutdown(&mut self) {
        self.status = AgentStatus::Shutdown;
        self.last_activity = chrono::Utc::now().timestamp();
    }

    /// Uptime in seconds
    pub fn uptime_secs(&self) -> u64 {
        let now = chrono::Utc::now().timestamp();
        (now - self.created_at) as u64
    }

    /// Idle time in seconds
    pub fn idle_time_secs(&self) -> u64 {
        let now = chrono::Utc::now().timestamp();
        (now - self.last_activity) as u64
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_agent_creation() {
        let agent = Agent::new();
        assert_eq!(agent.status, AgentStatus::Idle);
        assert_eq!(agent.state.decisions_made, 0);
    }

    #[test]
    fn test_agent_status_transitions() {
        let mut agent = Agent::new();
        assert_eq!(agent.status, AgentStatus::Idle);

        agent.start_running();
        assert_eq!(agent.status, AgentStatus::Running);

        agent.become_idle();
        assert_eq!(agent.status, AgentStatus::Idle);

        agent.start_drain();
        assert_eq!(agent.status, AgentStatus::Draining);

        agent.shutdown();
        assert_eq!(agent.status, AgentStatus::Shutdown);
    }

    #[test]
    fn test_agent_uptime() {
        let agent = Agent::new();
        let uptime = agent.uptime_secs();
        assert!(uptime >= 0);
        assert!(uptime < 2);
    }
}
