use axum::{
    extract::Query,
    http::StatusCode,
    Json,
};
use serde::Deserialize;
use uuid::Uuid;

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
    Query(params): Query<ProjectionQueryParams>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    // Parse sovereign_id as UUID
    let sovereign_id = Uuid::parse_str(&params.sovereign_id)
        .map_err(|_| StatusCode::BAD_REQUEST)?;

    let limit = params.limit.unwrap_or(100).min(500);

    // Call projections_repo
    let response = siss_graph_db::repo::projections_repo::fetch_agent_actions(
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
    Query(params): Query<ProjectionQueryParams>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    // Parse sovereign_id as UUID
    let sovereign_id = Uuid::parse_str(&params.sovereign_id)
        .map_err(|_| StatusCode::BAD_REQUEST)?;

    let limit = params.limit.unwrap_or(100).min(500);

    // Call projections_repo
    let response = siss_graph_db::repo::projections_repo::fetch_anomalies(
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
    Query(params): Query<ProjectionQueryParams>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    // Parse sovereign_id as UUID
    let sovereign_id = Uuid::parse_str(&params.sovereign_id)
        .map_err(|_| StatusCode::BAD_REQUEST)?;

    let limit = params.limit.unwrap_or(100).min(200);

    // Call projections_repo
    let response = siss_graph_db::repo::projections_repo::fetch_recovery(
        &sovereign_id,
        limit,
    )
    .await
    .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(serde_json::to_value(response)
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?))
}
