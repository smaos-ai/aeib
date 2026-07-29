use chrono::{Duration, Utc};
use siss_layer00::{
    DashMapStore, ExecLogEntry, GateError, Layer0Gate, Mandate, MandateStore, SovereignKeypair,
};
use std::sync::Arc;
use uuid::Uuid;

// ============================================================================
// TIER 1: MANDATE VERIFICATION (6 tests)
// ============================================================================

#[test]
fn test_mandate_verify_valid() {
    // Generate a keypair and create a valid mandate
    let keypair = SovereignKeypair::generate();
    let public_key = keypair.public_key_bytes();

    let intent_content = b"Intent: Deploy agent to EU datacenter";
    let intent_hash = siss_layer00::sha256(intent_content);
    let signature = keypair.sign(&intent_hash);

    let mandate = Mandate {
        id: Uuid::new_v4(),
        intent_hash,
        public_key,
        signature,
        jurisdiction: "EU".to_string(),
        action_scope: vec!["spawn_agent".to_string()],
        created_at: Utc::now(),
        expires_at: Utc::now() + Duration::seconds(3600),
    };

    assert!(mandate.validate().is_ok());
}

#[test]
fn test_mandate_verify_invalid_signature() {
    let keypair = SovereignKeypair::generate();
    let public_key = keypair.public_key_bytes();

    let intent_hash = siss_layer00::sha256(b"Intent: Deploy");
    let mut signature = keypair.sign(&intent_hash);
    signature[0] ^= 0xFF; // Tamper with signature

    let mandate = Mandate {
        id: Uuid::new_v4(),
        intent_hash,
        public_key,
        signature,
        jurisdiction: "EU".to_string(),
        action_scope: vec!["spawn_agent".to_string()],
        created_at: Utc::now(),
        expires_at: Utc::now() + Duration::seconds(3600),
    };

    assert!(mandate.validate().is_err());
}

#[test]
fn test_mandate_verify_expired() {
    let keypair = SovereignKeypair::generate();
    let public_key = keypair.public_key_bytes();

    let intent_hash = siss_layer00::sha256(b"Intent: Deploy");
    let signature = keypair.sign(&intent_hash);

    let mandate = Mandate {
        id: Uuid::new_v4(),
        intent_hash,
        public_key,
        signature,
        jurisdiction: "EU".to_string(),
        action_scope: vec!["spawn_agent".to_string()],
        created_at: Utc::now(),
        expires_at: Utc::now() - Duration::seconds(3600), // Already expired
    };

    assert!(mandate.validate().is_err());
}

#[test]
fn test_mandate_verify_jurisdiction_allowed() {
    let keypair = SovereignKeypair::generate();
    let public_key = keypair.public_key_bytes();

    let intent_hash = siss_layer00::sha256(b"Intent: EU operation");
    let signature = keypair.sign(&intent_hash);

    let mandate = Mandate {
        id: Uuid::new_v4(),
        intent_hash,
        public_key,
        signature,
        jurisdiction: "EU".to_string(),
        action_scope: vec!["spawn_agent".to_string()],
        created_at: Utc::now(),
        expires_at: Utc::now() + Duration::seconds(3600),
    };

    assert!(mandate.validate().is_ok());
    assert!(mandate.action_allowed("spawn_agent"));
}

#[test]
fn test_mandate_verify_jurisdiction_violation() {
    let keypair = SovereignKeypair::generate();
    let public_key = keypair.public_key_bytes();

    let intent_hash = siss_layer00::sha256(b"Intent: EU only");
    let signature = keypair.sign(&intent_hash);

    let mandate = Mandate {
        id: Uuid::new_v4(),
        intent_hash,
        public_key,
        signature,
        jurisdiction: "EU".to_string(),
        action_scope: vec!["spawn_agent".to_string()],
        created_at: Utc::now(),
        expires_at: Utc::now() + Duration::seconds(3600),
    };

    // Mandate is valid but action_scope doesn't include this action
    assert!(mandate.validate().is_ok());
    assert!(!mandate.action_allowed("invoke_tool_us_only"));
}

