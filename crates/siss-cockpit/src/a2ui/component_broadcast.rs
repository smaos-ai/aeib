/// Phase 33: Component Broadcast for SSE Streaming
/// Converts validated component events to SSE (Server-Sent Events) format

use std::sync::Arc;
use axum::response::sse::{Event, Sse};
use futures::stream::Stream;
use uuid::Uuid;

use super::streaming_gateway::A2UIStreamingGateway;

/// Component broadcast for a specific agent/client
pub struct ComponentBroadcast {
    gateway: Arc<A2UIStreamingGateway>,
    agent_id: Uuid,
}

impl ComponentBroadcast {
    /// Create a new broadcast for an agent
    pub fn new(gateway: Arc<A2UIStreamingGateway>, agent_id: Uuid) -> Self {
        Self { gateway, agent_id }
    }

    /// Stream components to client as SSE events
    pub fn stream_to_client(
        &self,
    ) -> Sse<impl Stream<Item = Result<Event, std::convert::Infallible>>> {
        let gateway = self.gateway.clone();
        let agent_id = self.agent_id;

        let stream = async_stream::stream! {
            let mut rx = gateway.subscribe();

            // Send initial open event
            let open_event = Event::default()
                .event("component_stream_open")
                .data(format!(r#"{{"agent_id":"{}"}}"#, agent_id));
            yield Ok(open_event);

            // Stream events from broadcast channel
            loop {
                match tokio::time::timeout(
                    std::time::Duration::from_secs(30),
                    rx.recv(),
                ).await {
                    Ok(Ok(event)) => {
                        // Serialize event to JSON and send as SSE
                        let component_id = match &event.component {
                            siss_agent_shell::a2ui::A2UIComponent::Text { id, .. } => id.clone(),
                            siss_agent_shell::a2ui::A2UIComponent::Button { id, .. } => id.clone(),
                            siss_agent_shell::a2ui::A2UIComponent::Input { id, .. } => id.clone(),
                            siss_agent_shell::a2ui::A2UIComponent::Badge { id, .. } => id.clone(),
                            siss_agent_shell::a2ui::A2UIComponent::Alert { id, .. } => id.clone(),
                            siss_agent_shell::a2ui::A2UIComponent::Progress { id, .. } => id.clone(),
                            siss_agent_shell::a2ui::A2UIComponent::Divider { id } => id.clone(),
                            siss_agent_shell::a2ui::A2UIComponent::Link { id, .. } => id.clone(),
                            siss_agent_shell::a2ui::A2UIComponent::Tooltip { id, .. } => id.clone(),
                            siss_agent_shell::a2ui::A2UIComponent::Breadcrumb { id, .. } => id.clone(),
                            siss_agent_shell::a2ui::A2UIComponent::Textarea { id, .. } => id.clone(),
                            siss_agent_shell::a2ui::A2UIComponent::Select { id, .. } => id.clone(),
                            siss_agent_shell::a2ui::A2UIComponent::Checkbox { id, .. } => id.clone(),
                            siss_agent_shell::a2ui::A2UIComponent::Radio { id, .. } => id.clone(),
                            siss_agent_shell::a2ui::A2UIComponent::Card { id, .. } => id.clone(),
                            siss_agent_shell::a2ui::A2UIComponent::Grid { id, .. } => id.clone(),
                            siss_agent_shell::a2ui::A2UIComponent::Modal { id, .. } => id.clone(),
                            siss_agent_shell::a2ui::A2UIComponent::Table { id, .. } => id.clone(),
                        };

                        let json_data = serde_json::json!({
                            "component_id": component_id,
                            "jsx": event.jsx,
                            "schema_valid": event.schema_valid,
                            "accessibility": {
                                "passed": event.accessibility.passed,
                                "violations": event.accessibility.violations,
                            },
                            "timestamp": event.timestamp.to_rfc3339(),
                        });

                        let sse_event = Event::default()
                            .event("component_update")
                            .json_data(&json_data)
                            .unwrap_or_else(|_| Event::default());

                        yield Ok(sse_event);
                    }
                    Ok(Err(_)) => {
                        // Broadcast channel closed
                        break;
                    }
                    Err(_) => {
                        // Keep-alive timeout
                        let keep_alive = Event::default()
                            .event("keep_alive")
                            .data("");

                        yield Ok(keep_alive);
                    }
                }
            }
        };

        Sse::new(stream)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_broadcast_creation() {
        let gateway = Arc::new(A2UIStreamingGateway::new(100));
        let agent_id = Uuid::new_v4();
        let broadcast = ComponentBroadcast::new(gateway, agent_id);
        assert_eq!(broadcast.agent_id, agent_id);
    }

    #[test]
    fn test_broadcast_stream_returns_sse() {
        let gateway = Arc::new(A2UIStreamingGateway::new(100));
        let agent_id = Uuid::new_v4();
        let broadcast = ComponentBroadcast::new(gateway, agent_id);

        // Stream should be created successfully
        let _stream = broadcast.stream_to_client();
    }
}
