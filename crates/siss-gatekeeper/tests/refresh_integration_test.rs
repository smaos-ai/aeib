use chrono::Utc;
use siss_gatekeeper::refresh::*;
use siss_gatekeeper::attestation::{Attestation, AttestationType};

/// Helper function to evaluate attestations and compute trust score and tier
fn reevaluate_trust(attestations: &[Attestation]) -> Result<(u32, u32), String> {
    let mut total_score = 0u32;

    for attestation in attestations {
        match attestation.attestation_type {
            AttestationType::HardwareEnclave => total_score += 50,
            AttestationType::ModelIntegrity => total_score += 30,
            AttestationType::SovereignOrigin => total_score += 20,
            AttestationType::RuntimeIntegrity => total_score += 15,
        }
    }

    let tier = if total_score >= 100 {
        1
    } else if total_score >= 70 {
        2
    } else if total_score >= 40 {
        3
    } else {
        return Err("insufficient_security_score".to_string());
    };

    Ok((total_score, tier))
}

#[test]
fn test_full_refresh_flow() {
    let attestations = vec![
        Attestation {
            attestation_type: AttestationType::HardwareEnclave,
            format: "sgx_quote".to_string(),
            payload: "test".to_string(),
            signature: "sig".to_string(),
            issuer: "intel".to_string(),
            issued_at: Utc::now(),
            valid_until: Utc::now() + chrono::Duration::hours(1),
        },
    ];

    let (score, tier) = reevaluate_trust(&attestations).unwrap();
    assert_eq!(score, 50);
    assert_eq!(tier, 3);
}

#[test]
fn test_refresh_proof_validation() {
    let now = Utc::now();
    let timestamp_str = now.to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
    let result = validate_refresh_proof(
        "session-123",
        "a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0",
        &timestamp_str,
        "[]",
        "test-sig",
        None,
    );
    assert!(result.is_ok());
}

#[test]
fn test_error_responses() {
    let err = error_signature_invalid();
    match err {
        AttestationRefreshResponse::Error(e) => {
            assert_eq!(e.reason, "signature_invalid");
            assert!(!e.remediation.is_empty());
        }
        _ => panic!(),
    }
}

#[test]
fn test_multiple_attestations_increase_score() {
    let attestations = vec![
        Attestation {
            attestation_type: AttestationType::HardwareEnclave,
            format: "sgx_quote".to_string(),
            payload: "test".to_string(),
            signature: "sig".to_string(),
            issuer: "intel".to_string(),
            issued_at: Utc::now(),
            valid_until: Utc::now() + chrono::Duration::hours(1),
        },
        Attestation {
            attestation_type: AttestationType::ModelIntegrity,
            format: "signed_manifest".to_string(),
            payload: "manifest".to_string(),
            signature: "sig2".to_string(),
            issuer: "anthropic".to_string(),
            issued_at: Utc::now(),
            valid_until: Utc::now() + chrono::Duration::days(30),
        },
    ];

    let (score, tier) = reevaluate_trust(&attestations).unwrap();
    assert_eq!(score, 80);
    assert_eq!(tier, 2);
}

#[test]
fn test_three_attestations_reach_tier_1() {
    let attestations = vec![
        Attestation {
            attestation_type: AttestationType::HardwareEnclave,
            format: "sgx_quote".to_string(),
            payload: "test".to_string(),
            signature: "sig".to_string(),
            issuer: "intel".to_string(),
            issued_at: Utc::now(),
            valid_until: Utc::now() + chrono::Duration::hours(1),
        },
        Attestation {
            attestation_type: AttestationType::ModelIntegrity,
            format: "signed_manifest".to_string(),
            payload: "manifest".to_string(),
            signature: "sig2".to_string(),
            issuer: "anthropic".to_string(),
            issued_at: Utc::now(),
            valid_until: Utc::now() + chrono::Duration::days(30),
        },
        Attestation {
            attestation_type: AttestationType::SovereignOrigin,
            format: "jurisdiction_cert".to_string(),
            payload: "us_cert".to_string(),
            signature: "sig3".to_string(),
            issuer: "us-deployer".to_string(),
            issued_at: Utc::now(),
            valid_until: Utc::now() + chrono::Duration::days(7),
        },
    ];

    let (score, tier) = reevaluate_trust(&attestations).unwrap();
    assert_eq!(score, 100);
    assert_eq!(tier, 1);
}

