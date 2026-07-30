/// Phase 38: π⁺ Projection Resolver — Read-Only RCE Cognitive State Surface
///
/// GET /api/rce/{workflow_id}/projection
///
/// Enables the Operator to see the RCE engine's cognitive state under a read lock
/// (never write lock), serializing the Tripartite Zonal Model and hydrating the
/// pending Step payload so informed decisions are possible without state mutation.
///
/// Critical invariant: Calling this endpoint zero or a thousand times leaves the
/// engine in identical state. Any write lock acquisition is a test failure.
use axum::{
    Json,
    extract::{Path, State},
    http::StatusCode,
};
use serde::Serialize;
use siss_context_cartography::inbound::project_to_task_context;
use siss_context_cartography::zones::ZonalContextMap;
use uuid::Uuid;

use crate::state::CockpitState;

// ============================================================================
// Response Types
// ============================================================================

/// Projection response — the Operator's window into RCE cognitive state
#[derive(Debug, Serialize)]
pub struct ProjectionResponse {
    pub workflow_id: String,
    pub state: String, // "Idle" | "Perform" | "Paused" | "Resumed"
    pub step_index: usize,
    pub total_steps: usize,
    pub pending_step: Option<PendingStepPayload>, // plan[step_index] when state == Paused
    pub checkpoint: Option<CheckpointMeta>,       // when paused
    pub context_map: Option<serde_json::Value>,   // ZonalContextMap → project_to_task_context()
    pub updated_at: String,                       // RFC3339
}

/// Pending step metadata — hydrated from plan[current_step_index]
#[derive(Debug, Serialize)]
pub struct PendingStepPayload {
    pub id: String,
    pub name: String,
    pub timeout_ms: u64,
    pub idempotent: bool,
}

/// Checkpoint metadata at pause point
#[derive(Debug, Serialize)]
pub struct CheckpointMeta {
    pub step_index: usize,
    pub reason: String,    // Captured interrupt reason
    pub version: usize,    // OCC version
    pub timestamp: String, // RFC3339
}

// ============================================================================
// Handler: GET /api/rce/{workflow_id}/projection
// ============================================================================

pub async fn get_rce_projection(
    State(state): State<CockpitState>,
    Path(workflow_id_str): Path<String>,
) -> Result<(StatusCode, Json<ProjectionResponse>), (StatusCode, String)> {
    // [1] Parse {workflow_id} as UUID
    let requested_workflow_id = Uuid::parse_str(&workflow_id_str).map_err(|_| {
        (
            StatusCode::BAD_REQUEST,
            "Invalid workflow_id UUID".to_string(),
        )
    })?;

    // [2] Acquire READ lock (NEVER write lock — π⁺ isomorphism invariant)
    let engine_guard = state.rce_engine.read().await;

    // [3] engine.as_ref().ok_or(404)
    let engine = engine_guard
        .as_ref()
        .ok_or_else(|| (StatusCode::NOT_FOUND, "RCE engine not wired".to_string()))?;

    // [4] Verify engine.workflow_id == path_workflow_id
    if engine.workflow_id != requested_workflow_id {
        return Err((StatusCode::NOT_FOUND, "Workflow not found".to_string()));
    }

    // [5] Extract pending_step: engine.plan.get(engine.current_step_index)
    let pending_step = engine
        .plan
        .get(engine.current_step_index)
        .map(|step| PendingStepPayload {
            id: step.id.to_string(),
            name: step.name.clone(),
            timeout_ms: step.timeout_ms,
            idempotent: step.idempotent,
        });

    // [6] Extract checkpoint: engine.checkpoint.as_ref()
    let checkpoint = engine.checkpoint.as_ref().map(|cp| CheckpointMeta {
        step_index: cp.step_index,
        reason: cp.reason.clone(),
        version: cp.version,
        timestamp: cp.timestamp.to_rfc3339(),
    });

    // [7] Deserialize context_map: ZonalContextMap → project_to_task_context()
    let context_map = engine
        .checkpoint
        .as_ref()
        .and_then(|cp| serde_json::from_slice::<ZonalContextMap>(&cp.state_snapshot).ok())
        .map(|map| project_to_task_context(&map));

    // Extract all values needed before releasing the lock
    let workflow_id = engine.workflow_id.to_string();
    let state_str = format!("{:?}", engine.state);
    let step_index = engine.current_step_index;
    let total_steps = engine.plan.len();
    let updated_at = engine.updated_at.to_rfc3339();

    // [8] Release read lock (drop engine_guard implicitly)
    drop(engine_guard);

    // [9] Return 200 ProjectionResponse
    let response = ProjectionResponse {
        workflow_id,
        state: state_str,
        step_index,
        total_steps,
        pending_step,
        checkpoint,
        context_map,
        updated_at,
    };

    Ok((StatusCode::OK, Json(response)))
}

// ============================================================================
// Error Response Type
// ============================================================================

#[derive(Debug, Serialize)]
pub struct ProjectionError {
    pub status: u16,
    pub error: String,
}
