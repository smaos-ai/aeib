use axum::{
    extract::{Query, State},
    http::StatusCode,
    Json,
};
use serde::Deserialize;
use uuid::Uuid;
use crate::state::CockpitState;

#[derive(Debug, Deserialize)]
pub struct ProjectionQueryParams {
    sovereign_id: String,
    #[serde(default)]
    severity: Option<String>,
    #[serde(default)]
    anomaly_type: Option<String>,
    #[serde(default)]
    limit: Option<i32>,
}

/// GET /api/graph/projections/agent-actions
/// Query params: sovereign_id (required), limit (optional, default 100)
pub async fn get_agent_actions(
    State(state): State<CockpitState>,
    Query(params): Query<ProjectionQueryParams>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    // Parse sovereign_id as UUID
    let sovereign_id = Uuid::parse_str(&params.sovereign_id)
        .map_err(|_| StatusCode::BAD_REQUEST)?;

    let limit = params.limit.unwrap_or(100).min(500);

    // Extract pool from state
    let pool = state.pool.lock()
        .ok()
        .and_then(|p| p.clone())
        .ok_or(StatusCode::INTERNAL_SERVER_ERROR)?;

    // Call projections_repo
    let response = siss_graph_db::repo::projections_repo::fetch_agent_actions(
        &pool,
        &sovereign_id,
        None,
        limit,
    )
    .await
    .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(serde_json::to_value(response)
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?))
}

/// GET /api/graph/projections/anomalies
/// Query params: sovereign_id (required), severity (optional), anomaly_type (optional), limit (optional)
pub async fn get_anomalies(
    State(state): State<CockpitState>,
    Query(params): Query<ProjectionQueryParams>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    // Parse sovereign_id as UUID
    let sovereign_id = Uuid::parse_str(&params.sovereign_id)
        .map_err(|_| StatusCode::BAD_REQUEST)?;

    let limit = params.limit.unwrap_or(100).min(500);

    // Extract pool from state
    let pool = state.pool.lock()
        .ok()
        .and_then(|p| p.clone())
        .ok_or(StatusCode::INTERNAL_SERVER_ERROR)?;

    // Call projections_repo
    let response = siss_graph_db::repo::projections_repo::fetch_anomalies(
        &pool,
        &sovereign_id,
        params.severity.as_deref(),
        params.anomaly_type.as_deref(),
        limit,
    )
    .await
    .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(serde_json::to_value(response)
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?))
}

/// GET /api/graph/projections/recovery
/// Query params: sovereign_id (required), limit (optional)
pub async fn get_recovery(
    State(state): State<CockpitState>,
    Query(params): Query<ProjectionQueryParams>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    // Parse sovereign_id as UUID
    let sovereign_id = Uuid::parse_str(&params.sovereign_id)
        .map_err(|_| StatusCode::BAD_REQUEST)?;

    let limit = params.limit.unwrap_or(100).min(200);

    // Extract pool from state
    let pool = state.pool.lock()
        .ok()
        .and_then(|p| p.clone())
        .ok_or(StatusCode::INTERNAL_SERVER_ERROR)?;

    // Call projections_repo
    let response = siss_graph_db::repo::projections_repo::fetch_recovery(
        &pool,
        &sovereign_id,
        limit,
    )
    .await
    .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(serde_json::to_value(response)
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?))
}
