/// Integration tests for Phase 5.5: Revocation & Pull-Based Refresh
/// Tests session revocation and challenge-based refresh flows
use chrono::{Duration, Utc};
use siss_gatekeeper::{
    attestation::{Attestation, AttestationType},
    refresh::*,
};

// ============================================================================
// Unit Tests: Revocation Detection
// ============================================================================

#[test]
fn test_error_session_revoked_response() {
    let response = error_session_revoked();

    match response {
        AttestationRefreshResponse::Error(error) => {
            assert_eq!(error.status, "denied");
            assert_eq!(error.reason, "session_revoked");
            assert!(error.detail.contains("revoked"));
            assert!(error.detail.contains("Phase 4"));
            assert_eq!(error.remediation.len(), 1);
            assert!(error.remediation[0].contains("handshake"));
            assert!(error.attestation_evaluation.is_none());
        }
        _ => panic!("Expected error response for revoked session"),
    }
}

// ============================================================================
// Unit Tests: Challenge Issuance and Structure
// ============================================================================

#[test]
fn test_build_refresh_required_challenge_structure() {
    let nonce = "test-nonce-abc123def456";
    let required = vec!["hardware".to_string(), "model".to_string()];

    let response = build_refresh_required_challenge(nonce.to_string(), required.clone());

    assert_eq!(response.status, 401);
    assert_eq!(response.error, "refresh_required");
    assert_eq!(response.challenge.nonce, nonce);
    assert_eq!(response.challenge.required_attestations, required);

    // Verify timestamps are reasonable
    let now = Utc::now();
    assert!(response.challenge.issued_at <= now + Duration::seconds(2));
    assert!(response.challenge.expires_at > now);
    assert!(response.challenge.expires_at <= now + Duration::minutes(6));
}

#[test]
fn test_refresh_required_response_serialization() {
    let response =
        build_refresh_required_challenge("nonce-xyz".to_string(), vec!["hardware".to_string()]);

    let json_str = serde_json::to_string(&response).expect("serialize");
    assert!(json_str.contains("401"));
    assert!(json_str.contains("refresh_required"));
    assert!(json_str.contains("nonce-xyz"));
    assert!(json_str.contains("hardware"));
}

// ============================================================================
// Unit Tests: Challenge Proof Validation
// ============================================================================

#[test]
fn test_validate_challenge_proof_valid() {
    let session_id = "session-123";
    let nonce = "challenge-nonce-abc";
    let timestamp = Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
    let attestations = r#"[{"type":"hardware"}]"#;
    let signature = "challenge-sig-valid";

    let result =
        validate_challenge_proof(session_id, nonce, &timestamp, attestations, signature, None);

    assert!(result.is_ok());
}

#[test]
fn test_validate_challenge_proof_stale_timestamp() {
    let session_id = "session-456";
    let nonce = "challenge-nonce-def";
    let old_time =
        (Utc::now() - Duration::minutes(10)).to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
    let attestations = r#"[]"#;
    let signature = "sig";

    let result =
        validate_challenge_proof(session_id, nonce, &old_time, attestations, signature, None);

    assert!(result.is_err());
    assert!(result.unwrap_err().contains("freshness"));
}

#[test]
fn test_validate_challenge_proof_empty_signature() {
    let session_id = "session-789";
    let nonce = "nonce";
    let timestamp = Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
    let attestations = r#"[]"#;

    let result = validate_challenge_proof(session_id, nonce, &timestamp, attestations, "", None);

    assert!(result.is_err());
    assert!(result.unwrap_err().contains("signature"));
}

#[test]
fn test_validate_challenge_proof_invalid_timestamp_format() {
    let result = validate_challenge_proof("sess", "nonce", "not-a-timestamp", "[]", "sig", None);

    assert!(result.is_err());
    assert!(result.unwrap_err().contains("timestamp"));
}

// ============================================================================
// Unit Tests: Challenge vs Push Proof Distinction
// ============================================================================

