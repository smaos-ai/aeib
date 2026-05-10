/// Integration tests for the attestation refresh flow
/// Tests the complete POST /.well-known/a2a/refresh endpoint workflow

use chrono::{Duration, Utc};
use siss_gatekeeper::{
    attestation::{Attestation, AttestationType},
    refresh::*,
    tokens::CapabilityToken,
};
use serde_json::json;

// ============================================================================
// Test Scenario 1: Successful refresh with session token reuse
// ============================================================================

#[test]
fn test_refresh_successful_session_token_reused() {
    // Simulate an agent with sufficient remaining session TTL (30 min > 10 min threshold)
    let remaining_seconds = 1800i64; // 30 minutes
    let rotation_threshold = 600i64; // 10 minutes

    let should_reuse = decide_session_token_reuse(remaining_seconds, rotation_threshold);
    assert!(should_reuse, "Token with 30 min remaining should be reused");
}

#[test]
fn test_refresh_response_success_with_reused_session_token() {
    // Build a success response where session token is reused
    let capability_token = CapabilityToken {
        token: "cap-token-123".to_string(),
        delegations: vec![],
        issued_at: Utc::now(),
        valid_until: Utc::now() + Duration::hours(24),
    };

    let evaluation = build_attestation_evaluation(
        80,
        Some(2),
        json!({
            "hardware_enclave": {
                "passed": true,
                "score_contribution": 50,
                "issuer": "intel-sgx"
            },
            "model_integrity": {
                "passed": true,
                "score_contribution": 30,
                "issuer": "anthropic"
            }
        }),
        vec![],
        json!({}),
    );

    let response = build_success_response(true, None, capability_token, evaluation);

    match response {
        AttestationRefreshResponse::Success(success) => {
            assert_eq!(success.status, "refreshed");
            assert!(success.session_token_reused);
            assert!(success.session_token.is_none());
            assert_eq!(success.attestation_evaluation.score, 80);
            assert_eq!(success.attestation_evaluation.tier, Some(2));
        }
        _ => panic!("Expected success response"),
    }
}

// ============================================================================
// Test Scenario 2: Session token rotation when near expiry
// ============================================================================

#[test]
fn test_refresh_session_token_rotated_near_expiry() {
    // Token with only 5 minutes remaining (< 10 min threshold) should be rotated
    let remaining_seconds = 300i64; // 5 minutes
    let rotation_threshold = 600i64; // 10 minutes

    let should_reuse = decide_session_token_reuse(remaining_seconds, rotation_threshold);
    assert!(!should_reuse, "Token with 5 min remaining should be rotated");
}

#[test]
fn test_refresh_response_success_with_new_session_token() {
    // Build a success response where session token is rotated
    let new_session_token_value = "new-session-token-xyz";
    let new_capability_token = CapabilityToken {
        token: "new-cap-token".to_string(),
        delegations: vec![],
        issued_at: Utc::now(),
        valid_until: Utc::now() + Duration::hours(24),
    };

    let evaluation = build_attestation_evaluation(
        85,
        Some(2),
        json!({}),
        vec!["rate_limit_enforced".to_string()],
        json!({}),
    );

    // Simulate a new session token being issued
    let new_session_token = siss_gatekeeper::tokens::SessionToken {
        token: new_session_token_value.to_string(),
        expires_in: 3600,
        token_type: "Bearer".to_string(),
    };

    let response = build_success_response(
        false,
        Some(new_session_token.clone()),
        new_capability_token,
        evaluation,
    );

    match response {
        AttestationRefreshResponse::Success(success) => {
            assert_eq!(success.status, "refreshed");
            assert!(!success.session_token_reused);
            assert!(success.session_token.is_some());
            let token = success.session_token.unwrap();
            assert_eq!(token.token, new_session_token_value);
            assert_eq!(token.token_type, "Bearer");
        }
        _ => panic!("Expected success response"),
    }
}

// ============================================================================
// Test Scenario 3: Trust re-evaluation with different tier assignments
// ============================================================================

