use axum::{extract::State, http::StatusCode, response::{IntoResponse, Json}};
use siss_gatekeeper::refresh::*;
use crate::handler::AgentCardState;

pub async fn attestation_refresh_handler(
    State(_state): State<AgentCardState>,
    Json(_request): Json<AttestationRefreshRequest>,
) -> impl IntoResponse {
    // Minimal MVP: return success response
    let response = AttestationRefreshResponse::Success(AttestationRefreshResponseSuccess {
        status: "refreshed".to_string(),
        session_token_reused: true,
        session_token: None,
        capability_token: siss_gatekeeper::tokens::CapabilityToken {
            token: format!("cap-{}", uuid::Uuid::new_v4()),
            delegations: vec![],
            issued_at: chrono::Utc::now(),
            valid_until: chrono::Utc::now() + chrono::Duration::hours(24),
        },
        attestation_evaluation: build_attestation_evaluation(
            80,
            Some(2),
            serde_json::json!({}),
            vec![],
            serde_json::json!({}),
        ),
    });
    (StatusCode::OK, Json(response)).into_response()
}