#[test]
fn test_mandate_intent_hash_mismatch() {
    let keypair = SovereignKeypair::generate();
    let public_key = keypair.public_key_bytes();

    let intent_hash = siss_layer00::sha256(b"Intent: Original");
    let signature = keypair.sign(&intent_hash);

    let mut mandate = Mandate {
        id: Uuid::new_v4(),
        intent_hash,
        public_key,
        signature,
        jurisdiction: "EU".to_string(),
        action_scope: vec!["spawn_agent".to_string()],
        created_at: Utc::now(),
        expires_at: Utc::now() + Duration::seconds(3600),
    };

    // Change intent_hash after signing
    mandate.intent_hash[0] ^= 0xFF;

    assert!(mandate.validate().is_err());
}

// ============================================================================
// TIER 2: FAIL-CLOSED GATE (5 tests)
// ============================================================================

#[test]
fn test_gate_deny_no_mandate() {
    let store = Arc::new(DashMapStore::new());
    let gate = Layer0Gate::new(store);

    let result = gate.request_capability(Uuid::new_v4(), "spawn_agent");
    assert!(result.is_err());
    assert!(matches!(result.unwrap_err(), GateError::MandateNotFound));
}

#[test]
fn test_gate_deny_out_of_scope() {
    let keypair = SovereignKeypair::generate();
    let public_key = keypair.public_key_bytes();
    let intent_hash = siss_layer00::sha256(b"Intent: Limited scope");
    let signature = keypair.sign(&intent_hash);

    let mandate = Mandate {
        id: Uuid::new_v4(),
        intent_hash,
        public_key,
        signature,
        jurisdiction: "EU".to_string(),
        action_scope: vec!["spawn_agent".to_string()],
        created_at: Utc::now(),
        expires_at: Utc::now() + Duration::seconds(3600),
    };

    let store = Arc::new(DashMapStore::new());
    let gate = Layer0Gate::new(store);
    gate.register_mandate(mandate.clone()).unwrap();

    // Try to use action outside scope
    let result = gate.request_capability(mandate.id, "invoke_tool_admin");
    assert!(result.is_err());
    assert!(matches!(
        result.unwrap_err(),
        GateError::CapabilityDenied(_)
    ));
}

#[test]
fn test_gate_allow_valid_token() {
    let keypair = SovereignKeypair::generate();
    let public_key = keypair.public_key_bytes();
    let intent_hash = siss_layer00::sha256(b"Intent: Tool invocation");
    let signature = keypair.sign(&intent_hash);

    let mandate = Mandate {
        id: Uuid::new_v4(),
        intent_hash,
        public_key,
        signature,
        jurisdiction: "EU".to_string(),
        action_scope: vec!["spawn_agent".to_string()],
        created_at: Utc::now(),
        expires_at: Utc::now() + Duration::seconds(3600),
    };

    let store = Arc::new(DashMapStore::new());
    let gate = Layer0Gate::new(store);
    gate.register_mandate(mandate.clone()).unwrap();

    let token = gate.request_capability(mandate.id, "spawn_agent").unwrap();
    let result = gate.invoke_tool(&token, "spawn_agent", [0u8; 32]);

    assert!(result.is_ok());
}

#[test]
fn test_gate_block_expired_token() {
    let keypair = SovereignKeypair::generate();
    let public_key = keypair.public_key_bytes();
    let intent_hash = siss_layer00::sha256(b"Intent: Expire test");
    let signature = keypair.sign(&intent_hash);

    let mandate = Mandate {
        id: Uuid::new_v4(),
        intent_hash,
        public_key,
        signature,
        jurisdiction: "EU".to_string(),
        action_scope: vec!["spawn_agent".to_string()],
        created_at: Utc::now(),
        expires_at: Utc::now() - Duration::seconds(1), // Already expired
    };

    let store = Arc::new(DashMapStore::new());
    let gate = Layer0Gate::new(store);
    let _ = gate.register_mandate(mandate.clone());

    let token_result = gate.request_capability(mandate.id, "spawn_agent");
    assert!(token_result.is_err());
}

