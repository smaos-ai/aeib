pub mod callback;
pub mod collecting;
pub mod emitter;

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use siss_behavioral_firewall::types::Verdict;
use siss_graph_core::node::execution::HardwareTarget;

/// All event types emitted by the AG-UI protocol.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AgentEvent {
    SessionStarted {
        session_id: Uuid,
        persona_id: Uuid,
        timestamp: DateTime<Utc>,
    },
    SessionClosed {
        session_id: Uuid,
        timestamp: DateTime<Utc>,
    },
    HookFired {
        hook_name: String,
        hook_point: HookPoint,
        result: HookResultSummary,
        timestamp: DateTime<Utc>,
    },
    TaskCreated {
        task_id: Uuid,
        intent: String,
        timestamp: DateTime<Utc>,
    },
    Authorized {
        task_id: Uuid,
        mandate_id: Uuid,
        timestamp: DateTime<Utc>,
    },
    Routed {
        task_id: Uuid,
        hardware_target: HardwareTarget,
        timestamp: DateTime<Utc>,
    },
    OutputChunk {
        task_id: Uuid,
        chunk: serde_json::Value,
        index: u32,
        timestamp: DateTime<Utc>,
    },
    Executing {
        task_id: Uuid,
        token_cost: i64,
        duration_ms: u64,
        timestamp: DateTime<Utc>,
    },
    FirewallInspected {
        task_id: Uuid,
        verdict: Verdict,
        violation_count: usize,
        timestamp: DateTime<Utc>,
    },
    Scored {
        task_id: Uuid,
        quality_score: f64,
        timestamp: DateTime<Utc>,
    },
    Crystallized {
        task_id: Uuid,
        memory_count: usize,
        timestamp: DateTime<Utc>,
    },
    IntentCompleted {
        task_id: Uuid,
        quality_score: f64,
        timestamp: DateTime<Utc>,
    },
    Error {
        message: String,
        timestamp: DateTime<Utc>,
    },
}

/// Which lifecycle hook point fired.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum HookPoint {
    SessionStart,
    PreExecution,
    PostExecution,
    PreToolUse,
    PostToolUse,
    Stop,
}

/// Summary of a hook's result for event reporting.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum HookResultSummary {
    Continue,
    Halted(String),
    Denied(String),
}

impl AgentEvent {
    /// Get the event type name for logging/filtering.
    pub fn event_type(&self) -> &'static str {
        match self {
            Self::SessionStarted { .. } => "session_started",
            Self::SessionClosed { .. } => "session_closed",
            Self::HookFired { .. } => "hook_fired",
            Self::TaskCreated { .. } => "task_created",
            Self::Authorized { .. } => "authorized",
            Self::Routed { .. } => "routed",
            Self::OutputChunk { .. } => "output_chunk",
            Self::Executing { .. } => "executing",
            Self::FirewallInspected { .. } => "firewall_inspected",
            Self::Scored { .. } => "scored",
            Self::Crystallized { .. } => "crystallized",
            Self::IntentCompleted { .. } => "intent_completed",
            Self::Error { .. } => "error",
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_event_type_names() {
        let event = AgentEvent::SessionStarted {
            session_id: Uuid::nil(),
            persona_id: Uuid::nil(),
            timestamp: Utc::now(),
        };
        assert_eq!(event.event_type(), "session_started");
    }

    #[test]
    fn test_event_serialization() {
        let event = AgentEvent::TaskCreated {
            task_id: Uuid::nil(),
            intent: "test".into(),
            timestamp: Utc::now(),
        };
        let json = serde_json::to_string(&event).unwrap();
        assert!(json.contains("task_created") || json.contains("TaskCreated"));
    }

    #[test]
    fn test_all_13_event_types() {
        let now = Utc::now();
        let events = vec![
            AgentEvent::SessionStarted {
                session_id: Uuid::nil(),
                persona_id: Uuid::nil(),
                timestamp: now,
            },
            AgentEvent::SessionClosed {
                session_id: Uuid::nil(),
                timestamp: now,
            },
            AgentEvent::HookFired {
                hook_name: "test".into(),
                hook_point: HookPoint::PreExecution,
                result: HookResultSummary::Continue,
                timestamp: now,
            },
            AgentEvent::TaskCreated {
                task_id: Uuid::nil(),
                intent: "x".into(),
                timestamp: now,
            },
            AgentEvent::Authorized {
                task_id: Uuid::nil(),
                mandate_id: Uuid::nil(),
                timestamp: now,
            },
            AgentEvent::Routed {
                task_id: Uuid::nil(),
                hardware_target: HardwareTarget::LocalMlx,
                timestamp: now,
            },
            AgentEvent::OutputChunk {
                task_id: Uuid::nil(),
                chunk: serde_json::json!("hi"),
                index: 0,
                timestamp: now,
            },
            AgentEvent::Executing {
                task_id: Uuid::nil(),
                token_cost: 100,
                duration_ms: 10,
                timestamp: now,
            },
            AgentEvent::FirewallInspected {
                task_id: Uuid::nil(),
                verdict: Verdict::Clear,
                violation_count: 0,
                timestamp: now,
            },
            AgentEvent::Scored {
                task_id: Uuid::nil(),
                quality_score: 0.75,
                timestamp: now,
            },
            AgentEvent::Crystallized {
                task_id: Uuid::nil(),
                memory_count: 1,
                timestamp: now,
            },
            AgentEvent::IntentCompleted {
                task_id: Uuid::nil(),
                quality_score: 0.75,
                timestamp: now,
            },
            AgentEvent::Error {
                message: "fail".into(),
                timestamp: now,
            },
        ];
        assert_eq!(events.len(), 13);
    }
}
