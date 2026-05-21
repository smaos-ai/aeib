use axum::{
    Json,
    extract::{Query, State},
    http::StatusCode,
};
use serde::{Deserialize, Serialize};
use sqlx::PgPool;
use uuid::Uuid;

use super::errors::{ApiError, ApiResult};
use crate::repo::projections_repo::{
    AgentActionPageResponse, AnomalyPageResponse, RecoveryPageResponse, fetch_agent_actions,
    fetch_anomalies, fetch_recovery,
};

/// Agent actions query parameters
#[derive(Debug, Deserialize)]
pub struct AgentActionsQuery {
    pub sovereign_id: String,
    #[serde(default = "default_limit")]
    pub limit: Option<i32>,
}

fn default_limit() -> Option<i32> {
    Some(50)
}

/// Anomalies query parameters
#[derive(Debug, Deserialize)]
pub struct AnomaliesQuery {
    pub sovereign_id: String,
    pub severity: Option<String>,
    pub anomaly_type: Option<String>,
    #[serde(default = "default_limit")]
    pub limit: Option<i32>,
}

/// Recovery query parameters
#[derive(Debug, Deserialize)]
pub struct RecoveryQuery {
    pub sovereign_id: String,
    #[serde(default = "default_limit")]
    pub limit: Option<i32>,
}

/// Correlations query parameters
#[derive(Debug, Deserialize)]
pub struct CorrelationsQuery {
    pub sovereign_id: String,
    pub min_sample_size: Option<i32>,
    #[serde(default = "default_limit")]
    pub limit: Option<i32>,
}

/// Handler for GET /api/graph/projections/agent_actions
pub async fn get_agent_actions(
    State(_pool): State<PgPool>,
    Query(params): Query<AgentActionsQuery>,
) -> ApiResult<(StatusCode, Json<AgentActionPageResponse>)> {
    // Validate UUID
    let sovereign_id: Uuid = Uuid::parse_str(&params.sovereign_id)
        .map_err(|_| ApiError::InvalidParameter("sovereign_id must be a valid UUID".to_string()))?;

    // Clamp limit
    let limit = params.limit.unwrap_or(50).max(1).min(500);

    let response = fetch_agent_actions(&sovereign_id, None, limit).await?;

    Ok((StatusCode::OK, Json(response)))
}

/// Handler for GET /api/graph/projections/anomalies
pub async fn get_anomalies(
    State(_pool): State<PgPool>,
    Query(params): Query<AnomaliesQuery>,
) -> ApiResult<(StatusCode, Json<AnomalyPageResponse>)> {
    // Validate UUID
    let sovereign_id: Uuid = Uuid::parse_str(&params.sovereign_id)
        .map_err(|_| ApiError::InvalidParameter("sovereign_id must be a valid UUID".to_string()))?;

    // Validate severity if provided
    if let Some(ref sev) = params.severity {
        if !["low", "medium", "high", "critical"].contains(&sev.as_str()) {
            return Err(ApiError::InvalidParameter(
                "severity must be one of: low, medium, high, critical".to_string(),
            ));
        }
    }

    // Clamp limit
    let limit = params.limit.unwrap_or(50).max(1).min(200);

    let response = fetch_anomalies(
        &sovereign_id,
        params.severity.as_deref(),
        params.anomaly_type.as_deref(),
        limit,
    )
    .await?;

    Ok((StatusCode::OK, Json(response)))
}

/// Handler for GET /api/graph/projections/recovery
pub async fn get_recovery(
    State(_pool): State<PgPool>,
    Query(params): Query<RecoveryQuery>,
) -> ApiResult<(StatusCode, Json<RecoveryPageResponse>)> {
    // Validate UUID
    let sovereign_id: Uuid = Uuid::parse_str(&params.sovereign_id)
        .map_err(|_| ApiError::InvalidParameter("sovereign_id must be a valid UUID".to_string()))?;

    // Clamp limit
    let limit = params.limit.unwrap_or(25).max(1).min(100);

    let response = fetch_recovery(&sovereign_id, limit).await?;

    Ok((StatusCode::OK, Json(response)))
}

/// Correlations response
#[derive(Debug, Serialize)]
pub struct CorrelationsResponse {
    pub sovereign_id: String,
    pub correlation_count: i32,
    pub min_sample_size: i32,
    pub correlations: Vec<CorrelationPair>,
}

#[derive(Debug, Serialize)]
pub struct CorrelationPair {
    pub event_type_a: String,
    pub event_type_b: String,
    pub correlation_coefficient: f64,
    pub sample_count: i32,
}

/// Handler for GET /api/graph/correlations
pub async fn get_correlations(
    State(_pool): State<PgPool>,
    Query(params): Query<CorrelationsQuery>,
) -> ApiResult<(StatusCode, Json<CorrelationsResponse>)> {
    // Validate UUID
    let sovereign_id: Uuid = Uuid::parse_str(&params.sovereign_id)
        .map_err(|_| ApiError::InvalidParameter("sovereign_id must be a valid UUID".to_string()))?;

    // Validate min_sample_size
    let min_sample_size = params.min_sample_size.unwrap_or(10);
    if min_sample_size < 10 {
        return Err(ApiError::InvalidParameter(
            "min_sample_size must be at least 10".to_string(),
        ));
    }

    // Clamp limit
    let _limit = params.limit.unwrap_or(50).max(1).min(500);

    // TODO: Implement actual correlation computation
    // For now, return empty response
    let response = CorrelationsResponse {
        sovereign_id: sovereign_id.to_string(),
        correlation_count: 0,
        min_sample_size,
        correlations: vec![],
    };

    Ok((StatusCode::OK, Json(response)))
}
