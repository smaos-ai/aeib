/// Phase 10: Federation protocol handlers
/// Dynamic renegotiation, settlement, and gossip endpoints

use axum::{
    extract::State,
    http::StatusCode,
    response::{IntoResponse, Json},
};
use chrono::{DateTime, Utc};
use ed25519_dalek::{Signature, Verifier, VerifyingKey};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use siss_graph_db::repo::federation_repo;
use siss_gatekeeper::federation_resolver;
use siss_gatekeeper::attestation::validators::parse_ed25519_pem;

use crate::handler::AgentCardState;

/// Request body for bilateral agreement renegotiation
#[derive(Debug, Deserialize)]
pub struct RenegotiateAgreementRequest {
    pub sovereign_b_id: Uuid,
    pub new_max_admitted_tier: i16,
    pub new_granted_attestation_types: Vec<String>,
    pub new_foreign_agent_budget_cap: i64,
    pub new_expires_at: Option<DateTime<Utc>>,
    pub effective_at: String, // RFC3339 timestamp
    pub agreement_signature: String, // Hex-encoded Ed25519 signature
}

/// Response body for renegotiation endpoint
#[derive(Debug, Serialize)]
pub struct RenegotiateAgreementResponse {
    pub status: String,
    pub new_agreement_id: Uuid,
}

/// Request body for invoice generation
#[derive(Debug, Deserialize)]
pub struct GenerateInvoiceRequest {
    pub debtor_sovereign_id: Uuid,
    pub period_start: DateTime<Utc>,
    pub period_end: DateTime<Utc>,
    pub canonical_invoice_payload: String, // Canonical JSON for hashing
    pub invoice_signature: String, // Hex-encoded Ed25519 signature over invoice_hash
}

/// Response body for invoice generation
#[derive(Debug, Serialize)]
pub struct GenerateInvoiceResponse {
    pub status: String,
    pub invoice_id: Uuid,
    pub total_tokens: i64,
    pub entry_count: i32,
}

/// Request body for invoice settlement
#[derive(Debug, Deserialize)]
pub struct SettleInvoiceRequest {
    pub invoice_id: Uuid,
}

/// Response body for invoice settlement
#[derive(Debug, Serialize)]
pub struct SettleInvoiceResponse {
    pub status: String,
}

/// Request body for gossip message
#[derive(Debug, Deserialize)]
pub struct GossipMessageRequest {
    pub source_sovereign_id: Uuid,
    pub gossip_seq: i64,
    pub message_type: String, // "revocation", "renegotiation", "heartbeat"
    pub payload: serde_json::Value,
    pub payload_signature: String, // Hex-encoded Ed25519 signature
}

/// Response body for gossip endpoint
#[derive(Debug, Serialize)]
pub struct GossipMessageResponse {
    pub status: String,
    pub message_id: Option<Uuid>,
}

