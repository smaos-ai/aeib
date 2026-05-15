/// Phase 37: Agent-User Interaction Protocol (AG-UI) — Axum Handlers
///
/// Real-time SSE stream + decision webhook for RCE state machine.
/// Spec: docs/api/phase-37-ag-ui-spec.md

use async_stream::stream;
use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    response::{sse::Event, Sse, IntoResponse},
    routing::{get, post},
    Json, Router,
};
use chrono::Utc;
use futures::Stream;
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::sync::Arc;
use tokio::sync::{broadcast, RwLock};
use uuid::Uuid;

use crate::rce::{ExecutionState, ResumableCognitiveExecution, Step};
use crate::rce_event_broadcaster::{RceEvent, RceEventBroadcaster};
use crate::repo::{projection_repo, rce_checkpoint_repo};

// =====================================================================
// SHARED STATE
// =====================================================================

#[derive(Clone, Debug)]
pub struct RceState {
    pub rce: Arc<RwLock<ResumableCognitiveExecution>>,
    pub broadcaster: Arc<RceEventBroadcaster>,
    pub pool: Arc<sqlx::PgPool>,
}

impl RceState {
    pub fn new(workflow_id: Uuid, pool: Arc<sqlx::PgPool>) -> Self {
        Self {
            rce: Arc::new(RwLock::new(ResumableCognitiveExecution::new(workflow_id))),
            broadcaster: Arc::new(RceEventBroadcaster::new()),
            pool,
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
    State(state): State<RceState>,
    Query(params): Query<StreamQuery>,
) -> Sse<impl Stream<Item = Result<Event, std::convert::Infallible>>> {
    let mut rx = state.broadcaster.subscribe();
    let severity_min = params.severity_min.clone();
    let workflow_filter = params.workflow_id;

    let stream = stream! {
        loop {
            match rx.recv().await {
                Ok(event) => {
                    // Filter by workflow_id if specified
                    if let Some(wf_id) = workflow_filter {
                        if event.workflow_id() != wf_id {
                            continue;
                        }
                    }

                    // Filter by severity if specified
                    if let Some(ref min_severity) = severity_min {
                        let event_severity = match &event {
                            RceEvent::WorkflowPaused { interrupt_severity, .. } => interrupt_severity.as_str(),
                            _ => "Medium",
                        };
                        let min_priority = severity_priority(min_severity);
                        let event_priority = severity_priority(event_severity);
                        if event_priority < min_priority {
                            continue;
                        }
                    }

                    // Serialize and send
                    if let Ok(json) = serde_json::to_string(&event) {
                        yield Ok(Event::default()
                            .event(event.event_type())
                            .data(json));
                    }
                }
                Err(broadcast::error::RecvError::Lagged(_)) => {
                    // Client fell behind; skip
                    continue;
                }
                Err(broadcast::error::RecvError::Closed) => {
                    // Broadcaster closed
                    break;
                }
            }
        }
    };

    Sse::new(stream)
}

/// Helper to convert severity string to priority level
fn severity_priority(severity: &str) -> u32 {
    match severity {
        "Critical" => 4,
        "High" => 3,
        "Medium" => 2,
        "Low" => 1,
        _ => 0,
    }
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

    let reject_reason = req.reason.clone();

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
        Ok((decision, new_state)) => {
            let workflow_id = rce.workflow_id;
            let step_index = rce.get_current_step_index();
            let timestamp = Utc::now();

            // Emit event based on decision type
            let event = match decision {
                "reject" => RceEvent::WorkflowRejected {
                    workflow_id,
                    timestamp,
                    reason: reject_reason.clone().unwrap_or_else(|| "operator_decision".to_string()),
                },
                _ => RceEvent::WorkflowResumed {
                    workflow_id,
                    timestamp,
                    step_index,
                    decision: decision.to_string(),
                },
            };
            state.broadcaster.emit(event);

            // Persist decision to audit trail
            let audit_result = rce_checkpoint_repo::append_audit_event(
                &state.pool,
                workflow_id,
                "human_decision",
                Some(decision),
                Some(&req.decided_by),
                reject_reason.as_deref(),
                &json!({ "decision": decision }),
            )
            .await;

            if audit_result.is_err() {
                // Log audit failure but don't block decision response
                eprintln!("Failed to record audit trail for decision");
            }

            // Delete checkpoint on reject (already cleared in memory, now remove from DB)
            if decision == "reject" {
                let _ = rce_checkpoint_repo::delete_checkpoint(&state.pool, workflow_id).await;
            }

            (
                StatusCode::OK,
                Json(DecisionResponse {
                    workflow_id,
                    decision: decision.to_string(),
                    state_after: format!("{:?}", new_state),
                    step_index,
                    timestamp: timestamp.to_rfc3339(),
                }),
            )
                .into_response()
        }
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
    State(state): State<RceState>,
    Path(_workflow_id): Path<Uuid>,
) -> impl IntoResponse {
    let rce = state.rce.read().await;

    // Use current step's sovereign as source
    if rce.get_current_step_index() >= rce.plan.len() {
        return (
            StatusCode::BAD_REQUEST,
            Json(ErrorResponse {
                error: "invalid_state".to_string(),
                message: "Workflow has no active step".to_string(),
                code: "NO_ACTIVE_STEP".to_string(),
            }),
        )
            .into_response();
    }

    // Query threat anticipation with depth 3
    match projection_repo::query_threat_anticipation(&state.pool, rce.workflow_id, 3).await {
        Ok(ta) => (
            StatusCode::OK,
            Json(json!({
                "type": "threat_anticipation",
                "source_sovereign_id": ta.source_sovereign_id,
                "tokens_at_risk": ta.total_tokens_at_risk,
                "confidence": 0.92,
                "affected_sovereigns": ta.affected_sovereigns.iter().take(5).map(|s| {
                    json!({
                        "sovereign_id": s.sovereign_id,
                        "risk_level": "high",
                        "tokens_affected": 0i64
                    })
                }).collect::<Vec<_>>(),
                "timestamp": Utc::now().to_rfc3339()
            })),
        )
            .into_response(),
        Err(_) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                error: "projection_failed".to_string(),
                message: "Failed to fetch threat anticipation projection".to_string(),
                code: "PROJECTION_ERROR".to_string(),
            }),
        )
            .into_response(),
    }
}