#[test]
fn test_refresh_reevaluate_trust_tier1_full_delegation() {
    // With hardware + model + sovereign = 100 points -> Tier 1 (FULL)
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
        Attestation {
            attestation_type: AttestationType::SovereignOrigin,
            format: "signed_manifest".to_string(),
            payload: "payload".to_string(),
            signature: "sig".to_string(),
            issuer: "origin-issuer".to_string(),
            issued_at: Utc::now(),
            valid_until: Utc::now() + Duration::hours(1),
        },
    ];

    let result = reevaluate_trust(&attestations);
    assert!(result.is_ok());
    let (score, tier) = result.unwrap();
    assert_eq!(score, 100);
    assert_eq!(tier, 1, "Score 100 should assign Tier 1 (FULL)");
}

#[test]
fn test_refresh_reevaluate_trust_tier2_standard_delegation() {
    // With hardware + model = 80 points -> Tier 2 (STANDARD)
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

    let result = reevaluate_trust(&attestations);
    assert!(result.is_ok());
    let (score, tier) = result.unwrap();
    assert_eq!(score, 80);
    assert_eq!(tier, 2, "Score 80 should assign Tier 2 (STANDARD)");
}

#[test]
fn test_refresh_reevaluate_trust_tier3_minimal_delegation() {
    // With hardware only = 50 points -> Tier 3 (MINIMAL)
    let attestations = vec![Attestation {
        attestation_type: AttestationType::HardwareEnclave,
        format: "sgx_quote".to_string(),
        payload: "payload".to_string(),
        signature: "sig".to_string(),
        issuer: "intel-sgx".to_string(),
        issued_at: Utc::now(),
        valid_until: Utc::now() + Duration::hours(1),
    }];

    let result = reevaluate_trust(&attestations);
    assert!(result.is_ok());
    let (score, tier) = result.unwrap();
    assert_eq!(score, 50);
    assert_eq!(tier, 3, "Score 50 should assign Tier 3 (MINIMAL)");
}

// ============================================================================
// Test Scenario 4: Insufficient trust score (< 40) -> DENY
// ============================================================================

#[test]
fn test_refresh_reevaluate_trust_insufficient_score_denied() {
    // With only runtime integrity = 20 points -> INSUFFICIENT
    let attestations = vec![Attestation {
        attestation_type: AttestationType::RuntimeIntegrity,
        format: "signed_manifest".to_string(),
        payload: "payload".to_string(),
        signature: "sig".to_string(),
        issuer: "runtime".to_string(),
        issued_at: Utc::now(),
        valid_until: Utc::now() + Duration::hours(1),
    }];

    let result = reevaluate_trust(&attestations);
    assert!(result.is_err());
    assert_eq!(
        result.unwrap_err(),
        "insufficient_security_tier",
        "Score < 40 should return error"
    );
}

#[test]
fn test_refresh_error_response_insufficient_trust() {
    let response = build_error_response(
        "insufficient_trust".to_string(),
        "Provided attestations score only 20, minimum 40 required".to_string(),
        vec![
            "Obtain additional attestations (model_integrity, sovereign_origin, etc.)".to_string(),
            "Ensure hardware_enclave attestation is fresh".to_string(),
        ],
        None,
    );

    match response {
        AttestationRefreshResponse::Error(error) => {
            assert_eq!(error.status, "denied");
            assert_eq!(error.reason, "insufficient_trust");
            assert_eq!(error.remediation.len(), 2);
        }
        _ => panic!("Expected error response"),
    }
}

// ============================================================================
// Test Scenario 5: Capability token expiry calculation
// ============================================================================

#[test]
fn test_refresh_capability_token_expiry_limited_by_max_ttl() {
    // Case: max_ttl is shorter than attestation validity
    let max_ttl = 3600u64; // 1 hour
    let attestation_expiry = Utc::now() + Duration::hours(24); // 24 hours from now

    let expiry = compute_capability_token_expiry(max_ttl, attestation_expiry);
    let expected = Utc::now() + Duration::seconds(max_ttl as i64);

    let diff = (expiry - expected).num_seconds().abs();
    assert!(
        diff < 2,
        "Token expiry should be limited by max_ttl (1 hour)"
    );
}

