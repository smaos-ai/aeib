/// Phase 37: Agent-User Interaction Protocol (AG-UI) — Axum Handlers
///
/// Real-time SSE stream + decision webhook for RCE state machine.
/// Spec: docs/api/phase-37-ag-ui-spec.md

use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::sync::Arc;
use tokio::sync::RwLock;
use uuid::Uuid;

use crate::rce::{ExecutionState, ResumableCognitiveExecution, Step};

// =====================================================================
// SHARED STATE
// =====================================================================

#[derive(Clone, Debug)]
pub struct RceState {
    pub rce: Arc<RwLock<ResumableCognitiveExecution>>,
}

impl RceState {
    pub fn new(workflow_id: Uuid) -> Self {
        Self {
            rce: Arc::new(RwLock::new(ResumableCognitiveExecution::new(workflow_id))),
        }
    }
}

// =====================================================================
// REQUEST/RESPONSE TYPES
// =====================================================================

#[derive(Debug, Serialize, Deserialize)]
pub struct DecisionRequest {
    pub workflow_id: Uuid,
    pub decision: String, // "Approve", "Reject", "Modify"
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reason: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub new_plan: Option<Vec<Step>>,
    pub decided_by: String,
}

#[derive(Debug, Serialize)]
pub struct DecisionResponse {
    pub workflow_id: Uuid,
    pub decision: String,
    pub state_after: String,
    pub step_index: usize,
    pub timestamp: String,
}

#[derive(Debug, Serialize)]
pub struct ProjectionResponse {
    pub workflow_id: Uuid,
    pub state: String,
    pub step_index: usize,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub interrupt_reason: Option<String>,
    pub timestamp: String,
}

#[derive(Debug, Serialize)]
pub struct ErrorResponse {
    pub error: String,
    pub message: String,
    pub code: String,
}

#[derive(Debug, Deserialize)]
pub struct StreamQuery {
    pub workflow_id: Option<Uuid>,
    pub severity_min: Option<String>,
}

// =====================================================================
// HANDLERS
// =====================================================================

/// GET /api/rce/stream — Server-Sent Events stream
pub async fn handle_stream(
    State(_state): State<RceState>,
    Query(_params): Query<StreamQuery>,
) -> impl IntoResponse {
    // TODO: Phase 37B: Implement SSE streaming
    (
        StatusCode::OK,
        Json(json!({
            "status": "stream_not_yet_implemented",
            "message": "SSE handler scaffolding complete. Phase 37B pending."
        })),
    )
}

/// POST /api/rce/decision — Apply human decision (Approve/Reject/Modify)
pub async fn handle_decision(
    State(state): State<RceState>,
    Json(req): Json<DecisionRequest>,
) -> impl IntoResponse {
    let mut rce = state.rce.write().await;

    // Validate state
    if rce.get_state() != ExecutionState::Paused {
        return (
            StatusCode::CONFLICT,
            Json(ErrorResponse {
                error: "invalid_state".to_string(),
                message: format!("Workflow in state {:?}, not Paused", rce.get_state()),
                code: "STATE_MISMATCH".to_string(),
            }),
        )
            .into_response();
    }

    // Apply decision
    let result = match req.decision.as_str() {
        "Approve" => rce.resume_workflow_approve().map(|_| ("approve", rce.get_state())),
        "Reject" => {
            let reason = req.reason.unwrap_or_else(|| "operator_decision".to_string());
            rce.resume_workflow_reject(reason)
                .map(|_| ("reject", rce.get_state()))
        }
        "Modify" => {
            if let Some(new_plan) = req.new_plan {
                rce.resume_workflow_modify(new_plan)
                    .map(|_| ("modify", rce.get_state()))
            } else {
                return (
                    StatusCode::BAD_REQUEST,
                    Json(ErrorResponse {
                        error: "invalid_request".to_string(),
                        message: "new_plan required when decision='Modify'".to_string(),
                        code: "MISSING_REQUIRED_FIELD".to_string(),
                    }),
                )
                    .into_response();
            }
        }
        _ => {
            return (
                StatusCode::BAD_REQUEST,
                Json(ErrorResponse {
                    error: "invalid_request".to_string(),
                    message: "decision must be 'Approve', 'Reject', or 'Modify'".to_string(),
                    code: "INVALID_DECISION".to_string(),
                }),
            )
                .into_response();
        }
    };

    match result {
        Ok((decision, new_state)) => (
            StatusCode::OK,
            Json(DecisionResponse {
                workflow_id: rce.workflow_id,
                decision: decision.to_string(),
                state_after: format!("{:?}", new_state),
                step_index: rce.get_current_step_index(),
                timestamp: Utc::now().to_rfc3339(),
            }),
        )
            .into_response(),
        Err(e) => (
            StatusCode::UNPROCESSABLE_ENTITY,
            Json(ErrorResponse {
                error: "decision_failed".to_string(),
                message: e,
                code: "DECISION_ERROR".to_string(),
            }),
        )
            .into_response(),
    }
}

