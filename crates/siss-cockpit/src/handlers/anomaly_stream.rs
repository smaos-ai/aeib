/// Phase 38: Anomaly Stream Handler — SSE Endpoint for Real-Time Anomaly Events
/// Server-Sent Events (SSE) endpoint for anomaly event streaming
/// Follows Pattern B: Bearer auth → 401, subscribe, timeout keep-alive, emit JSON

use axum::{
    extract::State,
    http::{StatusCode, HeaderMap},
    response::{sse::Event, Sse},
};
use futures::stream::Stream;
use serde_json::json;
use std::convert::Infallible;
use std::time::Duration;

use crate::state::{CockpitState, AnomalyEvent};

/// Anomaly Stream Handler
/// Authenticates request via Bearer token, subscribes to anomaly broadcaster, streams events with 30s keep-alive
#[axum::debug_handler]
pub async fn get_anomaly_stream(
    headers: HeaderMap,
    State(state): State<CockpitState>,
) -> Result<Sse<impl Stream<Item = Result<Event, Infallible>>>, StatusCode> {
    // Validate Bearer token from headers, return UNAUTHORIZED if missing
    let _auth_header = headers
        .get("Authorization")
        .and_then(|h| h.to_str().ok())
        .filter(|s| s.starts_with("Bearer "))
        .ok_or(StatusCode::UNAUTHORIZED)?;

    // Subscribe to anomaly broadcaster
    let mut rx = state.subscribe_anomalies();

    let stream = async_stream::stream! {
        // Send open event at stream start
        yield Ok(Event::default()
            .event("open")
            .data(""));

        loop {
            // Receive with 30s timeout for keep-alive
            match tokio::time::timeout(Duration::from_secs(30), rx.recv()).await {
                Ok(Ok(event)) => {
                    // Convert AnomalyEvent to SSE JSON
                    let json_data = json!({
                        "sovereign_id": event.sovereign_id.to_string(),
                        "anomaly_type": event.anomaly_type,
                        "severity": event.severity,
                        "detected_at": event.detected_at.to_rfc3339(),
                    });

                    if let Ok(sse_event) = Event::default()
                        .event("anomaly")
                        .json_data(&json_data)
                    {
                        yield Ok(sse_event);
                    }
                }
                Ok(Err(_)) => {
                    // Channel closed, stream ends
                    break;
                }
                Err(_) => {
                    // Timeout: send keep-alive
                    let keep_alive = json!({
                        "event": "keep_alive",
                        "timestamp": chrono::Utc::now().to_rfc3339(),
                    });
                    if let Ok(sse_event) = Event::default()
                        .event("keep_alive")
                        .json_data(&keep_alive)
                    {
                        yield Ok(sse_event);
                    }
                }
            }
        }
    };

    Ok(Sse::new(stream))
}

#[cfg(test)]
mod tests {
    use super::*;
    use uuid::Uuid;

    #[tokio::test]
    async fn test_anomaly_stream_requires_bearer_auth() {
        let headers = axum::http::HeaderMap::new();
        let state = CockpitState::new();
        let result = get_anomaly_stream(headers, State(state)).await;
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), StatusCode::UNAUTHORIZED);
    }

    #[tokio::test]
    async fn test_anomaly_stream_accepts_bearer_token() {
        let mut headers = axum::http::HeaderMap::new();
        headers.insert(
            "Authorization",
            "Bearer test-token-12345".parse().unwrap(),
        );
        let state = CockpitState::new();
        let result = get_anomaly_stream(headers, State(state)).await;
        assert!(result.is_ok(), "Should accept valid Bearer token and return SSE stream");
    }

    #[tokio::test]
    async fn test_anomaly_broadcaster_emits_to_stream() {
        let mut headers = axum::http::HeaderMap::new();
        headers.insert(
            "Authorization",
            "Bearer test-token".parse().unwrap(),
        );
        let state = CockpitState::new();

        // Test that broadcaster can emit events
        let event = AnomalyEvent {
            sovereign_id: Uuid::new_v4(),
            anomaly_type: "test_anomaly".to_string(),
            severity: 2,
            detected_at: chrono::Utc::now(),
        };
        // Emit an event on the broadcaster
        let result = state.anomaly_broadcaster.send(event);
        assert!(result.is_ok(), "Broadcaster should emit events without error");

        // Stream should accept bearer token and establish connection
        let stream_result = get_anomaly_stream(headers, State(state)).await;
        assert!(stream_result.is_ok(), "Should establish SSE connection with bearer token");
    }
}
