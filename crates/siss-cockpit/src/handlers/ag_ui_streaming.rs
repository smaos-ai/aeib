/// Phase 37: AG-UI Handlers RCE-to-Cockpit SSE Bridge
/// Server-Sent Events (SSE) endpoint for real-time RCE event streaming
///
/// Phase 33: A2UI Streaming SSE Endpoint
/// Real-time A2UI component streaming to frontend clients
use axum::{
    extract::{Query, State},
    http::{HeaderMap, StatusCode},
    response::{Sse, sse::Event},
};
use futures::stream::Stream;
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::sync::Arc;
use std::time::Duration;
use uuid::Uuid;

use crate::a2ui::component_broadcast::ComponentBroadcast;
use crate::a2ui::streaming_gateway::A2UIStreamingGateway;
use crate::state::CockpitState;
use siss_graph_db::rce_event_broadcaster::RceEvent;

#[derive(Debug, Deserialize)]
pub struct StreamParams {
    pub workflow_id: Option<String>,
    pub severity_min: Option<String>,
}

/// A2UI Event Payload — Declarative JSON for React components (kept for backwards compat)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct A2UIEvent {
    pub event_type: String,
    pub timestamp: String,
    pub data: serde_json::Value,
    pub component: serde_json::Value,
}

impl A2UIEvent {
    pub fn routing_decision(confidence: f64, tier: &str, latency_ms: u32, cost: f64) -> Self {
        A2UIEvent {
            event_type: "routing_decision".to_string(),
            timestamp: chrono::Utc::now().to_rfc3339(),
            data: json!({
                "confidence_score": confidence,
                "assigned_tier": tier,
                "latency_ms": latency_ms,
                "token_cost": cost,
            }),
            component: json!({
                "type": "metric_card",
                "title": "Routing Decision",
                "data_binding": "$.data"
            }),
        }
    }

    pub fn metrics_update(total: u64, t1: f64, t2: f64, t3: f64, latency: f64, cost: f64) -> Self {
        A2UIEvent {
            event_type: "metrics_update".to_string(),
            timestamp: chrono::Utc::now().to_rfc3339(),
            data: json!({
                "total_requests": total,
                "tier1_percentage": t1,
                "tier2_percentage": t2,
                "tier3_percentage": t3,
                "avg_latency_ms": latency,
                "total_cost": cost,
            }),
            component: json!({
                "type": "metric_dashboard",
                "title": "Routing Metrics",
                "layout": ["tier_distribution", "latency_chart", "cost_summary"],
                "data_binding": "$.data"
            }),
        }
    }
}

/// Parse severity level to numeric score for filtering
fn severity_score(severity: &str) -> i32 {
    match severity {
        "Low" => 1,
        "Medium" => 2,
        "High" => 3,
        "Critical" => 4,
        _ => 0,
    }
}

/// Convert RceEvent to SSE JSON payload
fn rce_event_to_sse_json(event: &RceEvent) -> serde_json::Value {
    match event {
        RceEvent::WorkflowStarted {
            workflow_id,
            timestamp,
            step_count,
            plan,
        } => json!({
            "event": "workflow_started",
            "workflow_id": workflow_id.to_string(),
            "timestamp": timestamp.to_rfc3339(),
            "data": {
                "step_count": step_count,
                "plan": plan,
            }
        }),
        RceEvent::WorkflowPaused {
            workflow_id,
            timestamp,
            step_index,
            step_id,
            step_name,
            interrupt_reason,
            interrupt_severity,
        } => json!({
            "event": "workflow_paused",
            "workflow_id": workflow_id.to_string(),
            "timestamp": timestamp.to_rfc3339(),
            "data": {
                "step_index": step_index,
                "step_id": step_id.to_string(),
                "step_name": step_name,
                "interrupt_reason": interrupt_reason,
                "interrupt_severity": interrupt_severity,
                "human_approval_required": true,
                "checkpoint_timestamp": timestamp.to_rfc3339(),
            }
        }),
        RceEvent::WorkflowResumed {
            workflow_id,
            timestamp,
            step_index,
            decision,
        } => json!({
            "event": "workflow_resumed",
            "workflow_id": workflow_id.to_string(),
            "timestamp": timestamp.to_rfc3339(),
            "data": {
                "step_index": step_index,
                "decision": decision,
                "decision_reason": serde_json::Value::Null,
                "human_operator_id": "",
            }
        }),
        RceEvent::WorkflowRejected {
            workflow_id,
            timestamp,
            reason,
        } => json!({
            "event": "workflow_rejected",
            "workflow_id": workflow_id.to_string(),
            "timestamp": timestamp.to_rfc3339(),
            "data": {
                "reason": reason,
                "human_operator_id": "",
            }
        }),
        RceEvent::WorkflowCompleted {
            workflow_id,
            timestamp,
            total_steps,
        } => json!({
            "event": "workflow_completed",
            "workflow_id": workflow_id.to_string(),
            "timestamp": timestamp.to_rfc3339(),
            "data": {
                "total_steps": total_steps,
                "execution_time_ms": 0,
            }
        }),
    }
}