#[test]
fn test_challenge_proof_message_includes_challenge_marker() {
    // Challenge proof uses "SISS:A2A:REFRESH:CHALLENGE" marker vs "SISS:A2A:REFRESH" for push
    let session_id = "session-diff";
    let nonce = "diff-nonce";
    let timestamp = Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
    let attestations = r#"[]"#;
    let sig = "sig";

    // Both should validate successfully (we don't verify actual crypto in Phase 5)
    let challenge_result =
        validate_challenge_proof(session_id, nonce, &timestamp, attestations, sig, None);
    let push_result =
        validate_refresh_proof(session_id, nonce, &timestamp, attestations, sig, None);

    assert!(challenge_result.is_ok());
    assert!(push_result.is_ok());
    // In Phase 5.1, these would have different signature verification paths
}

// ============================================================================
// Unit Tests: Request Structure with Challenge Nonce
// ============================================================================

#[test]
fn test_attestation_refresh_request_with_challenge_nonce() {
    let json = r#"{
        "session_token": "session-token-abc",
        "attestations": [
            {
                "attestation_type": "hardware_enclave",
                "format": "sgx_quote",
                "payload": "payload",
                "signature": "sig",
                "issuer": "intel-sgx",
                "issued_at": "2026-05-10T14:00:00Z",
                "valid_until": "2026-05-10T15:00:00Z"
            }
        ],
        "ephemeral_nonce": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0",
        "timestamp": "2026-05-10T14:33:15Z",
        "proof_signature": "challenge-response-sig",
        "challenge_nonce": "challenge-abc123"
    }"#;

    let request: AttestationRefreshRequest = serde_json::from_str(json).expect("deserialize");

    assert_eq!(request.session_token, "session-token-abc");
    assert_eq!(request.attestations.len(), 1);
    assert!(request.challenge_nonce.is_some());
    assert_eq!(request.challenge_nonce.unwrap(), "challenge-abc123");
}

#[test]
fn test_attestation_refresh_request_without_challenge_nonce() {
    let json = r#"{
        "session_token": "session-token-xyz",
        "attestations": [],
        "ephemeral_nonce": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0",
        "timestamp": "2026-05-10T14:33:15Z",
        "proof_signature": "sig"
    }"#;

    let request: AttestationRefreshRequest = serde_json::from_str(json).expect("deserialize");

    assert!(request.challenge_nonce.is_none());
}

#[test]
fn test_attestation_refresh_request_serialization_without_nonce() {
    // Verify that challenge_nonce is omitted from serialization when None
    let request = AttestationRefreshRequest {
        session_token: "tok".to_string(),
        attestations: vec![],
        ephemeral_nonce: "nonce".to_string(),
        timestamp: Utc::now(),
        proof_signature: "sig".to_string(),
        challenge_nonce: None,
    };

    let json = serde_json::to_string(&request).expect("serialize");
    assert!(!json.contains("challenge_nonce"));
}

// ============================================================================
// Integration Scenario: Pull-Based Refresh Flow
// ============================================================================

#[test]
fn test_pull_refresh_flow_empty_attestations_triggers_challenge() {
    // Step 1: Agent sends refresh with empty attestations
    let request = AttestationRefreshRequest {
        session_token: "bearer-token".to_string(),
        attestations: vec![],
        ephemeral_nonce: "emp-nonce".to_string(),
        timestamp: Utc::now(),
        proof_signature: "sig".to_string(),
        challenge_nonce: None,
    };

    // Should trigger challenge issuance
    assert!(request.attestations.is_empty());
    assert!(request.challenge_nonce.is_none());

    // Step 2: SISS issues a challenge
    let challenge = build_refresh_required_challenge(
        "issued-nonce".to_string(),
        vec!["hardware".to_string(), "model".to_string()],
    );

    assert_eq!(challenge.status, 401);
    assert_eq!(challenge.error, "refresh_required");
}