#[test]
fn test_refresh_capability_token_expiry_limited_by_attestation() {
    // Case: attestation expires sooner than max_ttl
    let max_ttl = 86400u64; // 24 hours
    let attestation_expiry = Utc::now() + Duration::minutes(30); // 30 minutes

    let expiry = compute_capability_token_expiry(max_ttl, attestation_expiry);

    let diff = (expiry - attestation_expiry).num_seconds().abs();
    assert!(
        diff < 1,
        "Token expiry should not exceed earliest attestation expiry"
    );
}

// ============================================================================
// Test Scenario 6: Attestation proof validation
// ============================================================================

#[test]
fn test_refresh_proof_validation_valid_timestamp() {
    // Fresh request within ±5 minute window should pass
    let session_id = "session-abc123";
    let nonce = "a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0";
    let timestamp = Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
    let attestations_json = r#"[{"type":"hardware_enclave"}]"#;
    let proof_signature = "valid-sig";

    let result =
        validate_refresh_proof(session_id, nonce, &timestamp, attestations_json, proof_signature, None);
    assert!(
        result.is_ok(),
        "Fresh request within window should validate"
    );
}

#[test]
fn test_refresh_proof_validation_stale_timestamp() {
    // Request older than 5 minutes should be rejected
    let session_id = "session-abc123";
    let nonce = "a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0";
    let old_timestamp = (Utc::now() - Duration::minutes(6)).to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
    let attestations_json = r#"[{"type":"hardware_enclave"}]"#;
    let proof_signature = "valid-sig";

    let result = validate_refresh_proof(
        session_id,
        nonce,
        &old_timestamp,
        attestations_json,
        proof_signature,
        None,
    );
    assert!(
        result.is_err(),
        "Request older than 5 minutes should fail"
    );
    assert_eq!(
        result.unwrap_err(),
        "timestamp_outside_freshness_window"
    );
}

#[test]
fn test_refresh_proof_validation_empty_signature() {
    // Empty proof signature should be rejected
    let session_id = "session-abc123";
    let nonce = "a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0";
    let timestamp = Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
    let attestations_json = r#"[{"type":"hardware_enclave"}]"#;
    let proof_signature = "";

    let result = validate_refresh_proof(
        session_id,
        nonce,
        &timestamp,
        attestations_json,
        proof_signature,
        None,
    );
    assert!(result.is_err(), "Empty signature should fail validation");
    assert_eq!(result.unwrap_err(), "proof_signature_empty");
}

// ============================================================================
// Test Scenario 7: Error responses with complete evaluation details
// ============================================================================

#[test]
fn test_refresh_error_response_signature_invalid() {
    let response = error_signature_invalid();

    match response {
        AttestationRefreshResponse::Error(error) => {
            assert_eq!(error.status, "denied");
            assert_eq!(error.reason, "signature_invalid");
            assert!(error.detail.contains("proof_signature"));
            assert_eq!(error.remediation.len(), 2);
            assert!(error.attestation_evaluation.is_none());
        }
        _ => panic!("Expected error response"),
    }
}

#[test]
fn test_refresh_error_response_session_token_expired() {
    let expired_at = Utc::now() - Duration::hours(1);
    let response = error_session_token_expired(expired_at);

    match response {
        AttestationRefreshResponse::Error(error) => {
            assert_eq!(error.status, "denied");
            assert_eq!(error.reason, "session_token_expired");
            assert!(error.detail.contains("expired at"));
            assert_eq!(error.remediation.len(), 1);
            assert!(error.remediation[0].contains("handshake"));
        }
        _ => panic!("Expected error response"),
    }
}

#[test]
fn test_refresh_error_response_hard_requirement_failed() {
    let response = error_hard_requirement_failed("hardware_enclave".to_string());

    match response {
        AttestationRefreshResponse::Error(error) => {
            assert_eq!(error.status, "denied");
            assert_eq!(error.reason, "hard_requirement_failed");
            assert!(error.detail.contains("TrustPolicyNode"));
            assert!(error.detail.contains("hardware_enclave"));
            assert_eq!(error.remediation.len(), 1);
        }
        _ => panic!("Expected error response"),
    }
}

// ============================================================================
// Test Scenario 8: Attestations evaluation report (Layer 1: Why)
// ============================================================================