/// POST `/.well-known/a2a/federation/renegotiate`
///
/// Atomically renegotiate a bilateral federation agreement.
/// Verifies Ed25519 signature over canonical agreement payload.
/// Returns 403 if unknown sovereign or invalid signature.
pub async fn renegotiate_handler(
    State(state): State<AgentCardState>,
    Json(request): Json<RenegotiateAgreementRequest>,
) -> impl IntoResponse {
    // Step 1: Lookup the peer's public key (fail-closed: unknown sovereign → 404)
    let peer_pubkey_pem = match federation_repo::lookup_sovereign_public_key(&state.pool, request.sovereign_b_id).await {
        Ok(Some(key)) => key,
        Ok(None) => {
            return (
                StatusCode::NOT_FOUND,
                Json(serde_json::json!({
                    "error": "unknown_sovereign",
                    "sovereign_id": request.sovereign_b_id.to_string()
                })),
            )
                .into_response()
        }
        Err(_) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(serde_json::json!({ "error": "database_error" })),
            )
                .into_response()
        }
    };

    // Step 2: Build canonical agreement payload for verification
    let canonical_payload = federation_resolver::build_canonical_agreement_payload(
        &state.sovereign_id.to_string(),
        &request.sovereign_b_id.to_string(),
        request.new_max_admitted_tier as u16,
        &request.new_granted_attestation_types,
        request.new_foreign_agent_budget_cap,
        &request.effective_at,
    );

    // Step 3: Verify Ed25519 signature (fail-closed: invalid signature → 403)
    // 3a. Decode signature from hex to 64-byte array
    let sig_bytes = match hex::decode(&request.agreement_signature) {
        Ok(bytes) if bytes.len() == 64 => {
            let mut arr = [0u8; 64];
            arr.copy_from_slice(&bytes);
            arr
        }
        _ => {
            return (
                StatusCode::FORBIDDEN,
                Json(serde_json::json!({ "error": "invalid_signature_encoding" })),
            )
                .into_response()
        }
    };

    // 3b. Parse PEM public key
    let key_bytes = match parse_ed25519_pem(&peer_pubkey_pem) {
        Ok(bytes) => bytes,
        Err(_) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(serde_json::json!({ "error": "invalid_peer_public_key" })),
            )
                .into_response()
        }
    };

    // 3c. Create VerifyingKey and verify signature
    let verifying_key = match VerifyingKey::from_bytes(&key_bytes) {
        Ok(key) => key,
        Err(_) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(serde_json::json!({ "error": "invalid_peer_public_key" })),
            )
                .into_response()
        }
    };

    let signature = Signature::from_bytes(&sig_bytes);
    if let Err(_) = verifying_key.verify(canonical_payload.as_bytes(), &signature) {
        return (
            StatusCode::FORBIDDEN,
            Json(serde_json::json!({ "error": "invalid_signature" })),
        )
            .into_response();
    }

    // Step 4: Atomically renegotiate (database transaction)
    match federation_repo::renegotiate_federation_agreement(
        &state.pool,
        state.sovereign_id,
        request.sovereign_b_id,
        request.new_max_admitted_tier,
        request.new_granted_attestation_types,
        request.new_foreign_agent_budget_cap,
        request.new_expires_at,
        &request.agreement_signature,
    )
    .await
    {
        Ok(new_agreement_id) => (
            StatusCode::OK,
            Json(RenegotiateAgreementResponse {
                status: "agreement_superseded".to_string(),
                new_agreement_id,
            }),
        )
            .into_response(),
        Err(_) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(serde_json::json!({ "error": "database_error" })),
        )
            .into_response(),
    }
}

/// POST `/.well-known/a2a/federation/invoice/generate`
///
/// Generate a settlement invoice from unpaid credit entries.
/// Creditor (home sovereign) aggregates tokens consumed by debtor.
pub async fn generate_invoice_handler(
    State(state): State<AgentCardState>,
    Json(request): Json<GenerateInvoiceRequest>,
) -> impl IntoResponse {
    match federation_repo::generate_settlement_invoice(
        &state.pool,
        state.sovereign_id,
        request.debtor_sovereign_id,
        request.period_start,
        request.period_end,
        &request.canonical_invoice_payload,
        &request.invoice_signature,
    )
    .await
    {
        Ok((invoice_id, total_tokens, entry_count)) => (
            StatusCode::OK,
            Json(GenerateInvoiceResponse {
                status: "invoice_generated".to_string(),
                invoice_id,
                total_tokens,
                entry_count,
            }),
        )
            .into_response(),
        Err(_) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(serde_json::json!({ "error": "database_error" })),
        )
            .into_response(),
    }
}

/// POST `/.well-known/a2a/federation/invoice/settle`
///
/// Mark an invoice as settled (debtor acknowledges and pays).
pub async fn settle_invoice_handler(
    State(state): State<AgentCardState>,
    Json(request): Json<SettleInvoiceRequest>,
) -> impl IntoResponse {
    match federation_repo::mark_invoice_settled(&state.pool, request.invoice_id, state.sovereign_id).await {
        Ok(settled) => {
            if settled {
                (
                    StatusCode::OK,
                    Json(SettleInvoiceResponse {
                        status: "invoice_settled".to_string(),
                    }),
                )
                    .into_response()
            } else {
                (
                    StatusCode::CONFLICT,
                    Json(serde_json::json!({
                        "error": "invoice_not_found_or_already_settled",
                        "invoice_id": request.invoice_id.to_string()
                    })),
                )
                    .into_response()
            }
        }
        Err(_) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(serde_json::json!({ "error": "database_error" })),
        )
            .into_response(),
    }
}

