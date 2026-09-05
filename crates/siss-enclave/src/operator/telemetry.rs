use serde::{Deserialize, Serialize};
use tokio::sync::broadcast;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum SwapEventKind {
    Queued,
    Distilling,
    AlignmentGateRunning,
    Authorized {
        swap_token: String,
        new_lora_id: String,
    },
    Blocked {
        reason: String,
    },
    Quarantined {
        task_id: Uuid,
        reason: String,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LoraSwapEvent {
    pub task_id: Uuid,
    pub agent_id: String,
    pub kind: SwapEventKind,
    pub timestamp_ms: u64,
}

pub struct OperatorTelemetry {
    tx: broadcast::Sender<LoraSwapEvent>,
}

impl OperatorTelemetry {
    pub fn new() -> (Self, broadcast::Receiver<LoraSwapEvent>) {
        let (tx, rx) = broadcast::channel(64);
        (Self { tx }, rx)
    }

    pub fn emit(&self, event: LoraSwapEvent) {
        let _ = self.tx.send(event);
    }

    pub fn subscribe(&self) -> broadcast::Receiver<LoraSwapEvent> {
        self.tx.subscribe()
    }
}

impl Default for OperatorTelemetry {
    fn default() -> Self {
        Self::new().0
    }
}