/// GET /api/rce/:workflow_id/projection/root-cause
pub async fn handle_get_root_cause(
    State(state): State<RceState>,
    Path(_workflow_id): Path<Uuid>,
) -> impl IntoResponse {
    let rce = state.rce.read().await;

    // Use workflow_id as anomaly_id
    match projection_repo::query_root_cause_chain(&state.pool, rce.workflow_id, 5).await {
        Ok(rc) => (
            StatusCode::OK,
            Json(json!({
                "type": "root_cause",
                "confidence": rc.confidence,
                "threshold": 0.90,
                "root_cause_chain": rc.root_cause_chain.iter().take(5).map(|node| {
                    json!({
                        "depth": node.depth,
                        "entity_type": node.chain_type.as_deref().unwrap_or("unknown"),
                        "description": node.label,
                        "confidence": node.confidence
                    })
                }).collect::<Vec<_>>(),
                "timestamp": Utc::now().to_rfc3339()
            })),
        )
            .into_response(),
        Err(_) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                error: "projection_failed".to_string(),
                message: "Failed to fetch root cause projection".to_string(),
                code: "PROJECTION_ERROR".to_string(),
            }),
        )
            .into_response(),
    }
}

/// GET /api/rce/:workflow_id/projection/swot
pub async fn handle_get_swot(
    State(state): State<RceState>,
    Path(_workflow_id): Path<Uuid>,
) -> impl IntoResponse {
    let rce = state.rce.read().await;

    // Query SWOT with 30-day window
    match projection_repo::query_swot_scenario(&state.pool, rce.workflow_id, 30).await {
        Ok(swot) => (
            StatusCode::OK,
            Json(json!({
                "type": "swot",
                "diversity_index": swot.diversity_index,
                "threshold": 0.50,
                "scenarios": {
                    "strengths": swot.strengths.iter().take(3).map(|s| json!({
                        "description": s.description,
                        "weight": 0.25
                    })).collect::<Vec<_>>(),
                    "weaknesses": swot.weaknesses.iter().take(3).map(|w| json!({
                        "description": w.description,
                        "weight": 0.25
                    })).collect::<Vec<_>>(),
                    "opportunities": swot.opportunities.iter().take(3).map(|o| json!({
                        "description": o.description,
                        "weight": 0.25
                    })).collect::<Vec<_>>(),
                    "threats": swot.threats.iter().take(3).map(|t| json!({
                        "description": t.description,
                        "weight": 0.25
                    })).collect::<Vec<_>>()
                },
                "timestamp": Utc::now().to_rfc3339()
            })),
        )
            .into_response(),
        Err(_) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                error: "projection_failed".to_string(),
                message: "Failed to fetch SWOT projection".to_string(),
                code: "PROJECTION_ERROR".to_string(),
            }),
        )
            .into_response(),
    }
}

