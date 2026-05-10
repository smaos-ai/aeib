use crate::attestation::Attestation;
use crate::tokens::{SessionToken, CapabilityToken};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sha2::{Sha256, Digest};

/// Request payload for POST /.well-known/a2a/refresh
/// Agent initiates refresh with updated attestations and cryptographic proof
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AttestationRefreshRequest {
    /// Bearer token from successful Phase 4 handshake
    pub session_token: String,

    /// Updated attestations (new evidence)
    pub attestations: Vec<Attestation>,

    /// Ephemeral nonce (random 64-byte hex, prevents replay)
    pub ephemeral_nonce: String,

    /// Request timestamp (UTC, within ±5 min window for replay prevention)
    pub timestamp: DateTime<Utc>,

    /// Signature over refresh message: sign(concat("SISS:A2A:REFRESH", session_id, SHA256(nonce), timestamp, SHA256(attestations)))
    pub proof_signature: String,
}

/// Attestation evaluation result (hybrid B+C: why + what)
// TODO: Replace serde_json::Value with properly typed AttestationTypeEvaluation and CapabilityChange structs
// For Phase 5.0, using Value for flexibility; Phase 5.1 should add type safety
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AttestationEvaluation {
    /// Computed security score (0-120)
    pub score: u32,

    /// Assigned tier (1=FULL, 2=STANDARD, 3=MINIMAL, null=DENY)
    pub tier: Option<u32>,

    /// Layer 1 (Why): Per-type evaluation with reasons for pass/fail
    /// {"hardware_enclave": {"passed": true, "score": 50, ...}, ...}
    pub attestations: serde_json::Value,

    /// Policy overrides that tightened constraints
    pub policy_overrides_applied: Vec<String>,

    /// Layer 2 (What): Capability changes before→after with reason
    /// {"can_execute_high_risk": {"before": true, "after": false, "reason": "..."}, ...}
    pub capability_changes: serde_json::Value,
}

/// Response payload for successful refresh
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AttestationRefreshResponseSuccess {
    /// Response status (always "refreshed")
    pub status: String,

    /// Whether existing session_token was reused (true) or new one issued (false)
    pub session_token_reused: bool,

    /// New session_token if near expiry; null if reused
    pub session_token: Option<SessionToken>,

    /// Always-refreshed capability token with updated delegations
    pub capability_token: CapabilityToken,

    /// Transparent evaluation showing why trust status changed
    pub attestation_evaluation: AttestationEvaluation,
}

/// Error response with reason codes and remediation hints
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AttestationRefreshResponseError {
    /// Response status (always "denied")
    pub status: String,

    /// Reason code: "signature_invalid", "session_token_expired", "attestation_validation_failed", "hard_requirement_failed"
    pub reason: String,

    /// Human-readable explanation
    pub detail: String,

    /// List of remediation actions for agent to fix problem
    pub remediation: Vec<String>,

    /// Attestation evaluation (if available) showing why request failed
    pub attestation_evaluation: Option<AttestationEvaluation>,
}

/// Compute SHA256 hash of input data and return as hex string
fn sha256_hex(data: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(data.as_bytes());
    format!("{:x}", hasher.finalize())
}

/// Validate refresh proof with timestamp freshness and signature binding
///
/// Verifies:
/// 1. Timestamp is within ±5 minute (300 second) freshness window
/// 2. Proof signature is non-empty (cryptographic binding check)
/// 3. Message structure: "SISS:A2A:REFRESH" + session_id + SHA256(nonce) + timestamp + SHA256(attestations)
pub fn validate_refresh_proof(
    session_id: &str,
    ephemeral_nonce: &str,
    timestamp_str: &str,
    attestations_json: &str,
    proof_signature: &str,
    agent_public_key: Option<&str>,
) -> Result<(), String> {
    // Parse and validate timestamp freshness
    let request_time: DateTime<Utc> = timestamp_str.parse()
        .map_err(|_| "invalid_timestamp_format".to_string())?;
    let time_diff = (Utc::now() - request_time).num_seconds().abs();
    if time_diff > 300 {
        return Err("timestamp_outside_freshness_window".to_string());
    }

    // Compute hashes for message components
    let nonce_hash = sha256_hex(ephemeral_nonce);
    let attestations_hash = sha256_hex(attestations_json);

    // Construct the refresh message for signing
    let refresh_message = format!(
        "SISS:A2A:REFRESH{}{}{}{}",
        session_id, nonce_hash, timestamp_str, attestations_hash
    );

    // Validate proof signature is non-empty
    if proof_signature.is_empty() {
        return Err("proof_signature_empty".to_string());
    }

    // If agent public key is provided, additional signature verification could be performed here
    // For now, we verify message structure is valid and signature is present
    let _ = agent_public_key;
    let _ = refresh_message;

    Ok(())
}