#[test]
fn test_insufficient_score_error() {
    let attestations = vec![];

    let result = reevaluate_trust(&attestations);
    assert!(result.is_err());
    assert_eq!(result.unwrap_err(), "insufficient_security_score");
}

#[test]
fn test_build_success_response() {
    let capability_token = siss_gatekeeper::tokens::CapabilityToken {
        token: "test_capability_token".to_string(),
        delegations: vec![],
        issued_at: Utc::now(),
        valid_until: Utc::now() + chrono::Duration::hours(1),
    };

    let evaluation = build_attestation_evaluation(
        80,
        Some(2),
        serde_json::json!({"hardware_enclave": {"passed": true}}),
        vec![],
        serde_json::json!({}),
    );

    let response = build_success_response(true, None, capability_token, evaluation);

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
fn test_error_session_token_expired_response() {
    let expired_at = Utc::now() - chrono::Duration::hours(1);
    let response = error_session_token_expired(expired_at);

    match response {
        AttestationRefreshResponse::Error(e) => {
            assert_eq!(e.reason, "session_token_expired");
            assert_eq!(e.status, "denied");
            assert!(!e.remediation.is_empty());
        }
        _ => panic!("Expected error response"),
    }
}

#[test]
fn test_error_attestation_validation_failed_response() {
    let response = error_attestation_validation_failed("Hardware enclave validation failed".to_string());

    match response {
        AttestationRefreshResponse::Error(e) => {
            assert_eq!(e.reason, "attestation_validation_failed");
            assert_eq!(e.status, "denied");
            assert!(e.detail.contains("Hardware enclave validation failed"));
            assert!(!e.remediation.is_empty());
        }
        _ => panic!("Expected error response"),
    }
}

#[test]
fn test_error_hard_requirement_failed_response() {
    let response = error_hard_requirement_failed("hardware_enclave".to_string());

    match response {
        AttestationRefreshResponse::Error(e) => {
            assert_eq!(e.reason, "hard_requirement_failed");
            assert_eq!(e.status, "denied");
            assert!(e.detail.contains("hardware_enclave"));
            assert!(!e.remediation.is_empty());
        }
        _ => panic!("Expected error response"),
    }
}

#[test]
fn test_validate_refresh_proof_with_old_timestamp() {
    let old_timestamp = (Utc::now() - chrono::Duration::minutes(10))
        .to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
    let result = validate_refresh_proof(
        "session-123",
        "a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0",
        &old_timestamp,
        "[]",
        "test-sig",
        None,
    );
    assert!(result.is_err());
}

#[test]
fn test_validate_refresh_proof_with_empty_signature() {
    let now = Utc::now();
    let timestamp_str = now.to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
    let result = validate_refresh_proof(
        "session-123",
        "a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0",
        &timestamp_str,
        "[]",
        "",
        None,
    );
    assert!(result.is_err());
}

#[test]
fn test_decide_session_token_reuse() {
    // Token with 30 minutes remaining should be reused when threshold is 10 minutes
    assert!(decide_session_token_reuse(1800, 600));

    // Token with 5 minutes remaining should NOT be reused when threshold is 10 minutes
    assert!(!decide_session_token_reuse(300, 600));

    // Token with exactly threshold remaining should NOT be reused (boundary: > not >=)
    assert!(!decide_session_token_reuse(600, 600));

    // Token with 601 sec remaining should be reused when threshold is 600 sec
    assert!(decide_session_token_reuse(601, 600));
}

#[test]
fn test_compute_capability_token_expiry_max_ttl_sooner() {
    let now = Utc::now();
    let max_ttl = 3600u64;
    let attestation_expiry = now + chrono::Duration::hours(2);

    let expiry = compute_capability_token_expiry(max_ttl, attestation_expiry);

    let expected_expiry = now + chrono::Duration::seconds(max_ttl as i64);
    let diff = (expiry - expected_expiry).num_seconds().abs();
    assert!(diff < 2);
}

#[test]
fn test_compute_capability_token_expiry_attestation_sooner() {
    let now = Utc::now();
    let max_ttl = 7200u64;
    let attestation_expiry = now + chrono::Duration::minutes(30);

    let expiry = compute_capability_token_expiry(max_ttl, attestation_expiry);

    let diff = (expiry - attestation_expiry).num_seconds().abs();
    assert!(diff < 1);
}
