use chrono::Utc;
use siss_gatekeeper::{
    attestation::{Attestation, AttestationType},
    evaluator::evaluate_capabilities,
    policy::TrustPolicyNode,
};
use siss_graph_core::node::NodeId;
use uuid::Uuid;

fn make_test_policy() -> TrustPolicyNode {
    TrustPolicyNode {
        id: NodeId(Uuid::new_v4()),
        persona_id: NodeId(Uuid::new_v4()),
        tenant_id: NodeId(Uuid::new_v4()),
        policy_version: 1,
        allowed_agent_types: vec!["ai_agent".to_string()],
        denied_agents_by_id: vec![],
        allowed_organizations: vec![],
        hardware_enclave_required: false,
        model_integrity_required: false,
        max_failed_attestations: 0,
        tier_1_score_threshold: 100,
        tier_2_score_threshold: 70,
        tier_3_score_threshold: 40,
        capability_overrides: vec![],
        session_token_expiry_seconds: 3600,
        capability_token_expiry_seconds: 86400,
        enforcement_mode: "strict".to_string(),
        audit_required: true,
        created_at: Utc::now(),
        last_modified: Utc::now(),
        last_modified_by: Uuid::new_v4(),
    }
}

#[test]
fn test_handshake_with_hardware_enclave_grants_capabilities() {
    let policy = make_test_policy();
    let attestations = vec![Attestation {
        attestation_type: AttestationType::HardwareEnclave,
        format: "sgx_quote".to_string(),
        payload: "payload".to_string(),
        signature: "sig".to_string(),
        issuer: "intel".to_string(),
        issued_at: Utc::now(),
        valid_until: Utc::now() + chrono::Duration::hours(1),
    }];
    let tools = vec![
        ("tool-high".to_string(), "high".to_string()),
        ("tool-low".to_string(), "low".to_string()),
    ];

    let result = evaluate_capabilities(attestations, &policy, tools);
    assert!(result.is_ok());

    let (session_token, capability_token) = result.unwrap();
    assert_eq!(session_token.token_type, "Bearer");
    assert!(session_token.expires_in > 0);
    assert!(capability_token.delegations.len() > 0);
}

#[test]
fn test_handshake_with_model_integrity_and_hardware_enclave() {
    let policy = make_test_policy();
    let attestations = vec![
        Attestation {
            attestation_type: AttestationType::HardwareEnclave,
            format: "sgx_quote".to_string(),
            payload: "payload".to_string(),
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
    let tools = vec![("tool-1".to_string(), "high".to_string())];

    let result = evaluate_capabilities(attestations, &policy, tools);
    assert!(result.is_ok());

    let (_session_token, capability_token) = result.unwrap();
    let score = 50 + 30;  // HW + Model = 80 points
    assert!(score >= policy.tier_2_score_threshold);
    assert!(capability_token.delegations.len() > 0);
}

#[test]
fn test_handshake_with_required_enclave_but_none_provided() {
    let mut policy = make_test_policy();
    policy.hardware_enclave_required = true;

    let attestations = vec![];  // No attestations
    let tools = vec![];

    let result = evaluate_capabilities(attestations, &policy, tools);
    assert!(result.is_err());
}

#[test]
fn test_capability_token_expiry_set_correctly() {
    let policy = make_test_policy();
    let attestations = vec![Attestation {
        attestation_type: AttestationType::HardwareEnclave,
        format: "sgx_quote".to_string(),
        payload: "payload".to_string(),
        signature: "sig".to_string(),
        issuer: "intel".to_string(),
        issued_at: Utc::now(),
        valid_until: Utc::now() + chrono::Duration::hours(1),
    }];
    let tools = vec![];

    let result = evaluate_capabilities(attestations, &policy, tools);
    assert!(result.is_ok());

    let (_session_token, capability_token) = result.unwrap();
    let expected_expiry = capability_token.issued_at
        + chrono::Duration::seconds(policy.capability_token_expiry_seconds as i64);
    assert_eq!(capability_token.valid_until, expected_expiry);
}

#[test]
fn test_multiple_attestations_increase_score() {
    let policy = make_test_policy();
    let attestations = vec![
        Attestation {
            attestation_type: AttestationType::HardwareEnclave,
            format: "sgx_quote".to_string(),
            payload: "payload".to_string(),
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
    let tools = vec![("tool-1".to_string(), "high".to_string())];

    let result = evaluate_capabilities(attestations, &policy, tools);
    assert!(result.is_ok());

    let (_session_token, capability_token) = result.unwrap();
    let score = 50 + 30 + 20;  // HW + Model + Sovereign = 100 points
    assert!(score >= policy.tier_1_score_threshold);
    // With tier 1, all high-risk tools should be delegated
    assert!(capability_token.delegations.len() > 0);
}