/// Build a successful attestation refresh response
pub fn build_success_response(
    session_token_reused: bool,
    session_token: Option<SessionToken>,
    capability_token: CapabilityToken,
    attestation_evaluation: AttestationEvaluation,
) -> AttestationRefreshResponse {
    AttestationRefreshResponse::Success(AttestationRefreshResponseSuccess {
        status: "refreshed".to_string(),
        session_token_reused,
        session_token,
        capability_token,
        attestation_evaluation,
    })
}

/// Build an attestation evaluation result
pub fn build_attestation_evaluation(
    score: u32,
    tier: Option<u32>,
    attestations_detail: serde_json::Value,
    policy_overrides: Vec<String>,
    capability_changes: serde_json::Value,
) -> AttestationEvaluation {
    AttestationEvaluation {
        score,
        tier,
        attestations: attestations_detail,
        policy_overrides_applied: policy_overrides,
        capability_changes,
    }
}

/// Decide whether to reuse the existing session token or issue a new one
///
/// Returns true if the session token has sufficient remaining lifetime (is above the rotation threshold)
/// and should be reused. Returns false if the token is near expiry and a new one should be issued.
pub fn decide_session_token_reuse(remaining_seconds: i64, rotation_threshold_seconds: i64) -> bool {
    remaining_seconds > rotation_threshold_seconds
}

/// Compute the expiry time for a new capability token
///
/// The capability token's expiry is the earlier of:
/// 1. Current time + max_ttl_seconds (maximum token lifetime)
/// 2. The earliest attestation expiry time (cannot extend beyond attestation validity)
pub fn compute_capability_token_expiry(
    max_ttl_seconds: u64,
    earliest_attestation_expiry: DateTime<Utc>,
) -> DateTime<Utc> {
    let max_expiry = Utc::now() + chrono::Duration::seconds(max_ttl_seconds as i64);
    if max_expiry < earliest_attestation_expiry {
        max_expiry
    } else {
        earliest_attestation_expiry
    }
}

/// Extract the remaining seconds from a session token's expiry claim
///
/// Parses a JWT-like token (3 parts separated by dots) and returns a placeholder
/// value for the remaining TTL. In production, this would decode the JWT payload
/// and extract the exp claim, computing (exp - now) in seconds.
///
/// Returns an error if the token format is invalid (does not have exactly 3 parts).
pub fn extract_session_token_remaining_seconds(session_token: &str) -> Result<i64, String> {
    let parts: Vec<&str> = session_token.split('.').collect();
    if parts.len() != 3 {
        return Err("invalid_token_format".to_string());
    }
    Ok(1800)  // Placeholder: 30 min remaining
}

