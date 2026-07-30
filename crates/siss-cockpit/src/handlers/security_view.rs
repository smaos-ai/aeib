/// Phase 34: Security View Handler
/// Integrates AoE session streams with A2UI components via streaming gateway

use std::sync::Arc;
use uuid::Uuid;
use serde::{Deserialize, Serialize};
use siss_agent_shell::ag_ui::sse_consumer::AoEEvent;
use crate::a2ui::security_dashboard::SecurityDashboard;
use crate::a2ui::streaming_gateway::A2UIStreamingGateway;
use crate::handlers::aoe_cockpit::AoECockpit;

/// Request to initiate a security view stream
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityStreamRequest {
    pub bearer_token: Option<String>,
    pub tmux_name: String,
}

/// Response from starting a security stream
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityStreamResponse {
    pub session_id: String,
    pub stream_url: String,
}

/// Error type for security view operations
#[derive(Debug, Clone, PartialEq)]
pub enum SecurityViewError {
    Unauthorized,
    SessionNotFound,
    SessionCapExceeded,
    StreamingError(String),
    GatewayError(String),
}

impl std::fmt::Display for SecurityViewError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Unauthorized => write!(f, "Unauthorized: missing or invalid bearer token"),
            Self::SessionNotFound => write!(f, "Session not found"),
            Self::SessionCapExceeded => write!(f, "Session capacity exceeded (max 10 concurrent)"),
            Self::StreamingError(msg) => write!(f, "Streaming error: {}", msg),
            Self::GatewayError(msg) => write!(f, "Gateway error: {}", msg),
        }
    }
}

impl std::error::Error for SecurityViewError {}

/// Security View Handler — manages AoE session streaming and component publishing
pub struct SecurityViewHandler {
    cockpit: Arc<AoECockpit>,
    gateway: Arc<A2UIStreamingGateway>,
    max_sessions: usize,
}

impl SecurityViewHandler {
    /// Create a new security view handler
    pub fn new(gateway: Arc<A2UIStreamingGateway>) -> Self {
        Self {
            cockpit: Arc::new(AoECockpit),
            gateway,
            max_sessions: 10,
        }
    }

    /// Start security view for a session
    pub async fn start_security_view(
        &self,
        session_id: &str,
    ) -> Result<(), SecurityViewError> {
        // Validate session exists (in real implementation, check against persistent store)
        Uuid::parse_str(session_id)
            .map_err(|_| SecurityViewError::SessionNotFound)?;

        Ok(())
    }

    /// Process AoE event and publish to gateway
    pub async fn process_aoe_event(
        &self,
        event: &AoEEvent,
    ) -> Result<(), SecurityViewError> {
        // Map AoEEvent to A2UIComponent
        let component = SecurityDashboard::aoe_event_to_component(event);

        // Publish to streaming gateway
        self.gateway
            .publish(component)
            .map_err(|e| SecurityViewError::GatewayError(e.to_string()))?;

        Ok(())
    }

    /// Batch process multiple AoE events
    pub async fn process_aoe_events(
        &self,
        events: Vec<AoEEvent>,
    ) -> Result<usize, SecurityViewError> {
        let mut published_count = 0;

        for event in events {
            self.process_aoe_event(&event).await?;
            published_count += 1;
        }

        Ok(published_count)
    }

    /// Compose security view from events (for batch rendering)
    pub fn compose_security_view(
        &self,
        events: Vec<AoEEvent>,
    ) -> Result<Vec<siss_agent_shell::a2ui::A2UIComponent>, SecurityViewError> {
        let components = SecurityDashboard::compose_security_view(events);
        Ok(components)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_security_view_handler_starts_stream() {
        let gateway = Arc::new(A2UIStreamingGateway::new(100));
        let handler = SecurityViewHandler::new(gateway);

        let session_id = Uuid::new_v4().to_string();
        let result = handler.start_security_view(&session_id).await;

        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_security_view_handler_rejects_invalid_session() {
        let gateway = Arc::new(A2UIStreamingGateway::new(100));
        let handler = SecurityViewHandler::new(gateway);

        let result = handler.start_security_view("not-a-uuid").await;

        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), SecurityViewError::SessionNotFound);
    }

    #[tokio::test]
    async fn test_security_view_processes_aoe_event() {
        let gateway = Arc::new(A2UIStreamingGateway::new(100));
        let handler = SecurityViewHandler::new(gateway);

        let event = AoEEvent {
            action_type: "ANOMALY_DETECTED".to_string(),
            id: Uuid::new_v4().to_string(),
            content: Some("Test anomaly".to_string()),
            metadata: None,
        };

        let result = handler.process_aoe_event(&event).await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_security_view_composes_events() {
        let gateway = Arc::new(A2UIStreamingGateway::new(100));
        let handler = SecurityViewHandler::new(gateway);

        let events = vec![
            AoEEvent {
                action_type: "ANOMALY_DETECTED".to_string(),
                id: Uuid::new_v4().to_string(),
                content: Some("Anomaly".to_string()),
                metadata: None,
            },
            AoEEvent {
                action_type: "ACTION_COMPLETED".to_string(),
                id: Uuid::new_v4().to_string(),
                content: Some("Action".to_string()),
                metadata: None,
            },
        ];

        let result = handler.compose_security_view(events);
        assert!(result.is_ok());

        let view = result.unwrap();
        assert!(!view.is_empty());
    }
}
