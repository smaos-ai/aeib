/// Phase 26 Task 1: Axum Router Endpoint
/// POST /api/router/route — Accept task_description, return tier routing decision + SSE metrics

use axum::{
    http::StatusCode,
    Json,
};
use serde::{Deserialize, Serialize};
use std::time::Instant;
use siss_job_router::confidence_scorer::SimpleScorer;
use siss_job_router::routing_engine::RoutingEngine;
use siss_job_router::cost_budget::CostMatrix;

#[derive(Debug, Serialize, Deserialize)]
pub struct RouteRequest {
    pub task_description: String,
    pub budget_tokens: Option<u32>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct RouteResponse {
    pub confidence_score: f64,
    pub assigned_tier: String,
    pub fallback_chain: Vec<String>,
    pub latency_ms: u32,
    pub token_cost: f64,
    pub reason: String,
}

pub async fn post_route(
    Json(payload): Json<RouteRequest>,
) -> Result<Json<RouteResponse>, StatusCode> {
    let start = Instant::now();

    // Validate input
    if payload.task_description.trim().is_empty() {
        return Err(StatusCode::BAD_REQUEST);
    }

    // Compute confidence score
    let score = SimpleScorer::score_task(&payload.task_description);

    // Get routing decision
    let decision = RoutingEngine::decide(&score, payload.budget_tokens)
        .map_err(|_| StatusCode::BAD_REQUEST)?;

    // Calculate token cost
    let matrix = CostMatrix::default();
    let base_cost = matrix.estimate_cost(score.recommended_tier, score.estimated_tokens);
    // Assume 20% cache hit rate for baseline
    let token_cost = base_cost * 0.8; // 20% cache discount

    let latency_ms = start.elapsed().as_millis() as u32;

    Ok(Json(RouteResponse {
        confidence_score: score.score,
        assigned_tier: format!("{:?}", decision.primary_tier),
        fallback_chain: decision
            .fallback_chain
            .iter()
            .map(|t| format!("{:?}", t))
            .collect(),
        latency_ms,
        token_cost,
        reason: decision.reason,
    }))
}

#[cfg(test)]
mod tests {
    use super::*;

    // =====================================================================
    // TEST SUITE 9: Router Endpoint Tests (Tests 9.1 - 9.5)
    // =====================================================================

    #[tokio::test]
    async fn test_router_endpoint_polling_task_routes_to_tier1() {
        let payload = RouteRequest {
            task_description: "polling status check".to_string(),
            budget_tokens: None,
        };

        let result = post_route(Json(payload)).await;
        assert!(result.is_ok());
        let Json(body) = result.unwrap();
        assert_eq!(body.assigned_tier, "Tier1RapidMLX");
        assert_eq!(body.confidence_score, 0.1);
        assert!(!body.fallback_chain.is_empty());
    }

    #[tokio::test]
    async fn test_router_endpoint_complex_task_routes_to_tier3() {
        let payload = RouteRequest {
            task_description: "complex decision making required".to_string(),
            budget_tokens: None,
        };

        let result = post_route(Json(payload)).await;
        assert!(result.is_ok());
        let Json(body) = result.unwrap();
        assert_eq!(body.assigned_tier, "Tier3Opus");
        assert!(body.confidence_score >= 0.8);
        assert!(body.fallback_chain.is_empty()); // Tier3 has no fallback
    }

    #[tokio::test]
    async fn test_router_endpoint_response_includes_required_fields() {
        let payload = RouteRequest {
            task_description: "filter anomalies by severity".to_string(),
            budget_tokens: Some(1000),
        };

        let result = post_route(Json(payload)).await;
        assert!(result.is_ok());
        let Json(body) = result.unwrap();
        assert!(body.confidence_score >= 0.0 && body.confidence_score <= 1.0);
        assert!(
            body.assigned_tier == "Tier1RapidMLX"
                || body.assigned_tier == "Tier2Sonnet"
                || body.assigned_tier == "Tier3Opus"
        );
        assert!(body.token_cost >= 0.0);
        assert!(!body.reason.is_empty());
    }

    #[tokio::test]
    async fn test_router_endpoint_missing_task_description_returns_400() {
        let payload = RouteRequest {
            task_description: "".to_string(),
            budget_tokens: None,
        };

        let result = post_route(Json(payload)).await;
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), StatusCode::BAD_REQUEST);
    }

    #[tokio::test]
    async fn test_router_endpoint_budget_constraint_enforced() {
        let payload = RouteRequest {
            task_description: "complex decision making".to_string(),
            budget_tokens: Some(50), // Budget: 50 tokens
        };

        // Tier3Opus tasks estimate ~800+ tokens, so budget should fail
        let result = post_route(Json(payload)).await;
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), StatusCode::BAD_REQUEST);
    }
}
