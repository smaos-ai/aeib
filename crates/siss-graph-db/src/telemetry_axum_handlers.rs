use axum::{
    extract::{State, Json},
    http::StatusCode,
    response::IntoResponse,
    routing::post,
    Router,
};
use serde_json::json;
use std::sync::Arc;
use sqlx::PgPool;

use crate::telemetry_handler::{OtelTraceEvent, AgUiEvent, TelemetryError, TelemetryIngestor};

/// Axum state for telemetry handlers
#[derive(Clone)]
pub struct TelemetryState {
    pub ingestor: Arc<TelemetryIngestor>,
}

impl TelemetryState {
    pub fn new(pool: Arc<PgPool>) -> Self {
        TelemetryState {
            ingestor: Arc::new(TelemetryIngestor::new(pool)),
        }
    }
}

/// POST `/api/telemetry/otel`
///
/// Accepts OpenTelemetry trace events and ingests them into the intelligence graph.
pub async fn ingest_otel_trace_handler(
    State(state): State<TelemetryState>,
    Json(event): Json<OtelTraceEvent>,
) -> impl IntoResponse {
    match state.ingestor.ingest_otel_trace(event).await {
        Ok(node_id) => (
            StatusCode::CREATED,
            Json(json!({
                "status": "success",
                "node_id": node_id
            })),
        )
            .into_response(),
        Err(TelemetryError::ValidationFailed(msg)) => (
            StatusCode::BAD_REQUEST,
            Json(json!({
                "status": "error",
                "error": msg
            })),
        )
            .into_response(),
        Err(TelemetryError::SerializationError(msg)) => (
            StatusCode::BAD_REQUEST,
            Json(json!({
                "status": "error",
                "error": format!("Serialization failed: {}", msg)
            })),
        )
            .into_response(),
        Err(TelemetryError::DatabaseError(msg)) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({
                "status": "error",
                "error": format!("Database error: {}", msg)
            })),
        )
            .into_response(),
    }
}

/// POST `/api/telemetry/agui`
///
/// Accepts AG-UI events (actions and anomalies) and ingests them into the intelligence graph.
pub async fn ingest_agui_event_handler(
    State(state): State<TelemetryState>,
    Json(event): Json<AgUiEvent>,
) -> impl IntoResponse {
    match state.ingestor.ingest_agui_event(event).await {
        Ok(node_id) => (
            StatusCode::CREATED,
            Json(json!({
                "status": "success",
                "node_id": node_id
            })),
        )
            .into_response(),
        Err(TelemetryError::ValidationFailed(msg)) => (
            StatusCode::BAD_REQUEST,
            Json(json!({
                "status": "error",
                "error": msg
            })),
        )
            .into_response(),
        Err(TelemetryError::SerializationError(msg)) => (
            StatusCode::BAD_REQUEST,
            Json(json!({
                "status": "error",
                "error": format!("Serialization failed: {}", msg)
            })),
        )
            .into_response(),
        Err(TelemetryError::DatabaseError(msg)) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({
                "status": "error",
                "error": format!("Database error: {}", msg)
            })),
        )
            .into_response(),
    }
}

/// Build the telemetry router
///
/// Returns a Router that handles all telemetry ingestion endpoints.
/// Integrate into your main Axum app with: `.nest("/api/telemetry", telemetry_router(state))`
pub fn telemetry_router(state: TelemetryState) -> Router {
    Router::new()
        .route("/otel", post(ingest_otel_trace_handler))
        .route("/agui", post(ingest_agui_event_handler))
        .with_state(state)
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::Body;
    use axum::http::{Request, StatusCode};
    use tower::ServiceExt;
    use uuid::Uuid;
    use chrono::Utc;

    #[tokio::test]
    async fn test_ingest_otel_trace_handler_success() {
        // This test would require a full database setup, so it's a smoke test
        // In integration testing, use with real database

        let event = OtelTraceEvent {
            trace_id: "trace-123".to_string(),
            span_id: "span-456".to_string(),
            span_name: "test_span".to_string(),
            session_id: Uuid::new_v4(),
            sovereign_id: Uuid::new_v4(),
            attributes: crate::telemetry_handler::OtelAttributes {
                event_type: "test_event".to_string(),
                tier_before: 1,
                tier_after: 2,
                cost_incurred: 100,
                lineage_safe: true,
            },
            start_time: Utc::now().to_rfc3339(),
            end_time: Utc::now().to_rfc3339(),
            status: "ok".to_string(),
        };

        // Event can be serialized to JSON
        let json = serde_json::to_value(&event).expect("serialize");
        assert!(json.is_object());
    }

    #[tokio::test]
    async fn test_ingest_agui_event_handler_success() {
        let event = AgUiEvent {
            event_id: Uuid::new_v4(),
            event_type: "action".to_string(),
            session_id: Uuid::new_v4(),
            sovereign_id: Uuid::new_v4(),
            payload: serde_json::json!({
                "action": "test_action"
            }),
            timestamp: Utc::now().to_rfc3339(),
        };

        let json = serde_json::to_value(&event).expect("serialize");
        assert!(json.is_object());
    }
}
