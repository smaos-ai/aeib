/// Chaos Petri Quarantine: Type-State RCE Failure Machine
/// Infrastructure failures (network drops, MCP socket loss, malformed mandates) trigger
/// deterministic state transitions without panicking or crashing the host.
use std::collections::VecDeque;
use std::marker::PhantomData;
use uuid::Uuid;

// Type-state markers (zero-cost)
pub struct Running;
pub struct Paused;

#[derive(Debug, Clone)]
pub enum ChaosInjection {
    NetworkDropout { duration_ms: u64 },
    McpSocketDrop { socket_path: String },
    MalformedMandate { reason: String },
}

pub struct RceStateMachine<S> {
    pub agent_id: Uuid,
    pub queued_commands: VecDeque<String>,
    _state: PhantomData<S>,
}

#[derive(Debug, PartialEq, Eq)]
pub enum ChaosError {
    NetworkDropout { agent_id: Uuid },
    McpDropout { socket_path: String },
    MalformedMandateRejected { reason: String },
}

impl RceStateMachine<Running> {
    pub fn new(agent_id: Uuid) -> Self {
        RceStateMachine {
            agent_id,
            queued_commands: VecDeque::new(),
            _state: PhantomData,
        }
    }

    pub fn add_command(&mut self, command: String) {
        self.queued_commands.push_back(command);
    }

    /// RULE A: Any ChaosInjection variant → consumes Running, returns Paused.
    /// RULE B: No crash(), no Running→Failed edge — type system enforces this.
    /// RULE C: queued_commands preserved across transition.
    pub fn inject_failure(self, _chaos: ChaosInjection) -> RceStateMachine<Paused> {
        RceStateMachine {
            agent_id: self.agent_id,
            queued_commands: self.queued_commands,
            _state: PhantomData,
        }
    }
}

impl RceStateMachine<Paused> {
    /// Consumes Paused; returns (Running, commands drained in FIFO order).
    pub fn resume(self) -> (RceStateMachine<Running>, Vec<String>) {
        let mut drained = Vec::new();
        let mut queued = self.queued_commands;
        while let Some(cmd) = queued.pop_front() {
            drained.push(cmd);
        }

        let resumed = RceStateMachine {
            agent_id: self.agent_id,
            queued_commands: VecDeque::new(),
            _state: PhantomData,
        };

        (resumed, drained)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_network_dropout_pauses() {
        let agent_id = Uuid::new_v4();
        let rce = RceStateMachine::new(agent_id);
        let chaos = ChaosInjection::NetworkDropout { duration_ms: 100 };
        let paused = rce.inject_failure(chaos);
        let (running, _) = paused.resume();
        assert_eq!(running.agent_id, agent_id);
    }

    #[test]
    fn test_queue_fifo() {
        let agent_id = Uuid::new_v4();
        let mut rce = RceStateMachine::new(agent_id);
        rce.add_command("cmd1".to_string());
        rce.add_command("cmd2".to_string());
        rce.add_command("cmd3".to_string());

        let chaos = ChaosInjection::NetworkDropout { duration_ms: 100 };
        let paused = rce.inject_failure(chaos);
        let (_running, drained) = paused.resume();

        assert_eq!(drained, vec!["cmd1", "cmd2", "cmd3"]);
    }
}