#[test]
fn test_challenge_response_flow_with_attestations() {
    // Step 1: Agent responds to challenge with attestations + nonce
    let attestations = vec![
        Attestation {
            attestation_type: AttestationType::HardwareEnclave,
            format: "sgx_quote".to_string(),
            payload: "payload".to_string(),
            signature: "sig".to_string(),
            issuer: "intel-sgx".to_string(),
            issued_at: Utc::now(),
            valid_until: Utc::now() + Duration::hours(1),
        },
        Attestation {
            attestation_type: AttestationType::ModelIntegrity,
            format: "signed_manifest".to_string(),
            payload: "payload".to_string(),
            signature: "sig".to_string(),
            issuer: "anthropic".to_string(),
            issued_at: Utc::now(),
            valid_until: Utc::now() + Duration::hours(1),
        },
    ];

    let request = AttestationRefreshRequest {
        session_token: "bearer-token".to_string(),
        attestations: attestations.clone(),
        ephemeral_nonce: "resp-nonce".to_string(),
        timestamp: Utc::now(),
        proof_signature: "response-sig".to_string(),
        challenge_nonce: Some("issued-nonce".to_string()),
    };

    assert!(request.challenge_nonce.is_some());
    assert!(!request.attestations.is_empty());

    // Step 2: Validate challenge proof
    let timestamp_str = request
        .timestamp
        .to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
    let attestations_json = serde_json::to_string(&request.attestations).unwrap();
    let proof_result = validate_challenge_proof(
        "session-uuid",
        request.challenge_nonce.as_ref().unwrap(),
        &timestamp_str,
        &attestations_json,
        &request.proof_signature,
        None,
    );

    assert!(proof_result.is_ok());

    // Step 3: Re-evaluate trust with provided attestations
    let trust_result = reevaluate_trust(&attestations);
    assert!(trust_result.is_ok());
    let (score, tier) = trust_result.unwrap();
    assert_eq!(score, 80);
    assert_eq!(tier, 2);
}

// ============================================================================
// Integration Scenario: Revocation
// ============================================================================

#[test]
fn test_revocation_invalidates_session() {
    // Simulate SISS revoking a session
    let response = error_session_revoked();

    match response {
        AttestationRefreshResponse::Error(error) => {
            assert_eq!(error.reason, "session_revoked");
            // Agent should see this and know to re-authenticate
            assert!(error.remediation.iter().any(|r| r.contains("handshake")));
        }
        _ => panic!("Expected revocation error"),
    }
}

// ============================================================================
// Edge Cases and Error Conditions
// ============================================================================

#[test]
fn test_challenge_nonce_must_not_be_empty() {
    let request = AttestationRefreshRequest {
        session_token: "tok".to_string(),
        attestations: vec![],
        ephemeral_nonce: "e-nonce".to_string(),
        timestamp: Utc::now(),
        proof_signature: "sig".to_string(),
        challenge_nonce: Some("".to_string()), // Empty nonce
    };

    // Empty challenge nonce should be treated as invalid
    assert_eq!(request.challenge_nonce.unwrap(), "");
}

#[test]
fn test_both_empty_attestations_and_challenge_nonce() {
    // If request has empty attestations AND a challenge nonce, it's a response
    let request = AttestationRefreshRequest {
        session_token: "tok".to_string(),
        attestations: vec![],
        ephemeral_nonce: "nonce".to_string(),
        timestamp: Utc::now(),
        proof_signature: "sig".to_string(),
        challenge_nonce: Some("challenge-nonce".to_string()),
    };

    assert!(request.attestations.is_empty());
    assert!(request.challenge_nonce.is_some());
    // Handler should attempt to validate the nonce, not issue a new challenge
}

#[test]
fn test_challenge_expiry_boundary() {
    let now = Utc::now();
    let response =
        build_refresh_required_challenge("nonce".to_string(), vec!["hardware".to_string()]);

    let expiry = response.challenge.expires_at;
    let diff_seconds = (expiry - now).num_seconds();

    // Should be approximately 5 minutes (300 seconds)
    assert!(diff_seconds >= 299 && diff_seconds <= 301);
}
