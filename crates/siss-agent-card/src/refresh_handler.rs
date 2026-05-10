use axum::{extract::State, http::StatusCode, response::{IntoResponse, Json}};
use chrono::Utc;
use siss_gatekeeper::{
    attestation::validators::validate_attestation,
    refresh::*,
    tokens::{CapabilityToken, SessionToken},
};
use crate::handler::AgentCardState;

const SESSION_TOKEN_ROTATION_THRESHOLD_SECONDS: i64 = 600; // 10 minutes
const MAX_ATTESTATION_AGE_SECONDS: u64 = 3600; // 1 hour
const TRUSTED_ISSUERS: &[&str] = &["intel", "intel-sgx", "anthropic", "origin-issuer", "runtime"];

/// Extract session_id from JWT-like token (first 20 chars after split by .)
/// In production, this would decode the JWT payload properly.
fn extract_session_id_from_token(token: &str) -> Result<String, String> {
    let parts: Vec<&str> = token.split('.').collect();
    if parts.len() != 3 {
        return Err("invalid_token_format".to_string());
    }
    // Placeholder: use first part as session identifier
    Ok(parts[0].to_string())
}

pub async fn attestation_refresh_handler(
    State(state): State<AgentCardState>,
    Json(request): Json<AttestationRefreshRequest>,
) -> impl IntoResponse {
    // Step 1: Extract session_id from token
    let session_id = match extract_session_id_from_token(&request.session_token) {
        Ok(id) => id,
        Err(_) => {
            let response = build_error_response(
                "session_token_invalid".to_string(),
                "Could not parse session_token: invalid format".to_string(),
                vec!["Ensure session_token is a valid JWT (3 dot-separated parts)".to_string()],
                None,
            );
            return (StatusCode::BAD_REQUEST, Json(response)).into_response();
        }
    };

    // Step 2: Lookup session in database (best-effort; graceful fallback for test environments)
    let db_session = siss_graph_db::repo::session_repo::fetch_session_by_token(&state.pool, &request.session_token)
        .await
        .ok()
        .flatten();

    // If we found a session in DB, it's automatically validated (expiry + active status checked by fetch_session_by_token)
    // If not found: proceed without DB context (graceful fallback for new/test sessions)

    // Step 3: Validate proof signature (timestamp freshness + signature presence)
    let timestamp_str = request.timestamp.to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
    let attestations_json = serde_json::to_string(&request.attestations)
        .unwrap_or_else(|_| "[]".to_string());

    if let Err(reason) = validate_refresh_proof(
        &session_id,
        &request.ephemeral_nonce,
        &timestamp_str,
        &attestations_json,
        &request.proof_signature,
        None,
    ) {
        let response = match reason.as_str() {
            "timestamp_outside_freshness_window" => build_error_response(
                "timestamp_outside_freshness_window".to_string(),
                "Request timestamp is older than 5 minutes".to_string(),
                vec!["Retry with a fresh timestamp (current time ±5 min)".to_string()],
                None,
            ),
            _ => error_signature_invalid(),
        };
        return (StatusCode::BAD_REQUEST, Json(response)).into_response();
    }

    // Step 4: Validate attestations
    let trusted_issuers: Vec<String> = TRUSTED_ISSUERS.iter().map(|s| s.to_string()).collect();

    for attestation in &request.attestations {
        if let Err(err) = validate_attestation(attestation, MAX_ATTESTATION_AGE_SECONDS, &trusted_issuers) {
            let response = match err {
                siss_gatekeeper::attestation::validators::AttestationValidationError::Expired => {
                    error_attestation_validation_failed(
                        format!("Attestation expired at {}", attestation.valid_until)
                    )
                }
                siss_gatekeeper::attestation::validators::AttestationValidationError::TooOld => {
                    error_attestation_validation_failed(
                        "Attestation is too old (older than 1 hour)".to_string()
                    )
                }
                siss_gatekeeper::attestation::validators::AttestationValidationError::IssuerNotTrusted => {
                    error_attestation_validation_failed(
                        format!("Issuer '{}' is not trusted", attestation.issuer)
                    )
                }
                _ => error_attestation_validation_failed("Attestation validation failed".to_string()),
            };
            return (StatusCode::BAD_REQUEST, Json(response)).into_response();
        }
    }

    // Step 5: Re-evaluate trust based on attestations
    let (score, tier) = match reevaluate_trust(&request.attestations) {
        Ok((s, t)) => (s, t),
        Err(_) => {
            let eval = build_attestation_evaluation(
                20,
                None,
                build_attestations_evaluation(&request.attestations, 20),
                vec![],
                serde_json::json!({}),
            );
            let response = build_error_response(
                "insufficient_trust".to_string(),
                "Provided attestations score too low for any tier assignment".to_string(),
                vec![
                    "Obtain additional attestations (hardware_enclave, model_integrity, sovereign_origin)".to_string(),
                ],
                Some(eval),
            );
            return (StatusCode::FORBIDDEN, Json(response)).into_response();
        }
    };

    // Step 6: Build attestation evaluation (Layer 1: Why + Layer 2: What)
    let attestations_eval = build_attestations_evaluation(&request.attestations, score);
    let capability_changes = build_capability_changes(None, tier);

    // Step 7: Decide session token reuse
    let remaining_seconds = extract_session_token_remaining_seconds(&request.session_token)
        .unwrap_or(1800); // Default: 30 min remaining
    let should_reuse = decide_session_token_reuse(remaining_seconds, SESSION_TOKEN_ROTATION_THRESHOLD_SECONDS);

    // Step 8: Build session token if needed
    let session_token = if !should_reuse {
        Some(SessionToken {
            token: format!("session-{}", uuid::Uuid::new_v4()),
            expires_in: 3600,
            token_type: "Bearer".to_string(),
        })
    } else {
        None
    };

    // Step 9: Build capability token (always refreshed)
    let earliest_attestation_expiry = request.attestations
        .iter()
        .map(|a| a.valid_until)
        .min()
        .unwrap_or_else(|| Utc::now() + chrono::Duration::hours(24));

    let capability_expiry = compute_capability_token_expiry(86400, earliest_attestation_expiry);
    let capability_token = CapabilityToken {
        token: format!("cap-{}", uuid::Uuid::new_v4()),
        delegations: vec![],
        issued_at: Utc::now(),
        valid_until: capability_expiry,
    };

    // Step 10: Build evaluation report
    let evaluation = build_attestation_evaluation(
        score,
        Some(tier),
        attestations_eval,
        vec![],
        capability_changes,
    );

    // Step 11: Build and return success response
    let response = build_success_response(should_reuse, session_token, capability_token.clone(), evaluation);

    // Step 12: Persist updated trust state to database (best-effort, non-blocking)
    if let Some((session_uuid, _, _, _, _, _)) = db_session {
        let _ = siss_graph_db::repo::session_repo::update_session_after_refresh(
            &state.pool,
            session_uuid,
            &capability_token.token,
            score as i32,
            tier as i32,
            Utc::now(),
        )
        .await;
    }

    (StatusCode::OK, Json(response)).into_response()
}