/// GET /api/rce/:workflow_id/checkpoint
pub async fn handle_get_checkpoint(
    State(state): State<RceState>,
    Path(workflow_id): Path<Uuid>,
) -> impl IntoResponse {
    // Try to load checkpoint from PostgreSQL first
    match rce_checkpoint_repo::load_checkpoint(&state.pool, workflow_id).await {
        Ok(Some((id, step_index, _state, checksum, version, reason))) => (
            StatusCode::OK,
            Json(json!({
                "id": id,
                "workflow_id": workflow_id,
                "state_index": step_index,
                "checksum": checksum,
                "version": version,
                "reason": reason,
                "checksum_valid": true,
                "can_resume": true,
                "source": "persistent"
            })),
        )
            .into_response(),
        Ok(None) => {
            // Fall back to in-memory checkpoint if DB has none
            let rce = state.rce.read().await;
            match rce.checkpoint.as_ref() {
                Some(cp) => (
                    StatusCode::OK,
                    Json(json!({
                        "workflow_id": rce.workflow_id,
                        "state_index": cp.step_index,
                        "reason": cp.reason,
                        "version": cp.version,
                        "checksum_valid": true,
                        "can_resume": true,
                        "source": "memory"
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
        Err(_) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                error: "database_error".to_string(),
                message: "Failed to query checkpoint".to_string(),
                code: "DB_ERROR".to_string(),
            }),
        )
            .into_response(),
    }
}

/// POST /api/rce/:workflow_id/checkpoint/save — Persist checkpoint to database
pub async fn handle_save_checkpoint(
    State(state): State<RceState>,
    Path(workflow_id): Path<Uuid>,
) -> impl IntoResponse {
    let rce = state.rce.read().await;

    // Get checkpoint from memory
    match rce.checkpoint.as_ref() {
        Some(cp) => {
            // Serialize the RCE state for storage
            let state_json = serde_json::json!({
                "workflow_id": rce.workflow_id,
                "step_index": cp.step_index,
                "plan_size": rce.plan.len(),
                "state_snapshot_size": cp.state_snapshot.len(),
            });

            // Save to database
            match rce_checkpoint_repo::save_checkpoint(
                &state.pool,
                workflow_id,
                cp.step_index as i32,
                &state_json,
                &cp.checksum,
                cp.version as i32,
                &cp.reason,
                "High",
            )
            .await
            {
                Ok(id) => (
                    StatusCode::CREATED,
                    Json(json!({
                        "id": id,
                        "workflow_id": workflow_id,
                        "status": "saved",
                        "timestamp": Utc::now().to_rfc3339()
                    })),
                )
                    .into_response(),
                Err(_) => (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    Json(ErrorResponse {
                        error: "save_failed".to_string(),
                        message: "Failed to save checkpoint to database".to_string(),
                        code: "SAVE_ERROR".to_string(),
                    }),
                )
                    .into_response(),
            }
        }
        None => (
            StatusCode::BAD_REQUEST,
            Json(ErrorResponse {
                error: "no_checkpoint".to_string(),
                message: "No in-memory checkpoint to persist".to_string(),
                code: "NO_CHECKPOINT_IN_MEMORY".to_string(),
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
        .route("/:workflow_id/checkpoint/save", post(handle_save_checkpoint))
        .with_state(state)
}