#[test]
fn test_refresh_build_attestations_evaluation_detailed_report() {
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

    let report = build_attestations_evaluation(&attestations, 80);

    // Check hardware enclave
    assert!(report["hardware_enclave"]["passed"].as_bool().unwrap());
    assert_eq!(
        report["hardware_enclave"]["score_contribution"].as_u64().unwrap(),
        50
    );
    assert_eq!(
        report["hardware_enclave"]["issuer"].as_str().unwrap(),
        "intel-sgx"
    );

    // Check model integrity
    assert!(report["model_integrity"]["passed"].as_bool().unwrap());
    assert_eq!(
        report["model_integrity"]["score_contribution"].as_u64().unwrap(),
        30
    );
    assert_eq!(
        report["model_integrity"]["issuer"].as_str().unwrap(),
        "anthropic"
    );
}

// ============================================================================
// Test Scenario 9: Capability changes report (Layer 2: What)
// ============================================================================

#[test]
fn test_refresh_build_capability_changes_tier_demotion() {
    // Tier 1 -> Tier 2 (demotion): some capabilities lost
    let changes = build_capability_changes(Some(1), 2);

    // In Phase 5.0, this returns empty object (Phase 5.1 will populate)
    assert_eq!(changes.as_object().unwrap().len(), 0);
}

#[test]
fn test_refresh_build_capability_changes_tier_promotion() {
    // Tier 3 -> Tier 2 (promotion): additional capabilities gained
    let changes = build_capability_changes(Some(3), 2);

    assert_eq!(changes.as_object().unwrap().len(), 0);
}

// ============================================================================
// Test Scenario 10: Session token extraction from JWT-like format
// ============================================================================

#[test]
fn test_refresh_extract_session_token_remaining_seconds_valid() {
    let token = "header.payload.signature";
    let result = extract_session_token_remaining_seconds(token);

    assert!(result.is_ok());
    assert_eq!(result.unwrap(), 1800, "Should return placeholder 30 min");
}

#[test]
fn test_refresh_extract_session_token_remaining_seconds_invalid_format() {
    let token = "invalid.format";
    let result = extract_session_token_remaining_seconds(token);

    assert!(result.is_err());
    assert_eq!(result.unwrap_err(), "invalid_token_format");
}

// ============================================================================
// Test Scenario 11: Duplicate attestation type handling
// ============================================================================

#[test]
fn test_refresh_reevaluate_trust_duplicate_types_counted_once() {
    // Multiple attestations of same type should only score once
    let attestations = vec![
        Attestation {
            attestation_type: AttestationType::HardwareEnclave,
            format: "sgx_quote".to_string(),
            payload: "payload1".to_string(),
            signature: "sig1".to_string(),
            issuer: "intel".to_string(),
            issued_at: Utc::now(),
            valid_until: Utc::now() + Duration::hours(1),
        },
        Attestation {
            attestation_type: AttestationType::HardwareEnclave, // Same type, should not double-count
            format: "sgx_quote_v2".to_string(),
            payload: "payload2".to_string(),
            signature: "sig2".to_string(),
            issuer: "intel".to_string(),
            issued_at: Utc::now(),
            valid_until: Utc::now() + Duration::hours(1),
        },
        Attestation {
            attestation_type: AttestationType::ModelIntegrity,
            format: "signed_manifest".to_string(),
            payload: "payload3".to_string(),
            signature: "sig3".to_string(),
            issuer: "anthropic".to_string(),
            issued_at: Utc::now(),
            valid_until: Utc::now() + Duration::hours(1),
        },
    ];

    let result = reevaluate_trust(&attestations);
    assert!(result.is_ok());
    let (score, tier) = result.unwrap();

    // Score should be 50 (HW once) + 30 (Model) = 80, NOT 100
    assert_eq!(score, 80, "Duplicate types should be counted only once");
    assert_eq!(tier, 2);
}

// ============================================================================
// Test Scenario 12: Full end-to-end refresh flow
// ============================================================================

