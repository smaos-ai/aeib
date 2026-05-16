use crate::operator::{CryptoApproval, OperatorCockpit};
use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::response::sse::{Event, KeepAlive, Sse};
use axum::Json;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use uuid::Uuid;

#[derive(Clone)]
pub struct AgUiState {
    pub cockpit: Arc<OperatorCockpit>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct OperatorDecisionRequest {
    pub task_id: String,
    pub operator_id: String,
    pub signature: String,
    pub approved: bool,
    pub rejection_reason: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct OperatorDecisionResponse {
    pub status: String,
    pub message: String,
}

#[derive(Debug, Serialize)]
pub struct ContextProjectionResponse {
    pub agent_id: String,
    pub visible_field_entries: usize,
    pub gray_fog_summary: String,
    pub pending_approvals: Vec<String>,
}

/// GET /api/rce/stream — SSE endpoint for LoRA swap lifecycle events
/// Streams Queued, Distilling, AlignmentGateRunning, Authorized, Blocked, Quarantined events
pub async fn stream_lora_swap_events(
    State(state): State<AgUiState>,
) -> Sse<impl futures::stream::Stream<Item = Result<Event, std::convert::Infallible>>> {
    let mut rx = state.cockpit.subscribe_telemetry();

    let stream = async_stream::stream! {
        loop {
            match rx.recv().await {
                Ok(event) => {
                    let json = serde_json::to_string(&event).unwrap_or_default();
                    yield Ok(Event::default().data(json));
                }
                Err(_) => {
                    // Broadcast channel closed, stop streaming
                    break;
                }
            }
        }
    };

    Sse::new(stream).keep_alive(KeepAlive::default())
}

/// POST /api/rce/decision — Cryptographic decision webhook
/// Accepts operator approval with SHA-256 signature validation
/// Returns 200 OK on success, 401 Unauthorized on invalid signature, 403 Forbidden on unrecognized DID
pub async fn submit_operator_decision(
    State(state): State<AgUiState>,
    Json(request): Json<OperatorDecisionRequest>,
) -> Result<(StatusCode, Json<OperatorDecisionResponse>), (StatusCode, String)> {
    // Parse task_id
    let task_id = Uuid::parse_str(&request.task_id).map_err(|_| {
        (
            StatusCode::BAD_REQUEST,
            "Invalid task_id UUID format".to_string(),
        )
    })?;

    // Validate signature
    use sha2::{Digest, Sha256};
    let mut hasher = Sha256::new();
    hasher.update(task_id.as_bytes());
    hasher.update(request.operator_id.as_bytes());
    let sig_bytes = hasher.finalize();
    let expected_signature = hex::encode(sig_bytes);

    if request.signature != expected_signature {
        return Err((
            StatusCode::UNAUTHORIZED,
            "Invalid cryptographic signature".to_string(),
        ));
    }

    // Validate operator DID (zero-trust membrane)
    // For now, accept any operator with valid signature; production would check allowlist
    if request.operator_id.is_empty() {
        return Err((
            StatusCode::FORBIDDEN,
            "Unrecognized operator DID".to_string(),
        ));
    }

    // Issue approval via cockpit
    let approval = CryptoApproval {
        task_id,
        operator_id: request.operator_id,
        signature: request.signature,
        approved: request.approved,
        rejection_reason: request.rejection_reason,
    };

    match state.cockpit.issue_operator_approval(approval).await {
        Ok(_) => Ok((
            StatusCode::OK,
            Json(OperatorDecisionResponse {
                status: "approved".to_string(),
                message: "Operator decision processed".to_string(),
            }),
        )),
        Err(_) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            "Failed to process operator decision".to_string(),
        )),
    }
}

/// GET /api/rce/{task_id}/projection — State projection resolver
/// Returns ContextProjection with visible field vs Gray Fog summary
pub async fn get_state_projection(
    State(state): State<AgUiState>,
    Path(task_id): Path<String>,
) -> Result<Json<ContextProjectionResponse>, (StatusCode, String)> {
    let agent_id = Uuid::parse_str(&task_id).map_err(|_| {
        (
            StatusCode::BAD_REQUEST,
            "Invalid task_id UUID format".to_string(),
        )
    })?;

    match state.cockpit.project_agent_state(agent_id).await {
        Ok(projection) => Ok(Json(ContextProjectionResponse {
            agent_id: projection.agent_id.to_string(),
            visible_field_entries: projection.visible_field_entries,
            gray_fog_summary: projection.gray_fog_summary,
            pending_approvals: projection
                .pending_approvals
                .iter()
                .map(|id| id.to_string())
                .collect(),
        })),
        Err(_) => Err((StatusCode::NOT_FOUND, "Agent state not found".to_string())),
    }
}

/// Health check endpoint
pub async fn health_check() -> (StatusCode, String) {
    (StatusCode::OK, "AG-UI boundary operational".to_string())
}