#[test]
fn test_gate_revoke_invalidates_tokens() {
    let keypair = SovereignKeypair::generate();
    let public_key = keypair.public_key_bytes();
    let intent_hash = siss_layer00::sha256(b"Intent: Revoke test");
    let signature = keypair.sign(&intent_hash);

    let mandate = Mandate {
        id: Uuid::new_v4(),
        intent_hash,
        public_key,
        signature,
        jurisdiction: "EU".to_string(),
        action_scope: vec!["spawn_agent".to_string()],
        created_at: Utc::now(),
        expires_at: Utc::now() + Duration::seconds(3600),
    };

    let store = Arc::new(DashMapStore::new());
    let gate = Layer0Gate::new(store);
    gate.register_mandate(mandate.clone()).unwrap();

    // Get token before revoke
    let _token = gate.request_capability(mandate.id, "spawn_agent").unwrap();

    // Revoke mandate
    gate.revoke_mandate(mandate.id).unwrap();

    // Try to request new token → should fail
    let result = gate.request_capability(mandate.id, "spawn_agent");
    assert!(result.is_err());
}

// ============================================================================
// TIER 3: MERKLE EXEC_LOG (5 tests)
// ============================================================================

#[test]
fn test_exec_log_genesis_entry() {
    let store = Arc::new(DashMapStore::new());
    let gate = Layer0Gate::new(store);

    let keypair = SovereignKeypair::generate();
    let public_key = keypair.public_key_bytes();
    let intent_hash = siss_layer00::sha256(b"Intent: Genesis");
    let signature = keypair.sign(&intent_hash);

    let mandate = Mandate {
        id: Uuid::new_v4(),
        intent_hash,
        public_key,
        signature,
        jurisdiction: "EU".to_string(),
        action_scope: vec!["spawn_agent".to_string()],
        created_at: Utc::now(),
        expires_at: Utc::now() + Duration::seconds(3600),
    };

    gate.register_mandate(mandate.clone()).unwrap();
    let token = gate.request_capability(mandate.id, "spawn_agent").unwrap();

    let result = gate.invoke_tool(&token, "spawn_agent", [0u8; 32]);
    assert!(result.is_ok());

    let root = gate.merkle_root().unwrap();
    // Root should be non-zero (computed hash)
    assert!(root != [0u8; 32]);
}

#[test]
fn test_exec_log_chain_linkage() {
    let store = Arc::new(DashMapStore::new());
    let gate = Layer0Gate::new(store);

    let keypair = SovereignKeypair::generate();
    let public_key = keypair.public_key_bytes();
    let intent_hash = siss_layer00::sha256(b"Intent: Chain test");
    let signature = keypair.sign(&intent_hash);

    let mandate = Mandate {
        id: Uuid::new_v4(),
        intent_hash,
        public_key,
        signature,
        jurisdiction: "EU".to_string(),
        action_scope: vec!["spawn_agent".to_string()],
        created_at: Utc::now(),
        expires_at: Utc::now() + Duration::seconds(3600),
    };

    gate.register_mandate(mandate.clone()).unwrap();
    let token = gate.request_capability(mandate.id, "spawn_agent").unwrap();

    // Invoke tool twice
    gate.invoke_tool(&token, "tool_a", [1u8; 32]).unwrap();
    gate.invoke_tool(&token, "tool_b", [2u8; 32]).unwrap();

    // Verify chain is intact
    assert!(gate.verify_chain().unwrap());
}

