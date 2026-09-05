/// Agent Status Emitter Module
///
/// Emits [AGENT_STATUS] flags for integration with the AoE orchestrator.
/// Status transitions: running -> idle -> waiting -> error (or back to running)

/// Represents the agent's operational state
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AgentState {
    Running,
    Idle,
    Waiting,
    Error,
    Suspended,
}

impl AgentState {
    /// Convert state to string for emission
    pub fn as_str(&self) -> &'static str {
        match self {
            AgentState::Running => "running",
            AgentState::Idle => "idle",
            AgentState::Waiting => "waiting",
            AgentState::Error => "error",
            AgentState::Suspended => "suspended",
        }
    }
}

/// Emits agent status in AoE format to stdout
pub fn emit_agent_status(state: AgentState) {
    println!("[AGENT_STATUS] state={}", state.as_str());
}

/// Session manager that tracks agent state and emits status on transitions
#[derive(Debug)]
pub struct AgentSessionManager {
    current_state: AgentState,
}

impl AgentSessionManager {
    /// Create a new session manager (initially idle)
    pub fn new() -> Self {
        Self {
            current_state: AgentState::Idle,
        }
    }

    /// Transition to a new state and emit the status change
    pub fn transition_to(&mut self, new_state: AgentState) {
        if self.current_state != new_state {
            self.current_state = new_state;
            emit_agent_status(new_state);
        }
    }

    /// Start the session (emit running)
    pub fn start_session(&mut self) {
        self.transition_to(AgentState::Running);
    }

    /// End the session (emit idle)
    pub fn end_session(&mut self) {
        self.transition_to(AgentState::Idle);
    }

    /// Mark session as waiting for input
    pub fn set_waiting(&mut self) {
        self.transition_to(AgentState::Waiting);
    }

    /// Mark session as having an error
    pub fn set_error(&mut self) {
        self.transition_to(AgentState::Error);
    }

    /// Get the current state
    pub fn current_state(&self) -> AgentState {
        self.current_state
    }
}

impl Default for AgentSessionManager {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_agent_state_as_str() {
        assert_eq!(AgentState::Running.as_str(), "running");
        assert_eq!(AgentState::Idle.as_str(), "idle");
        assert_eq!(AgentState::Waiting.as_str(), "waiting");
        assert_eq!(AgentState::Error.as_str(), "error");
    }

    #[test]
    fn test_session_manager_initialization() {
        let manager = AgentSessionManager::new();
        assert_eq!(manager.current_state(), AgentState::Idle);
    }

    #[test]
    fn test_session_start() {
        let mut manager = AgentSessionManager::new();
        manager.start_session();
        assert_eq!(manager.current_state(), AgentState::Running);
    }

    #[test]
    fn test_session_end() {
        let mut manager = AgentSessionManager::new();
        manager.start_session();
        manager.end_session();
        assert_eq!(manager.current_state(), AgentState::Idle);
    }

    #[test]
    fn test_session_state_transitions() {
        let mut manager = AgentSessionManager::new();

        manager.transition_to(AgentState::Running);
        assert_eq!(manager.current_state(), AgentState::Running);

        manager.transition_to(AgentState::Waiting);
        assert_eq!(manager.current_state(), AgentState::Waiting);

        manager.transition_to(AgentState::Error);
        assert_eq!(manager.current_state(), AgentState::Error);

        manager.transition_to(AgentState::Running);
        assert_eq!(manager.current_state(), AgentState::Running);
    }

    #[test]
    fn test_status_format() {
        let states = vec!["running", "idle", "waiting", "error", "suspended"];
        for state_str in states {
            let msg = format!("[AGENT_STATUS] state={}", state_str);
            assert!(
                msg.starts_with("[AGENT_STATUS]"),
                "Status message should start with [AGENT_STATUS]"
            );
            assert!(
                msg.contains(&format!("state={}", state_str)),
                "Status message should contain state field"
            );
        }
    }
}
