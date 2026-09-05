//! L5 Error Handling: MCP server communication and agent-to-agent messaging
//! Handles network failures, message routing, and protocol errors

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Error, Debug, Clone, Serialize, Deserialize)]
pub enum L5Error {
    #[error("Server registration failed: {reason}. Recovery: {recovery}")]
    ServerRegistrationFailed {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Message routing failed: {reason}. Recovery: {recovery}")]
    MessageRoutingFailed {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Agent not found: {agent_id}. Recovery: {recovery}")]
    AgentNotFound {
        agent_id: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Protocol error: {reason}. Recovery: {recovery}")]
    ProtocolError {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Message serialization failed: {reason}. Recovery: {recovery}")]
    SerializationFailed {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Communication timeout: exceeded {timeout_ms}ms. Recovery: {recovery}")]
    CommunicationTimeout {
        timeout_ms: u64,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Invalid message format: {reason}. Recovery: {recovery}")]
    InvalidMessageFormat {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },
}

impl L5Error {
    pub fn reason(&self) -> String {
        match self {
            Self::ServerRegistrationFailed { reason, .. } => reason.clone(),
            Self::MessageRoutingFailed { reason, .. } => reason.clone(),
            Self::AgentNotFound { agent_id, .. } => format!("Agent {} not in registry", agent_id),
            Self::ProtocolError { reason, .. } => reason.clone(),
            Self::SerializationFailed { reason, .. } => reason.clone(),
            Self::CommunicationTimeout { timeout_ms, .. } => {
                format!("Message send exceeded {}ms", timeout_ms)
            }
            Self::InvalidMessageFormat { reason, .. } => reason.clone(),
        }
    }

    pub fn timestamp(&self) -> DateTime<Utc> {
        match self {
            Self::ServerRegistrationFailed { timestamp, .. }
            | Self::MessageRoutingFailed { timestamp, .. }
            | Self::AgentNotFound { timestamp, .. }
            | Self::ProtocolError { timestamp, .. }
            | Self::SerializationFailed { timestamp, .. }
            | Self::CommunicationTimeout { timestamp, .. }
            | Self::InvalidMessageFormat { timestamp, .. } => *timestamp,
        }
    }

    pub fn recovery(&self) -> String {
        match self {
            Self::ServerRegistrationFailed { recovery, .. }
            | Self::MessageRoutingFailed { recovery, .. }
            | Self::AgentNotFound { recovery, .. }
            | Self::ProtocolError { recovery, .. }
            | Self::SerializationFailed { recovery, .. }
            | Self::CommunicationTimeout { recovery, .. }
            | Self::InvalidMessageFormat { recovery, .. } => recovery.clone(),
        }
    }
}

/// AuditEntry for communication in L5
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct L5AuditEntry {
    pub timestamp: DateTime<Utc>,
    pub event_id: String,
    pub sender: String,
    pub recipient: String,
    pub message_type: String,
    pub error: Option<String>,
    pub latency_ms: u64,
    pub success: bool,
}

impl L5AuditEntry {
    pub fn new(sender: String, recipient: String, message_type: String) -> Self {
        Self {
            timestamp: Utc::now(),
            event_id: uuid::Uuid::new_v4().to_string(),
            sender,
            recipient,
            message_type,
            error: None,
            latency_ms: 0,
            success: true,
        }
    }

    pub fn with_error(mut self, error: L5Error) -> Self {
        self.error = Some(format!("{:?}", error));
        self.success = false;
        self
    }

    pub fn with_latency(mut self, latency_ms: u64) -> Self {
        self.latency_ms = latency_ms;
        self
    }
}

/// Input validation for L5
pub fn validate_agent_id(agent_id: &str) -> Result<(), L5Error> {
    if agent_id.is_empty() {
        return Err(L5Error::AgentNotFound {
            agent_id: agent_id.to_string(),
            recovery: "Provide non-empty agent ID (e.g., 'hotel-pilot')".to_string(),
            timestamp: Utc::now(),
        });
    }
    if agent_id.len() > 255 {
        return Err(L5Error::AgentNotFound {
            agent_id: agent_id.to_string(),
            recovery: "Shorten agent ID to <= 255 chars".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

pub fn validate_server_name(server_name: &str) -> Result<(), L5Error> {
    if server_name.is_empty() {
        return Err(L5Error::ServerRegistrationFailed {
            reason: "Server name cannot be empty".to_string(),
            recovery: "Provide non-empty server name (e.g., 'palace-mcp')".to_string(),
            timestamp: Utc::now(),
        });
    }
    if server_name.len() > 255 {
        return Err(L5Error::ServerRegistrationFailed {
            reason: "Server name exceeds 255 characters".to_string(),
            recovery: "Shorten server name".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

pub fn validate_message_content(content: &str) -> Result<(), L5Error> {
    if content.is_empty() {
        return Err(L5Error::InvalidMessageFormat {
            reason: "Message content cannot be empty".to_string(),
            recovery: "Provide non-empty message body".to_string(),
            timestamp: Utc::now(),
        });
    }
    if content.len() > 1_000_000 {
        return Err(L5Error::InvalidMessageFormat {
            reason: "Message content exceeds 1MB".to_string(),
            recovery: "Split message into smaller chunks".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

pub fn validate_server_url(url: &str) -> Result<(), L5Error> {
    if url.is_empty() {
        return Err(L5Error::ServerRegistrationFailed {
            reason: "Server URL cannot be empty".to_string(),
            recovery: "Provide valid server URL (e.g., http://localhost:3000)".to_string(),
            timestamp: Utc::now(),
        });
    }
    if !url.starts_with("http://")
        && !url.starts_with("https://")
        && !url.starts_with("ws://")
        && !url.starts_with("wss://")
    {
        return Err(L5Error::ServerRegistrationFailed {
            reason: "Invalid server URL scheme".to_string(),
            recovery: "Use http://, https://, ws://, or wss://".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_validate_agent_id_empty() {
        let result = validate_agent_id("");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_agent_id_too_long() {
        let long_id = "a".repeat(300);
        let result = validate_agent_id(&long_id);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_server_name_empty() {
        let result = validate_server_name("");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_server_name_valid() {
        let result = validate_server_name("palace-mcp");
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_message_content_empty() {
        let result = validate_message_content("");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_message_content_too_large() {
        let large_content = "x".repeat(1_000_001);
        let result = validate_message_content(&large_content);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_server_url_invalid_scheme() {
        let result = validate_server_url("ftp://example.com");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_server_url_valid() {
        assert!(validate_server_url("http://localhost:3000").is_ok());
        assert!(validate_server_url("https://example.com").is_ok());
        assert!(validate_server_url("ws://localhost:3001").is_ok());
    }

    #[test]
    fn test_audit_entry_with_error() {
        let entry = L5AuditEntry::new(
            "agent1".to_string(),
            "agent2".to_string(),
            "request".to_string(),
        );
        let error = L5Error::AgentNotFound {
            agent_id: "agent2".to_string(),
            recovery: "check registry".to_string(),
            timestamp: Utc::now(),
        };
        let entry = entry.with_error(error);
        assert!(!entry.success);
        assert!(entry.error.is_some());
    }

    #[test]
    fn test_audit_entry_with_latency() {
        let entry = L5AuditEntry::new(
            "agent1".to_string(),
            "agent2".to_string(),
            "request".to_string(),
        );
        let entry = entry.with_latency(150);
        assert_eq!(entry.latency_ms, 150);
    }

    #[test]
    fn test_audit_entry_success_by_default() {
        let entry = L5AuditEntry::new(
            "agent1".to_string(),
            "agent2".to_string(),
            "request".to_string(),
        );
        assert!(entry.success);
    }
}
