use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use thiserror::Error;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum AgentState {
    #[serde(rename = "idle")]
    Idle,
    #[serde(rename = "running")]
    Running,
    #[serde(rename = "paused")]
    Paused,
    #[serde(rename = "failed")]
    Failed,
    #[serde(rename = "completed")]
    Completed,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentStatus {
    pub agent_id: String,
    pub state: AgentState,
    pub memory_mb: u32,
    pub tasks_active: usize,
    pub timestamp_ms: u64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metadata: Option<HashMap<String, String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum WsMessage {
    #[serde(rename = "agent_status")]
    AgentStatus(AgentStatus),
    #[serde(rename = "heartbeat")]
    Heartbeat { timestamp_ms: u64 },
    #[serde(rename = "error")]
    Error { message: String },
    #[serde(rename = "ack")]
    Ack { request_id: String },
}

#[derive(Debug, Error)]
pub enum ConsoleError {
    #[error("WebSocket connection error: {0}")]
    WsError(String),

    #[error("USB tunnel error: {0}")]
    UsbError(String),

    #[error("Serialization error: {0}")]
    SerializationError(#[from] serde_json::Error),

    #[error("Frame encoding error: {0}")]
    FrameError(String),

    #[error("Accessibility error: {0}")]
    A11yError(String),

    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_agent_state_serialization() {
        let state = AgentState::Running;
        let json = serde_json::to_string(&state).unwrap();
        assert_eq!(json, "\"running\"");
    }

    #[test]
    fn test_agent_status_creation() {
        let status = AgentStatus {
            agent_id: "alpha_001".to_string(),
            state: AgentState::Running,
            memory_mb: 256,
            tasks_active: 3,
            timestamp_ms: 1719072747000,
            error: None,
            metadata: None,
        };
        assert_eq!(status.agent_id, "alpha_001");
        assert_eq!(status.memory_mb, 256);
    }

    #[test]
    fn test_ws_message_agent_status() {
        let status = AgentStatus {
            agent_id: "alpha_001".to_string(),
            state: AgentState::Running,
            memory_mb: 256,
            tasks_active: 3,
            timestamp_ms: 1719072747000,
            error: None,
            metadata: None,
        };
        let msg = WsMessage::AgentStatus(status);
        let json = serde_json::to_string(&msg).unwrap();
        assert!(json.contains("agent_status"));
        assert!(json.contains("alpha_001"));
    }

    #[test]
    fn test_ws_message_heartbeat() {
        let msg = WsMessage::Heartbeat {
            timestamp_ms: 1719072747000,
        };
        let json = serde_json::to_string(&msg).unwrap();
        assert!(json.contains("heartbeat"));
    }

    #[test]
    fn test_agent_status_with_error() {
        let status = AgentStatus {
            agent_id: "beta_002".to_string(),
            state: AgentState::Failed,
            memory_mb: 512,
            tasks_active: 0,
            timestamp_ms: 1719072747000,
            error: Some("Task execution timeout".to_string()),
            metadata: None,
        };
        assert_eq!(status.error, Some("Task execution timeout".to_string()));
    }

    #[test]
    fn test_agent_status_with_metadata() {
        let mut metadata = HashMap::new();
        metadata.insert("hardware_target".to_string(), "gpu_ml3".to_string());
        let status = AgentStatus {
            agent_id: "gamma_003".to_string(),
            state: AgentState::Running,
            memory_mb: 1024,
            tasks_active: 5,
            timestamp_ms: 1719072747000,
            error: None,
            metadata: Some(metadata),
        };
        assert!(status.metadata.is_some());
    }
}