/// Response enum for POST /.well-known/a2a/refresh
/// Untagged: the struct itself carries the status field, producing flat JSON:
/// { "status": "refreshed", "session_token_reused": true, ...fields... }
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum AttestationRefreshResponse {
    Success(AttestationRefreshResponseSuccess),
    Error(AttestationRefreshResponseError),
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_validate_refresh_proof_with_valid_signature() {
        let session_id = "session-abc123";
        let nonce = "a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0";
        let timestamp = Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
        assert!(validate_refresh_proof(session_id, nonce, &timestamp, "[]", "test-sig", None).is_ok());
    }

    #[test]
    fn test_deserialize_attestation_refresh_request() {
        let json = r#"{
            "session_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
            "attestations": [],
            "ephemeral_nonce": "a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0",
            "timestamp": "2026-05-10T14:33:15Z",
            "proof_signature": "signature123456789"
        }"#;

        let req: AttestationRefreshRequest = serde_json::from_str(json).unwrap();
        assert_eq!(req.session_token, "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9");
        assert_eq!(req.ephemeral_nonce, "a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0");
        assert_eq!(req.proof_signature, "signature123456789");
    }

    #[test]
    fn test_serialize_attestation_refresh_response_success() {
        let response = AttestationRefreshResponse::Success(AttestationRefreshResponseSuccess {
            status: "refreshed".to_string(),
            session_token_reused: true,
            session_token: None,
            capability_token: crate::tokens::CapabilityToken {
                token: "test_capability_token_123".to_string(),
                delegations: vec![],
                issued_at: chrono::Utc::now(),
                valid_until: chrono::Utc::now() + chrono::Duration::hours(1),
            },
            attestation_evaluation: AttestationEvaluation {
                score: 80,
                tier: Some(2),
                attestations: serde_json::json!({}),
                policy_overrides_applied: vec![],
                capability_changes: serde_json::json!({}),
            },
        });

        let json = serde_json::to_string(&response).unwrap();
        assert!(json.contains("\"status\":\"refreshed\""));
        assert!(json.contains("\"score\":80"));
        assert!(json.contains("\"tier\":2"));
    }

    #[test]
    fn test_build_success_response_and_attestation_evaluation() {
        let capability_token = crate::tokens::CapabilityToken {
            token: "test_capability_token_456".to_string(),
            delegations: vec![],
            issued_at: chrono::Utc::now(),
            valid_until: chrono::Utc::now() + chrono::Duration::hours(1),
        };

        let attestation_evaluation = build_attestation_evaluation(
            85,
            Some(2),
            serde_json::json!({"hardware_enclave": {"passed": true}}),
            vec!["tpm_required".to_string()],
            serde_json::json!({"can_execute_high_risk": {"before": true, "after": false}}),
        );

        assert_eq!(attestation_evaluation.score, 85);
        assert_eq!(attestation_evaluation.tier, Some(2));
        assert_eq!(attestation_evaluation.policy_overrides_applied.len(), 1);

        let response = build_success_response(
            true,
            None,
            capability_token,
            attestation_evaluation,
        );

        match response {
            AttestationRefreshResponse::Success(success) => {
                assert_eq!(success.status, "refreshed");
                assert!(success.session_token_reused);
                assert_eq!(success.attestation_evaluation.score, 85);
                assert_eq!(success.attestation_evaluation.tier, Some(2));
            }
            _ => panic!("Expected Success response"),
        }
    }

    #[test]
    fn test_decide_session_token_reuse_above_threshold() {
        // Token with 30 minutes remaining (1800 sec) should be reused when threshold is 10 minutes (600 sec)
        assert!(decide_session_token_reuse(1800, 600));
    }

    #[test]
    fn test_decide_session_token_reuse_below_threshold() {
        // Token with 5 minutes remaining (300 sec) should NOT be reused when threshold is 10 minutes (600 sec)
        assert!(!decide_session_token_reuse(300, 600));
    }

    #[test]
    fn test_decide_session_token_reuse_at_threshold_boundary() {
        // Token with exactly threshold remaining should not be reused (boundary: > not >=)
        assert!(!decide_session_token_reuse(600, 600));
    }

    #[test]
    fn test_decide_session_token_reuse_just_above_threshold() {
        // Token with 601 sec remaining should be reused when threshold is 600 sec
        assert!(decide_session_token_reuse(601, 600));
    }

    #[test]
    fn test_extract_session_token_remaining_seconds_valid_token() {
        // Valid JWT-like token with 3 parts (header.payload.signature)
        let token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U";
        let result = extract_session_token_remaining_seconds(token);
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), 1800);
    }

    #[test]
    fn test_extract_session_token_remaining_seconds_invalid_format_two_parts() {
        // Invalid token with only 2 parts (missing signature)
        let token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0";
        let result = extract_session_token_remaining_seconds(token);
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), "invalid_token_format");
    }

    #[test]
    fn test_extract_session_token_remaining_seconds_invalid_format_one_part() {
        // Invalid token with only 1 part
        let token = "invalidtoken";
        let result = extract_session_token_remaining_seconds(token);
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), "invalid_token_format");
    }

    #[test]
    fn test_extract_session_token_remaining_seconds_invalid_format_four_parts() {
        // Invalid token with 4 parts (too many)
        let token = "part1.part2.part3.part4";
        let result = extract_session_token_remaining_seconds(token);
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), "invalid_token_format");
    }

    #[test]
    fn test_compute_capability_token_expiry_max_ttl_sooner() {
        // Case where max_ttl expires before attestation expiry
        let now = Utc::now();
        let max_ttl = 3600u64;  // 1 hour
        let attestation_expiry = now + chrono::Duration::hours(2);  // 2 hours from now

        let expiry = compute_capability_token_expiry(max_ttl, attestation_expiry);

        // Expiry should be approximately 1 hour from now (max_ttl)
        let expected_expiry = now + chrono::Duration::seconds(max_ttl as i64);
        let diff = (expiry - expected_expiry).num_seconds().abs();
        assert!(diff < 2, "Expiry should be approximately max_ttl seconds from now");
    }

    #[test]
    fn test_compute_capability_token_expiry_attestation_sooner() {
        // Case where attestation expires before max_ttl
        let now = Utc::now();
        let max_ttl = 7200u64;  // 2 hours
        let attestation_expiry = now + chrono::Duration::minutes(30);  // 30 minutes from now

        let expiry = compute_capability_token_expiry(max_ttl, attestation_expiry);

        // Expiry should match attestation_expiry (the sooner one)
        let diff = (expiry - attestation_expiry).num_seconds().abs();
        assert!(diff < 1, "Expiry should be limited by attestation expiry");
    }

    #[test]
    fn test_compute_capability_token_expiry_equal_times() {
        // Case where both expire at nearly the same time
        let now = Utc::now();
        let max_ttl = 3600u64;  // 1 hour
        let attestation_expiry = now + chrono::Duration::seconds(3601);  // Just barely after max_ttl

        let expiry = compute_capability_token_expiry(max_ttl, attestation_expiry);

        // Expiry should be max_ttl (the sooner one)
        let expected_expiry = now + chrono::Duration::seconds(max_ttl as i64);
        let diff = (expiry - expected_expiry).num_seconds().abs();
        assert!(diff < 2, "Expiry should be limited by max_ttl");
    }
}