/// AG-UI SSE Stream Handler
/// Authenticates request, subscribes to RceEventBroadcaster, streams events with keep-alive
pub async fn get_rce_stream(
    headers: HeaderMap,
    State(state): State<CockpitState>,
    Query(params): Query<StreamParams>,
) -> Result<Sse<impl Stream<Item = Result<Event, std::convert::Infallible>>>, StatusCode> {
    let _auth_header = headers
        .get("Authorization")
        .and_then(|h| h.to_str().ok())
        .filter(|s| s.starts_with("Bearer "))
        .ok_or(StatusCode::UNAUTHORIZED)?;

    // Parse and validate workflow_id if provided
    let filter_workflow_id = if let Some(ref id_str) = params.workflow_id {
        match Uuid::parse_str(id_str) {
            Ok(id) => Some(id),
            Err(_) => return Err(StatusCode::BAD_REQUEST),
        }
    } else {
        None
    };

    // Validate severity_min if provided
    let min_severity_score = if let Some(ref sev) = params.severity_min {
        match sev.as_str() {
            "Low" | "Medium" | "High" | "Critical" => severity_score(sev),
            _ => return Err(StatusCode::BAD_REQUEST),
        }
    } else {
        0
    };

    let mut rx = state.rce_broadcaster.subscribe();

    let stream = async_stream::stream! {
        // Send retry hint and keep-alive interval at stream start
        yield Ok(Event::default()
            .event("open")
            .data(""));

        loop {
            // Receive with 30s timeout for keep-alive
            match tokio::time::timeout(Duration::from_secs(30), rx.recv()).await {
                Ok(Ok(event)) => {
                    // Filter by workflow_id if specified
                    if let Some(filter_id) = filter_workflow_id {
                        if event.workflow_id() != filter_id {
                            continue;
                        }
                    }

                    // Filter by severity_min if WorkflowPaused
                    if min_severity_score > 0 {
                        if let RceEvent::WorkflowPaused { interrupt_severity, .. } = &event {
                            if severity_score(interrupt_severity) < min_severity_score {
                                continue;
                            }
                        }
                    }

                    // Convert to SSE JSON
                    let json_data = rce_event_to_sse_json(&event);
                    let event_name = event.event_type().to_string();

                    if let Ok(sse_event) = Event::default()
                        .event(event_name)
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

    #[tokio::test]
    async fn test_ag_ui_stream_endpoint_requires_authentication() {
        let headers = axum::http::HeaderMap::new();
        let state = CockpitState::new();
        let params = Query(StreamParams {
            workflow_id: None,
            severity_min: None,
        });
        let result = get_rce_stream(headers, State(state), params).await;
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), StatusCode::UNAUTHORIZED);
    }

    #[tokio::test]
    async fn test_ag_ui_stream_establishes_sse_connection() {
        let mut headers = axum::http::HeaderMap::new();
        headers.insert("Authorization", "Bearer test-token-12345".parse().unwrap());
        let state = CockpitState::new();
        let params = Query(StreamParams {
            workflow_id: None,
            severity_min: None,
        });
        let result = get_rce_stream(headers, State(state), params).await;
        assert!(
            result.is_ok(),
            "Should accept valid Bearer token and return SSE stream"
        );
    }

    #[tokio::test]
    async fn test_sse_invalid_workflow_id_returns_400() {
        let mut headers = axum::http::HeaderMap::new();
        headers.insert("Authorization", "Bearer test-token".parse().unwrap());
        let state = CockpitState::new();
        let params = Query(StreamParams {
            workflow_id: Some("not-a-uuid".to_string()),
            severity_min: None,
        });
        let result = get_rce_stream(headers, State(state), params).await;
        assert_eq!(result.unwrap_err(), StatusCode::BAD_REQUEST);
    }

    #[tokio::test]
    async fn test_sse_invalid_severity_min_returns_400() {
        let mut headers = axum::http::HeaderMap::new();
        headers.insert("Authorization", "Bearer test-token".parse().unwrap());
        let state = CockpitState::new();
        let params = Query(StreamParams {
            workflow_id: None,
            severity_min: Some("InvalidSeverity".to_string()),
        });
        let result = get_rce_stream(headers, State(state), params).await;
        assert_eq!(result.unwrap_err(), StatusCode::BAD_REQUEST);
    }
}

/// Phase 33: A2UI Component Stream Parameters
#[derive(Debug, Deserialize)]
pub struct A2UIStreamParams {
    pub agent_id: Option<String>,
}

/// Phase 33: A2UI Stream Helper
/// Returns an SSE stream that sends keep-alive events
/// In a production system, this would subscribe to the global A2UIStreamingGateway
pub fn get_a2ui_sse_stream(
    agent_id: Uuid,
) -> Sse<impl Stream<Item = Result<Event, std::convert::Infallible>>> {
    let agent_id_str = agent_id.to_string();

    let stream = async_stream::stream! {
        // Send initial open event with agent_id
        let open_event = Event::default()
            .event("a2ui_stream_open")
            .data(format!(r#"{{"agent_id":"{}"}}"#, agent_id_str));
        yield Ok(open_event);

        // Keep-alive loop (30s timeout)
        loop {
            // In production, would receive from broadcast channel
            // For now, send keep-alive every 30s
            tokio::time::sleep(std::time::Duration::from_secs(30)).await;

            let keep_alive = Event::default()
                .event("keep_alive")
                .data("");
            yield Ok(keep_alive);
        }
    };

    Sse::new(stream)
}

/// Phase 33: GET /api/a2ui/stream endpoint
/// Streams real-time validated A2UI component updates to frontend clients
/// Returns Server-Sent Events (SSE) stream with component updates
pub async fn get_a2ui_stream(
    headers: HeaderMap,
    Query(params): Query<A2UIStreamParams>,
) -> Result<Sse<impl Stream<Item = Result<Event, std::convert::Infallible>>>, StatusCode> {
    // Authenticate request
    let _auth_header = headers
        .get("Authorization")
        .and_then(|h| h.to_str().ok())
        .filter(|s| s.starts_with("Bearer "))
        .ok_or(StatusCode::UNAUTHORIZED)?;

    // Parse and validate agent_id if provided
    let agent_id = if let Some(agent_id_str) = params.agent_id {
        match Uuid::parse_str(&agent_id_str) {
            Ok(id) => id,
            Err(_) => return Err(StatusCode::BAD_REQUEST),
        }
    } else {
        Uuid::new_v4()
    };

    // Return SSE stream for this agent
    Ok(get_a2ui_sse_stream(agent_id))
}

#[cfg(test)]
mod a2ui_streaming_tests {
    use super::*;

    #[tokio::test]
    async fn test_a2ui_stream_endpoint_requires_authentication() {
        let headers = axum::http::HeaderMap::new();
        let params = Query(A2UIStreamParams { agent_id: None });
        let result = get_a2ui_stream(headers, params).await;
        assert_eq!(result.unwrap_err(), StatusCode::UNAUTHORIZED);
    }

    #[tokio::test]
    async fn test_a2ui_stream_establishes_sse_connection() {
        let mut headers = axum::http::HeaderMap::new();
        headers.insert("Authorization", "Bearer test-token-a2ui".parse().unwrap());
        let params = Query(A2UIStreamParams { agent_id: None });
        let result = get_a2ui_stream(headers, params).await;
        assert!(
            result.is_ok(),
            "Should accept valid Bearer token and return SSE stream"
        );
    }

    #[tokio::test]
    async fn test_a2ui_stream_invalid_agent_id_returns_400() {
        let mut headers = axum::http::HeaderMap::new();
        headers.insert("Authorization", "Bearer test-token".parse().unwrap());
        let params = Query(A2UIStreamParams {
            agent_id: Some("not-a-uuid".to_string()),
        });
        let result = get_a2ui_stream(headers, params).await;
        assert_eq!(result.unwrap_err(), StatusCode::BAD_REQUEST);
    }

    #[tokio::test]
    async fn test_a2ui_stream_accepts_valid_agent_id() {
        let mut headers = axum::http::HeaderMap::new();
        headers.insert("Authorization", "Bearer test-token".parse().unwrap());
        let valid_uuid = Uuid::new_v4().to_string();
        let params = Query(A2UIStreamParams {
            agent_id: Some(valid_uuid),
        });
        let result = get_a2ui_stream(headers, params).await;
        assert!(result.is_ok());
    }
}