#[test]
fn test_refresh_complete_flow_success() {
    // Simulate a complete refresh: request -> validation -> re-evaluation -> response

    // 1. Request validation: check proof freshness
    let session_id = "sess-uuid-123";
    let nonce = "a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0";
    let timestamp = Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
    let proof_sig = "proof-signature-here";

    let validation_result = validate_refresh_proof(
        session_id,
        nonce,
        &timestamp,
        "[]",
        proof_sig,
        None,
    );
    assert!(
        validation_result.is_ok(),
        "Request proof validation should pass"
    );

    // 2. Re-evaluate trust with attestations
    let attestations = vec![
        Attestation {
            attestation_type: AttestationType::HardwareEnclave,
            format: "sgx_quote".to_string(),
            payload: "payload".to_string(),
            signature: "sig".to_string(),
            issuer: "intel".to_string(),
            issued_at: Utc::now(),
            valid_until: Utc::now() + Duration::hours(2),
        },
        Attestation {
            attestation_type: AttestationType::ModelIntegrity,
            format: "signed".to_string(),
            payload: "payload".to_string(),
            signature: "sig".to_string(),
            issuer: "anthropic".to_string(),
            issued_at: Utc::now(),
            valid_until: Utc::now() + Duration::hours(2),
        },
    ];

    let trust_result = reevaluate_trust(&attestations);
    assert!(trust_result.is_ok(), "Trust re-evaluation should pass");
    let (score, tier) = trust_result.unwrap();
    assert_eq!(score, 80);
    assert_eq!(tier, 2);

    // 3. Build attestations evaluation
    let attestations_eval = build_attestations_evaluation(&attestations, score);
    assert!(attestations_eval["hardware_enclave"]["passed"].as_bool().unwrap());
    assert!(attestations_eval["model_integrity"]["passed"].as_bool().unwrap());

    // 4. Check session token reuse
    let remaining_secs = 1800i64;
    let should_reuse = decide_session_token_reuse(remaining_secs, 600);
    assert!(should_reuse, "Session token should be reused");

    // 5. Build successful response
    let capability_token = CapabilityToken {
        token: "cap-token".to_string(),
        delegations: vec![],
        issued_at: Utc::now(),
        valid_until: Utc::now() + Duration::hours(24),
    };

    let evaluation = build_attestation_evaluation(
        score,
        Some(tier),
        attestations_eval,
        vec![],
        build_capability_changes(None, tier),
    );

    let response = build_success_response(should_reuse, None, capability_token, evaluation);

    match response {
        AttestationRefreshResponse::Success(success) => {
            assert_eq!(success.status, "refreshed");
            assert!(success.session_token_reused);
            assert_eq!(success.attestation_evaluation.score, 80);
            assert_eq!(success.attestation_evaluation.tier, Some(2));
        }
        _ => panic!("Expected success response"),
    }
}

#[test]
fn test_refresh_complete_flow_error_insufficient_attestations() {
    // Simulate a complete error flow: request -> validation -> re-evaluation -> error response

    // 1. Request validation passes
    let session_id = "sess-uuid-456";
    let nonce = "b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1";
    let timestamp = Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
    let proof_sig = "valid-proof";

    let validation_result = validate_refresh_proof(
        session_id,
        nonce,
        &timestamp,
        "[]",
        proof_sig,
        None,
    );
    assert!(validation_result.is_ok());

    // 2. Re-evaluate trust with insufficient attestations
    let attestations = vec![Attestation {
        attestation_type: AttestationType::RuntimeIntegrity, // Only 20 points
        format: "signed".to_string(),
        payload: "payload".to_string(),
        signature: "sig".to_string(),
        issuer: "runtime".to_string(),
        issued_at: Utc::now(),
        valid_until: Utc::now() + Duration::hours(1),
    }];

    let trust_result = reevaluate_trust(&attestations);
    assert!(
        trust_result.is_err(),
        "Trust re-evaluation should fail with insufficient score"
    );

    // 3. Build error response
    let response = build_error_response(
        "insufficient_trust".to_string(),
        "Score 20 < minimum 40 required for tier assignment".to_string(),
        vec![
            "Obtain additional attestations".to_string(),
            "Ensure hardware_enclave attestation is included".to_string(),
        ],
        None,
    );

    match response {
        AttestationRefreshResponse::Error(error) => {
            assert_eq!(error.status, "denied");
            assert_eq!(error.reason, "insufficient_trust");
            assert_eq!(error.remediation.len(), 2);
        }
        _ => panic!("Expected error response"),
    }
}
