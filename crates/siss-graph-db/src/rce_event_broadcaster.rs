/// Phase 37: RCE Event Broadcaster
///
/// Broadcast RCE state transitions and interrupt signals via tokio::sync::broadcast.
/// Consumed by SSE handler to stream events to clients.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use tokio::sync::broadcast;
use uuid::Uuid;

use crate::rce::{ExecutionState, Step};

// =====================================================================
// RCE EVENT TYPES
// =====================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum RceEvent {
    WorkflowStarted {
        workflow_id: Uuid,
        timestamp: DateTime<Utc>,
        step_count: usize,
        plan: Vec<Step>,
    },
    WorkflowPaused {
        workflow_id: Uuid,
        timestamp: DateTime<Utc>,
        step_index: usize,
        step_id: Uuid,
        step_name: String,
        interrupt_reason: String,
        interrupt_severity: String,
    },
    WorkflowResumed {
        workflow_id: Uuid,
        timestamp: DateTime<Utc>,
        step_index: usize,
        decision: String, // "approve", "reject", "modify"
    },
    WorkflowRejected {
        workflow_id: Uuid,
        timestamp: DateTime<Utc>,
        reason: String,
    },
    WorkflowCompleted {
        workflow_id: Uuid,
        timestamp: DateTime<Utc>,
        total_steps: usize,
    },
}

impl RceEvent {
    pub fn event_type(&self) -> &str {
        match self {
            RceEvent::WorkflowStarted { .. } => "workflow_started",
            RceEvent::WorkflowPaused { .. } => "workflow_paused",
            RceEvent::WorkflowResumed { .. } => "workflow_resumed",
            RceEvent::WorkflowRejected { .. } => "workflow_rejected",
            RceEvent::WorkflowCompleted { .. } => "workflow_completed",
        }
    }

    pub fn timestamp(&self) -> DateTime<Utc> {
        match self {
            RceEvent::WorkflowStarted { timestamp, .. } => *timestamp,
            RceEvent::WorkflowPaused { timestamp, .. } => *timestamp,
            RceEvent::WorkflowResumed { timestamp, .. } => *timestamp,
            RceEvent::WorkflowRejected { timestamp, .. } => *timestamp,
            RceEvent::WorkflowCompleted { timestamp, .. } => *timestamp,
        }
    }

    pub fn workflow_id(&self) -> Uuid {
        match self {
            RceEvent::WorkflowStarted { workflow_id, .. } => *workflow_id,
            RceEvent::WorkflowPaused { workflow_id, .. } => *workflow_id,
            RceEvent::WorkflowResumed { workflow_id, .. } => *workflow_id,
            RceEvent::WorkflowRejected { workflow_id, .. } => *workflow_id,
            RceEvent::WorkflowCompleted { workflow_id, .. } => *workflow_id,
        }
    }
}

// =====================================================================
// BROADCASTER
// =====================================================================

#[derive(Debug)]
pub struct RceEventBroadcaster {
    tx: broadcast::Sender<RceEvent>,
}

impl RceEventBroadcaster {
    /// Create a new broadcaster with capacity 256 for RCE events
    pub fn new() -> Self {
        let (tx, _) = broadcast::channel(256);
        Self { tx }
    }

    /// Emit an event (fire-and-forget; errors if no subscribers)
    pub fn emit(&self, event: RceEvent) {
        let _ = self.tx.send(event);
    }

    /// Subscribe to receive RCE events
    pub fn subscribe(&self) -> broadcast::Receiver<RceEvent> {
        self.tx.subscribe()
    }
}

impl Default for RceEventBroadcaster {
    fn default() -> Self {
        Self::new()
    }
}
