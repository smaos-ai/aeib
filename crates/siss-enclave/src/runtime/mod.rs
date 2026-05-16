use crate::operator::{HitlVerdict, OperatorCockpit};
use uuid::Uuid;

#[derive(Debug, Clone, PartialEq)]
pub enum ExecutionState {
    Running,
    Paused { reason: String, checkpoint_id: Uuid },
    Completed,
}

pub struct ResumableCognitiveExecution {
    cockpit: OperatorCockpit,
    running: bool,
}

impl ResumableCognitiveExecution {
    pub fn new(cockpit: OperatorCockpit) -> Self {
        Self {
            cockpit,
            running: false,
        }
    }

    pub async fn start_trajectory(&mut self) {
        self.running = true;
    }

    pub async fn step_execution(&mut self) -> ExecutionState {
        if self.cockpit.has_active_drop("rapid-mlx-backend") {
            self.cockpit.set_agent_verdict(HitlVerdict::Suspended);
            return ExecutionState::Paused {
                reason: "rapid-mlx-backend offline".to_string(),
                checkpoint_id: Uuid::new_v4(),
            };
        }

        if self.cockpit.has_active_drop("openclaw-gateway") {
            self.cockpit.set_agent_verdict(HitlVerdict::Suspended);
            return ExecutionState::Paused {
                reason: "openclaw-gateway offline".to_string(),
                checkpoint_id: Uuid::new_v4(),
            };
        }

        if self.running {
            ExecutionState::Running
        } else {
            ExecutionState::Completed
        }
    }
}