/// POST `/.well-known/a2a/federation/gossip`
///
/// Receive a gossip message from a peer sovereign.
/// Idempotent: duplicate (source_sovereign_id, gossip_seq) returns 200 "duplicate_ignored".
pub async fn gossip_receive_handler(
    State(state): State<AgentCardState>,
    Json(request): Json<GossipMessageRequest>,
) -> impl IntoResponse {
    use siss_graph_db::repo::gossip_repo;

    // Step 1: Lookup peer's public key (fail-closed: unknown sovereign → 403)
    let peer_pubkey_pem = match federation_repo::lookup_sovereign_public_key(&state.pool, request.source_sovereign_id).await {
        Ok(Some(key)) => key,
        Ok(None) => {
            return (
                StatusCode::FORBIDDEN,
                Json(serde_json::json!({
                    "error": "unknown_sovereign",
                    "source_sovereign_id": request.source_sovereign_id.to_string()
                })),
            )
                .into_response()
        }
        Err(_) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(serde_json::json!({ "error": "database_error" })),
            )
                .into_response()
        }
    };

    // Step 2: Decode signature and parse PEM public key
    let sig_bytes = match hex::decode(&request.payload_signature) {
        Ok(bytes) if bytes.len() == 64 => {
            let mut arr = [0u8; 64];
            arr.copy_from_slice(&bytes);
            arr
        }
        _ => {
            return (
                StatusCode::FORBIDDEN,
                Json(serde_json::json!({ "error": "invalid_signature_encoding" })),
            )
                .into_response()
        }
    };

    let key_bytes = match parse_ed25519_pem(&peer_pubkey_pem) {
        Ok(bytes) => bytes,
        Err(_) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(serde_json::json!({ "error": "invalid_peer_public_key" })),
            )
                .into_response()
        }
    };

    // Step 3: Verify signature over canonical gossip payload
    let verifying_key = match VerifyingKey::from_bytes(&key_bytes) {
        Ok(key) => key,
        Err(_) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(serde_json::json!({ "error": "invalid_peer_public_key" })),
            )
                .into_response()
        }
    };

    let payload_str = request.payload.to_string();
    let signature = Signature::from_bytes(&sig_bytes);
    if let Err(_) = verifying_key.verify(payload_str.as_bytes(), &signature) {
        return (
            StatusCode::FORBIDDEN,
            Json(serde_json::json!({ "error": "invalid_signature" })),
        )
            .into_response();
    }

    // Step 4: Insert gossip message (idempotent)
    let message_id = match gossip_repo::insert_gossip_message_idempotent(
        &state.pool,
        request.source_sovereign_id,
        request.gossip_seq,
        &request.message_type,
        &request.payload,
        &request.payload_signature,
    )
    .await
    {
        Ok(Some(id)) => id,
        Ok(None) => {
            // Duplicate (already seen)
            return (
                StatusCode::OK,
                Json(GossipMessageResponse {
                    status: "duplicate_ignored".to_string(),
                    message_id: None,
                }),
            )
                .into_response();
        }
        Err(_) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(serde_json::json!({ "error": "database_error" })),
            )
                .into_response()
        }
    };

    // Step 5: Route by message type
    match request.message_type.as_str() {
        "revocation" => {
            // Extract agent_id and revoked_at from payload
            if let Some(agent_id) = request.payload.get("agent_id").and_then(|v| v.as_str()) {
                let revoked_at = request.payload
                    .get("revoked_at")
                    .and_then(|v| v.as_str())
                    .and_then(|s| DateTime::parse_from_rfc3339(s).ok())
                    .map(|dt| dt.with_timezone(&Utc));

                if let Some(revoked_at) = revoked_at {
                    let _ = federation_repo::insert_revocation_from_gossip(
                        &state.pool,
                        agent_id,
                        request.source_sovereign_id,
                        revoked_at,
                        &request.payload_signature,
                    )
                    .await;
                }
            }
        }
        "renegotiation" => {
            // Gossip is audit record only; no side effect
        }
        "heartbeat" => {
            // Gossip is audit record only; no side effect
        }
        _ => {}
    }

    // Step 6: Mark as processed
    let _ = gossip_repo::mark_gossip_message_processed(&state.pool, message_id).await;

    (
        StatusCode::OK,
        Json(GossipMessageResponse {
            status: "accepted".to_string(),
            message_id: Some(message_id),
        }),
    )
        .into_response()
}
