use axum::response::sse::{Event, Sse};
use futures::stream::Stream;
use std::convert::Infallible;
use std::sync::Arc;

// Re-export from siss-graph-db
pub use siss_graph_db::recovery_event_broadcaster::{RecoveryEvent, RecoveryEventBroadcaster};

pub type EventBroadcaster = RecoveryEventBroadcaster;

/// Axum SSE handler: GET /events
/// Streams recovery events as Server-Sent Events (text/event-stream)
pub async fn events_stream(
    broadcaster: axum::extract::State<Arc<RecoveryEventBroadcaster>>,
) -> Sse<impl Stream<Item = Result<Event, std::convert::Infallible>>> {
    let mut rx = broadcaster.subscribe();

    let stream = async_stream::stream! {
        loop {
            match rx.recv().await {
                Ok(event) => {
                    match serde_json::to_string(&event) {
                        Ok(json_str) => {
                            yield Ok(Event::default().data(json_str));
                        }
                        Err(_) => {
                            yield Ok(Event::default().data("error: serialization failed"));
                        }
                    }
                }
                Err(tokio::sync::broadcast::error::RecvError::Lagged(_)) => {
                    // Client fell behind; skip and continue
                    continue;
                }
                Err(tokio::sync::broadcast::error::RecvError::Closed) => {
                    // Broadcaster was dropped
                    break;
                }
            }
        }
    };

    Sse::new(stream)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_event_broadcaster_creation() {
        let broadcaster = RecoveryEventBroadcaster::new();
        let _rx = broadcaster.subscribe();
    }

    #[test]
    fn test_recovery_event_serialization() {
        let event = RecoveryEvent::RecoveryEntered {
            sovereign_id: "test-id".to_string(),
            score_at_entry: 82,
            timestamp: "2026-05-11T12:34:56Z".to_string(),
        };
        let json = serde_json::to_string(&event).unwrap();
        assert!(json.contains("RecoveryEntered"));
        assert!(json.contains("test-id"));
    }
}