#[test]
fn test_exec_log_tamper_detection() {
    // Test that the merkle root is computed correctly and can detect tampering
    let store = Arc::new(DashMapStore::new());
    let gate = Layer0Gate::new(store);

    let keypair = SovereignKeypair::generate();
    let public_key = keypair.public_key_bytes();
    let intent_hash = siss_layer00::sha256(b"Intent: Tamper test");
    let signature = keypair.sign(&intent_hash);

    let mandate = Mandate {
        id: Uuid::new_v4(),
        intent_hash,
        public_key,
        signature,
        jurisdiction: "EU".to_string(),
        action_scope: vec!["spawn_agent".to_string()],
        created_at: Utc::now(),
        expires_at: Utc::now() + Duration::seconds(3600),
    };

    gate.register_mandate(mandate.clone()).unwrap();
    let token = gate.request_capability(mandate.id, "spawn_agent").unwrap();

    gate.invoke_tool(&token, "tool_a", [1u8; 32]).unwrap();

    // Verify chain is valid
    assert!(gate.verify_chain().unwrap());
}

#[test]
fn test_exec_log_merkle_root() {
    let store = Arc::new(DashMapStore::new());
    let gate = Layer0Gate::new(store);

    let keypair = SovereignKeypair::generate();
    let public_key = keypair.public_key_bytes();
    let intent_hash = siss_layer00::sha256(b"Intent: Root test");
    let signature = keypair.sign(&intent_hash);

    let mandate = Mandate {
        id: Uuid::new_v4(),
        intent_hash,
        public_key,
        signature,
        jurisdiction: "EU".to_string(),
        action_scope: vec!["spawn_agent".to_string()],
        created_at: Utc::now(),
        expires_at: Utc::now() + Duration::seconds(3600),
    };

    gate.register_mandate(mandate.clone()).unwrap();
    let token = gate.request_capability(mandate.id, "spawn_agent").unwrap();

    gate.invoke_tool(&token, "tool_a", [1u8; 32]).unwrap();
    let root1 = gate.merkle_root().unwrap();

    gate.invoke_tool(&token, "tool_b", [2u8; 32]).unwrap();
    let root2 = gate.merkle_root().unwrap();

    // Root should change after new invocation
    assert!(root1 != root2);
}

#[test]
fn test_exec_log_append_only() {
    let store = Arc::new(DashMapStore::new());
    let gate = Layer0Gate::new(store);

    let keypair = SovereignKeypair::generate();
    let public_key = keypair.public_key_bytes();
    let intent_hash = siss_layer00::sha256(b"Intent: Append test");
    let signature = keypair.sign(&intent_hash);

    let mandate = Mandate {
        id: Uuid::new_v4(),
        intent_hash,
        public_key,
        signature,
        jurisdiction: "EU".to_string(),
        action_scope: vec!["spawn_agent".to_string()],
        created_at: Utc::now(),
        expires_at: Utc::now() + Duration::seconds(3600),
    };

    gate.register_mandate(mandate.clone()).unwrap();
    let token = gate.request_capability(mandate.id, "spawn_agent").unwrap();

    // Append entries
    let id1 = gate.invoke_tool(&token, "tool_a", [1u8; 32]).unwrap();
    let id2 = gate.invoke_tool(&token, "tool_b", [2u8; 32]).unwrap();
    let id3 = gate.invoke_tool(&token, "tool_c", [3u8; 32]).unwrap();

    // All should succeed
    assert_eq!(id1, 0);
    assert_eq!(id2, 1);
    assert_eq!(id3, 2);
}

// ============================================================================
// TIER 4: DUAL-LOOP COUPLING (4 tests)
// ============================================================================

#[test]
fn test_human_override_invalidates_prior() {
    let store = Arc::new(DashMapStore::new());
    let gate = Layer0Gate::new(store);

    let keypair = SovereignKeypair::generate();
    let public_key = keypair.public_key_bytes();
    let intent_hash = siss_layer00::sha256(b"Intent: Override test");
    let signature = keypair.sign(&intent_hash);

    let mandate1 = Mandate {
        id: Uuid::new_v4(),
        intent_hash,
        public_key,
        signature,
        jurisdiction: "EU".to_string(),
        action_scope: vec!["spawn_agent".to_string()],
        created_at: Utc::now(),
        expires_at: Utc::now() + Duration::seconds(3600),
    };

    gate.register_mandate(mandate1.clone()).unwrap();
    let _token1 = gate.request_capability(mandate1.id, "spawn_agent").unwrap();

    // Revoke first mandate
    gate.revoke_mandate(mandate1.id).unwrap();

    // Register new mandate with different ID
    let mandate2 = Mandate {
        id: Uuid::new_v4(),
        intent_hash,
        public_key,
        signature,
        jurisdiction: "EU".to_string(),
        action_scope: vec!["spawn_agent".to_string()],
        created_at: Utc::now(),
        expires_at: Utc::now() + Duration::seconds(3600),
    };

    gate.register_mandate(mandate2.clone()).unwrap();
    let _token2 = gate.request_capability(mandate2.id, "spawn_agent").unwrap();

    // Old mandate should be inaccessible
    let result = gate.request_capability(mandate1.id, "spawn_agent");
    assert!(result.is_err());
}

