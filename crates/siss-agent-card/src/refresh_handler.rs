use axum::{extract::State, http::StatusCode, response::{IntoResponse, Json}};
use chrono::Utc;
use siss_gatekeeper::{
    attestation::validators::validate_attestation,
    refresh::*,
    tokens::{CapabilityToken, SessionToken},
};
use crate::handler::AgentCardState;
use rand::RngCore;

const SESSION_TOKEN_ROTATION_THRESHOLD_SECONDS: i64 = 600; // 10 minutes
const MAX_ATTESTATION_AGE_SECONDS: u64 = 3600; // 1 hour
const TRUSTED_ISSUERS: &[&str] = &["intel", "intel-sgx", "anthropic", "origin-issuer", "runtime"];
const CHALLENGE_EXPIRY_MINUTES: i64 = 5; // Challenge nonce validity window

/// Generate a random nonce as 64-byte hex string (256-bit)
fn generate_nonce() -> String {
    let mut bytes = [0u8; 32];
    rand::thread_rng().fill_bytes(&mut bytes);
    hex::encode(bytes)
}

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

    // Step 2: Check session status (revocation detection) and lookup in database
    let db_session = match siss_graph_db::repo::session_repo::fetch_session_status_by_token(&state.pool, &request.session_token)
        .await
        .ok()
        .flatten()
    {
        Some((_, status)) if status == "revoked" => {
            // Session has been revoked by SISS
            let response = error_session_revoked();
            return (StatusCode::UNAUTHORIZED, Json(response)).into_response();
        }
        Some((_, status)) if status == "active" => {
            // Session is active; fetch full details for validation
            siss_graph_db::repo::session_repo::fetch_session_by_token(&state.pool, &request.session_token)
                .await
                .ok()
                .flatten()
        }
        _ => {
            // Session not found or in other state; proceed with graceful fallback
            None
        }
    };

    // If we found a session in DB, it's automatically validated (expiry + active status checked by fetch_session_by_token)
    // If not found: proceed without DB context (graceful fallback for new/test sessions)

    // Step 2b: Check for pull-trigger condition (empty attestations → issue challenge)
    if request.attestations.is_empty() && request.challenge_nonce.is_none() {
        let nonce = generate_nonce();
        let required_attestations = vec!["hardware".to_string(), "model".to_string()];
        let expiry = Utc::now() + chrono::Duration::minutes(CHALLENGE_EXPIRY_MINUTES);

        // Best-effort: store challenge in DB (non-blocking on failure)
        if let Some((session_uuid, _, _, _, _, _, _, _, _, _, _)) = &db_session {
            let _ = siss_graph_db::repo::challenge_repo::insert_challenge(
                &state.pool,
                *session_uuid,
                &nonce,
                &required_attestations,
                expiry,
            )
            .await;
        }

        let response = build_refresh_required_challenge(nonce, required_attestations);
        return (StatusCode::UNAUTHORIZED, Json(response)).into_response();
    }

    // Step 2c: Challenge-response path (if request has challenge_nonce)
    if let Some(challenge_nonce) = &request.challenge_nonce {
        if let Some((session_uuid, _, _, _, _, _, _, _, _, _, _)) = &db_session {
            match siss_graph_db::repo::challenge_repo::fetch_and_consume_challenge(
                &state.pool,
                *session_uuid,
                challenge_nonce,
            )
            .await
            {
                Ok(Some(_)) => {
                    // Challenge consumed successfully; skip Step 3 (validate_refresh_proof) and continue from Step 4
                    // Validate challenge proof to ensure agent signed with correct nonce
                    let timestamp_str = request.timestamp.to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
                    let attestations_json = serde_json::to_string(&request.attestations)
                        .unwrap_or_else(|_| "[]".to_string());

                    if let Err(reason) = validate_challenge_proof(
                        &session_id,
                        challenge_nonce,
                        &timestamp_str,
                        &attestations_json,
                        &request.proof_signature,
                        None,
                    ) {
                        let response = if reason.as_str() == "timestamp_outside_freshness_window" {
                            build_error_response(
                                "timestamp_outside_freshness_window".to_string(),
                                "Challenge response timestamp is older than 5 minutes".to_string(),
                                vec!["Retry with a fresh timestamp (current time ±5 min)".to_string()],
                                None,
                            )
                        } else {
                            error_signature_invalid()
                        };
                        return (StatusCode::BAD_REQUEST, Json(response)).into_response();
                    }

                    // Proceed to Step 4 (validate attestations)
                    // We jump to the attestation validation block below by continuing normally
                }
                Ok(None) => {
                    // Challenge not found, expired, or already consumed
                    let response = error_signature_invalid();
                    return (StatusCode::UNAUTHORIZED, Json(response)).into_response();
                }
                Err(_) => {
                    // DB error; treat as invalid nonce
                    let response = error_signature_invalid();
                    return (StatusCode::UNAUTHORIZED, Json(response)).into_response();
                }
            }
        }
    }

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

    // Phase 6: Detect if session is delegated and apply delegation constraints
    let (is_delegated, effective_tier, lineage_context, effective_envelope) =
        if let Some((_, _, _, _, _, _, parent_session_id, delegated_by_agent_id, ceiling_envelope_json, current_envelope_json, lineage_cache_json)) = &db_session {
            if parent_session_id.is_some() {
                // Session is delegated; apply Phase 6 constraints

                // Clamp tier to ceiling (immutable ceiling enforcement)
                let ceiling_envelope: Option<siss_gatekeeper::refresh::DelegationEnvelope> = ceiling_envelope_json
                    .as_ref()
                    .and_then(|json| serde_json::from_str(json).ok());

                let clamped_tier = if let Some(ceiling) = &ceiling_envelope {
                    clamp_tier_to_ceiling(tier as u32, ceiling.max_tier) as i32
                } else {
                    tier
                };

                // Check ancestor revocation (fail-closed: if ancestor revoked, return error)
                // For now, stub implementation; will be enhanced with DB lookup in Phase 6.1
                if is_ancestor_revoked(&[delegated_by_agent_id.unwrap_or_default()]) {
                    let response = error_ancestor_revoked_subtree();
                    return (StatusCode::UNAUTHORIZED, Json(response)).into_response();
                }

                // Build minimal lineage context from cache (OPSEC-aware: UUID-only, no names)
                let lineage = lineage_cache_json
                    .as_ref()
                    .and_then(|json| serde_json::from_str::<serde_json::Value>(json).ok());

                // Extract effective envelope from current state
                let effective_env = current_envelope_json
                    .as_ref()
                    .and_then(|json| serde_json::from_str::<serde_json::Value>(json).ok());

                (true, clamped_tier, lineage, effective_env)
            } else {
                // Root session: no delegation constraints
                (false, tier, None, None)
            }
        } else {
            // No DB session: not delegated
            (false, tier, None, None)
        };

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
    // Use effective_tier if delegated (clamped to ceiling), otherwise use computed tier
    let response_tier = if is_delegated { effective_tier as u32 } else { tier };
    let evaluation = build_attestation_evaluation(
        score,
        Some(response_tier),
        attestations_eval,
        vec![],
        capability_changes,
    );

    // Step 11: Build and return success response (with optional Phase 6 delegation context)
    let response = if is_delegated {
        build_success_response_with_delegation(should_reuse, session_token, capability_token.clone(), evaluation, lineage_context, effective_envelope)
    } else {
        build_success_response(should_reuse, session_token, capability_token.clone(), evaluation)
    };

    // Step 12: Persist updated trust state to database (best-effort, non-blocking)
    // Use effective_tier for delegated sessions, original tier for root sessions
    if let Some((session_uuid, _, _, _, _, _, _, _, _, _, _)) = db_session {
        let persistence_tier = if is_delegated { effective_tier } else { tier };
        let _ = siss_graph_db::repo::session_repo::update_session_after_refresh(
            &state.pool,
            session_uuid,
            &capability_token.token,
            score as i32,
            persistence_tier,
            Utc::now(),
        )
        .await;
    }

    (StatusCode::OK, Json(response)).into_response()
}
