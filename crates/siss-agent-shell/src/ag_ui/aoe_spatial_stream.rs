/// Phase 55: AoE Spatial Telemetry Stream — Pixel Provenance → SSE Events
/// Translates PixelProvenance broadcast messages into AoEEvent format for dashboard.
use crate::ag_ui::AoEEvent;
use crate::swarm_channel::{SwarmChannel, SwarmMessage};
use serde_json::json;
use tokio::sync::broadcast;

pub struct AoeSpatialStream {
    rx: broadcast::Receiver<SwarmMessage>,
}

impl AoeSpatialStream {
    pub fn new(channel: &SwarmChannel) -> Self {
        AoeSpatialStream {
            rx: channel.subscribe(),
        }
    }

    /// Drain the broadcast receiver until a PixelProvenance message arrives.
    /// RULE 1: Skip StatusUpdate, ArtifactReady, CommandDispatch — they are not spatial events
    /// RULE 2: On PixelProvenance → return AoEEvent {
    ///     action_type: "PIXEL_PROVENANCE",
    ///     id: provenance_id,
    ///     content: Some(action_type),
    ///     metadata: Some(json!({ "action_x": x, "action_y": y, "mandate_id": mandate_id, "token_cost": tc }))
    /// }
    /// RULE 3: Channel closed (all senders dropped) → None
    pub async fn next_event(&mut self) -> Option<AoEEvent> {
        loop {
            match self.rx.recv().await {
                Ok(SwarmMessage::PixelProvenance {
                    provenance_id,
                    action_type,
                    action_x,
                    action_y,
                    token_cost,
                    mandate_id,
                    ..
                }) => {
                    let metadata = json!({
                        "action_x": action_x,
                        "action_y": action_y,
                        "mandate_id": mandate_id.to_string(),
                        "token_cost": token_cost
                    });

                    return Some(AoEEvent {
                        action_type: "PIXEL_PROVENANCE".to_string(),
                        id: provenance_id.to_string(),
                        content: Some(action_type),
                        metadata: Some(metadata),
                    });
                }
                Ok(_) => continue,
                Err(_) => return None,
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;
    use uuid::Uuid;

    #[tokio::test]
    async fn test_aoe_spatial_stream_translates_to_aoe_event() {
        let channel = Arc::new(SwarmChannel::new());
        let mut stream = AoeSpatialStream::new(&channel);

        let provenance_id = Uuid::new_v4();
        let mandate_id = Uuid::new_v4();

        let msg = SwarmMessage::PixelProvenance {
            provenance_id,
            agent_id: "test_agent".to_string(),
            action_type: "GuiClick".to_string(),
            action_x: Some(100.0),
            action_y: Some(200.0),
            token_cost: 42,
            mandate_id,
        };

        channel.broadcast(msg).expect("broadcast failed");

        let event = stream.next_event().await;
        assert!(event.is_some());
        let ev = event.unwrap();
        assert_eq!(ev.action_type, "PIXEL_PROVENANCE");
        assert_eq!(ev.id, provenance_id.to_string());
        assert_eq!(ev.content, Some("GuiClick".to_string()));
    }

    #[tokio::test]
    async fn test_aoe_event_metadata_contains_all_fields() {
        let channel = Arc::new(SwarmChannel::new());
        let mut stream = AoeSpatialStream::new(&channel);

        let provenance_id = Uuid::new_v4();
        let mandate_id = Uuid::new_v4();

        let msg = SwarmMessage::PixelProvenance {
            provenance_id,
            agent_id: "test_agent".to_string(),
            action_type: "GuiType".to_string(),
            action_x: Some(50.0),
            action_y: Some(75.0),
            token_cost: 15,
            mandate_id,
        };

        channel.broadcast(msg).expect("broadcast failed");

        let event = stream.next_event().await;
        assert!(event.is_some());
        let ev = event.unwrap();
        let metadata = ev.metadata.expect("metadata missing");

        assert_eq!(metadata["action_x"], 50.0);
        assert_eq!(metadata["action_y"], 75.0);
        assert_eq!(metadata["token_cost"], 15);
        assert_eq!(metadata["mandate_id"], mandate_id.to_string());
    }
}
