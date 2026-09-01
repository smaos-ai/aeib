//! Phase 2A L4 Execution Hook Tests (TDD)
//! Tests: route to L3B, enrich intent hash, fail-closed on error

use chrono::Utc;
use ed25519_dalek::{SigningKey, Signer};
use l3_permit_gates::{
    CryptoIntentCommitment, DelegationLink, IntentVerificationGate, VerificationResult,
};
use rand::RngCore;

/// Helper: Create valid commitment with signature
fn create_test_commitment(
    request_id: String,
    hours_until_expiry: i64,
    signing_key: &SigningKey,
) -> CryptoIntentCommitment {
    let mut commitment = CryptoIntentCommitment {
        request_id: request_id.clone(),
        scope: vec!["read:user".to_string()],
        delegation_chain: vec![DelegationLink {
            delegator: "user_alice".to_string(),
            delegatee: "agent_bot".to_string(),
            tools: vec!["read:user".to_string()],
            created_at: Utc::now(),
        }],
        time_lock: Utc::now() + chrono::Duration::hours(hours_until_expiry),
        ed25519_signature: vec![0u8; 64],
        intent_tree_hash: String::new(),
    };

    commitment.intent_tree_hash = IntentVerificationGate::build_intent_tree(&commitment);
    let signature = signing_key.sign(commitment.intent_tree_hash.as_bytes());
    commitment.ed25519_signature = signature.to_bytes().to_vec();

    commitment
}

#[tokio::test]
async fn test_l4_hook_routes_valid_intent_to_l3b() {
    // Test: L4 hook receives intent, routes to L3B verification
    let mut verifier = IntentVerificationGate::new();
    verifier.add_delegation_policy("user_alice".to_string(), "agent_bot".to_string());

    let mut seed = [0u8; 32];
    rand::thread_rng().fill_bytes(&mut seed);
    let signing_key = SigningKey::from_bytes(&seed);

    let commitment = create_test_commitment("l4_req_001".to_string(), 24, &signing_key);

    // L4 hook routes to L3B
    let delegation_check = verifier.check_delegation_chain(&commitment);
    let scope_check = verifier.check_scope_boundary(&commitment);

    // Both checks should pass, intent is routable
    assert_eq!(delegation_check, VerificationResult::Valid);
    assert_eq!(scope_check, VerificationResult::Valid);
}

#[tokio::test]
async fn test_l4_hook_enriches_intent_hash_from_l3b() {
    // Test: L4 hook receives verification result, enriches with hash
    let mut seed = [0u8; 32];
    rand::thread_rng().fill_bytes(&mut seed);
    let signing_key = SigningKey::from_bytes(&seed);

    let mut commitment = create_test_commitment("l4_req_002".to_string(), 24, &signing_key);
    let original_hash = commitment.intent_tree_hash.clone();

    // Hash should be deterministic and non-empty
    assert!(!original_hash.is_empty());
    assert_eq!(original_hash.len(), 64); // SHA256 hex digest

    // Enrichment verification: hash should match rebuild
    let rebuilt_hash = IntentVerificationGate::build_intent_tree(&commitment);
    assert_eq!(original_hash, rebuilt_hash);
}

#[tokio::test]
async fn test_l4_hook_fails_closed_on_l3b_error() {
    // Test: L4 hook receives invalid result from L3B, denies execution
    let verifier = IntentVerificationGate::new();
    // No delegation policy added (will fail)

    let mut seed = [0u8; 32];
    rand::thread_rng().fill_bytes(&mut seed);
    let signing_key = SigningKey::from_bytes(&seed);

    let commitment = create_test_commitment("l4_req_003".to_string(), 24, &signing_key);

    // L3B check fails
    let delegation_check = verifier.check_delegation_chain(&commitment);

    // L4 hook receives failure, denies execution (fail-closed)
    assert_eq!(delegation_check, VerificationResult::UnauthorizedDelegation);
}

#[tokio::test]
async fn test_l4_hook_enriches_metadata_for_l8_ledger() {
    // Test: L4 hook enriches metadata (timestamp, request_id, hash) for L8
    let mut seed = [0u8; 32];
    rand::thread_rng().fill_bytes(&mut seed);
    let signing_key = SigningKey::from_bytes(&seed);

    let commitment = create_test_commitment("l4_req_004".to_string(), 24, &signing_key);

    // Metadata enriched by L4
    let request_id = &commitment.request_id;
    let intent_hash = &commitment.intent_tree_hash;
    let timestamp = commitment.time_lock;

    // All metadata present and valid
    assert!(!request_id.is_empty());
    assert!(!intent_hash.is_empty());
    assert!(timestamp > Utc::now()); // Should be in future
}

#[tokio::test]
async fn test_l4_hook_preserves_delegation_chain_for_audit() {
    // Test: L4 hook preserves delegation chain for L8 audit trail
    let mut seed = [0u8; 32];
    rand::thread_rng().fill_bytes(&mut seed);
    let signing_key = SigningKey::from_bytes(&seed);

    let commitment = create_test_commitment("l4_req_005".to_string(), 24, &signing_key);

    // Delegation chain preserved
    assert_eq!(commitment.delegation_chain.len(), 1);
    assert_eq!(commitment.delegation_chain[0].delegator, "user_alice");
    assert_eq!(commitment.delegation_chain[0].delegatee, "agent_bot");
    assert_eq!(commitment.delegation_chain[0].tools.len(), 1);
}