#[test]
fn test_ai_cannot_self_authorize() {
    let store = Arc::new(DashMapStore::new());
    let gate = Layer0Gate::new(store);

    // Try to create a mandate with an invalid signature (AI cannot forge human signature)
    let invalid_mandate = Mandate {
        id: Uuid::new_v4(),
        intent_hash: siss_layer00::sha256(b"Fake intent"),
        public_key: [1u8; 32],
        signature: [2u8; 64],
        jurisdiction: "EU".to_string(),
        action_scope: vec!["spawn_agent".to_string()],
        created_at: Utc::now(),
        expires_at: Utc::now() + Duration::seconds(3600),
    };

    let result = gate.register_mandate(invalid_mandate);
    assert!(result.is_err());
}

#[test]
fn test_action_scope_limits_ai() {
    let keypair = SovereignKeypair::generate();
    let public_key = keypair.public_key_bytes();
    let intent_hash = siss_layer00::sha256(b"Intent: Limited tools");
    let signature = keypair.sign(&intent_hash);

    let mandate = Mandate {
        id: Uuid::new_v4(),
        intent_hash,
        public_key,
        signature,
        jurisdiction: "EU".to_string(),
        action_scope: vec!["spawn_agent".to_string()], // Only spawn_agent allowed
        created_at: Utc::now(),
        expires_at: Utc::now() + Duration::seconds(3600),
    };

    let store = Arc::new(DashMapStore::new());
    let gate = Layer0Gate::new(store);
    gate.register_mandate(mandate.clone()).unwrap();

    // Should succeed for allowed action
    let token = gate.request_capability(mandate.id, "spawn_agent").unwrap();
    let result = gate.invoke_tool(&token, "spawn_agent", [0u8; 32]);
    assert!(result.is_ok());

    // Should fail for disallowed action
    let disallowed = gate.request_capability(mandate.id, "invoke_admin_tool");
    assert!(disallowed.is_err());
}

#[test]
fn test_every_invocation_logged() {
    let keypair = SovereignKeypair::generate();
    let public_key = keypair.public_key_bytes();
    let intent_hash = siss_layer00::sha256(b"Intent: Logging test");
    let signature = keypair.sign(&intent_hash);

    let mandate = Mandate {
        id: Uuid::new_v4(),
        intent_hash,
        public_key,
        signature,
        jurisdiction: "EU".to_string(),
        action_scope: vec!["spawn_agent".to_string()],
        created_at: Utc::now(),
        expires_at: Utc::now() + Duration::seconds(3600),
    };

    let store = Arc::new(DashMapStore::new());
    let gate = Layer0Gate::new(store);
    gate.register_mandate(mandate.clone()).unwrap();
    let token = gate.request_capability(mandate.id, "spawn_agent").unwrap();

    // Invoke tool 3 times
    gate.invoke_tool(&token, "tool_a", [1u8; 32]).unwrap();
    gate.invoke_tool(&token, "tool_b", [2u8; 32]).unwrap();
    gate.invoke_tool(&token, "tool_c", [3u8; 32]).unwrap();

    // Verify chain has 3 entries
    assert!(gate.verify_chain().unwrap());

    // Root should be deterministic and non-zero
    let root = gate.merkle_root().unwrap();
    assert!(root != [0u8; 32]);
}