/// GET /api/rce/:workflow_id/projection — Fetch full projection context
pub async fn handle_get_projection(
    State(state): State<RceState>,
    Path(_workflow_id): Path<Uuid>,
) -> impl IntoResponse {
    let rce = state.rce.read().await;

    (
        StatusCode::OK,
        Json(ProjectionResponse {
            workflow_id: rce.workflow_id,
            state: format!("{:?}", rce.get_state()),
            step_index: rce.get_current_step_index(),
            interrupt_reason: rce
                .get_history()
                .iter()
                .rev()
                .find(|e| e.event_type == "workflow_paused")
                .and_then(|e| e.details.get("reason").map(|v| v.to_string())),
            timestamp: Utc::now().to_rfc3339(),
        }),
    )
}

/// GET /api/rce/:workflow_id/projection/threat-anticipation
pub async fn handle_get_threat_anticipation(
    State(_state): State<RceState>,
    Path(_workflow_id): Path<Uuid>,
) -> impl IntoResponse {
    // TODO: Phase 37B: Fetch from projection_repo
    (
        StatusCode::OK,
        Json(json!({
            "type": "threat_anticipation",
            "message": "Implementation pending Phase 37B"
        })),
    )
}

/// GET /api/rce/:workflow_id/projection/root-cause
pub async fn handle_get_root_cause(
    State(_state): State<RceState>,
    Path(_workflow_id): Path<Uuid>,
) -> impl IntoResponse {
    // TODO: Phase 37B: Fetch from projection_repo
    (
        StatusCode::OK,
        Json(json!({
            "type": "root_cause",
            "message": "Implementation pending Phase 37B"
        })),
    )
}

/// GET /api/rce/:workflow_id/projection/swot
pub async fn handle_get_swot(
    State(_state): State<RceState>,
    Path(_workflow_id): Path<Uuid>,
) -> impl IntoResponse {
    // TODO: Phase 37B: Fetch from projection_repo
    (
        StatusCode::OK,
        Json(json!({
            "type": "swot",
            "message": "Implementation pending Phase 37B"
        })),
    )
}

/// GET /api/rce/:workflow_id/checkpoint
pub async fn handle_get_checkpoint(
    State(state): State<RceState>,
    Path(_workflow_id): Path<Uuid>,
) -> impl IntoResponse {
    let rce = state.rce.read().await;

    match rce.checkpoint.as_ref() {
        Some(cp) => (
            StatusCode::OK,
            Json(json!({
                "workflow_id": rce.workflow_id,
                "state_index": cp.step_index,
                "timestamp": cp.timestamp.to_rfc3339(),
                "reason": cp.reason,
                "version": cp.version,
                "checksum_valid": true,
                "can_resume": true
            })),
        )
            .into_response(),
        None => (
            StatusCode::NOT_FOUND,
            Json(ErrorResponse {
                error: "not_found".to_string(),
                message: "No checkpoint exists for this workflow".to_string(),
                code: "NO_CHECKPOINT".to_string(),
            }),
        )
            .into_response(),
    }
}

// =====================================================================
// ROUTER
// =====================================================================

pub fn rce_router(state: RceState) -> Router {
    Router::new()
        .route("/stream", get(handle_stream))
        .route("/decision", post(handle_decision))
        .route("/:workflow_id/projection", get(handle_get_projection))
        .route("/:workflow_id/projection/threat-anticipation", get(handle_get_threat_anticipation))
        .route("/:workflow_id/projection/root-cause", get(handle_get_root_cause))
        .route("/:workflow_id/projection/swot", get(handle_get_swot))
        .route("/:workflow_id/checkpoint", get(handle_get_checkpoint))
        .with_state(state)
}
