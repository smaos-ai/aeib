use ed25519_dalek::{Signer, SigningKey};
use siss_agent_shell::a2a_dispatcher::{
    A2ADispatcher, A2AStreamEvent, DispatchError, JsonRpcError, JsonRpcRequest, JsonRpcResponse,
};
/// Phase 58: Federated Guild Network — ANP Registry, A2A Dispatcher, CRDT Sync (27 RED tests)
use siss_agent_shell::anp_registry::{AnpError, AnpRegistry};
use siss_agent_shell::crdt_sync::{CrdtSync, ProvenanceFork};
use siss_agent_shell::swarm_knowledge::KnowledgeAtom;
use siss_gatekeeper::tokens::IntentMandate;
use uuid::Uuid;

// ─── ANP REGISTRY TESTS (1–9) ──────────────────────────────

#[tokio::test]
async fn test_anp_register_peer_valid_did() {
    let registry = AnpRegistry::new();
    let mut rng = rand::thread_rng();
    let signing_key = SigningKey::generate(&mut rng);
    let public_key = signing_key.verifying_key().to_bytes();

    let did = format!("did:sovereign:{}", Uuid::new_v4());
    let result = registry
        .register_peer(
            &did,
            "https://factory.local",
            vec!["task/run".to_string()],
            public_key,
        )
        .await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_anp_register_rejects_invalid_did() {
    let registry = AnpRegistry::new();
    let mut rng = rand::thread_rng();
    let signing_key = SigningKey::generate(&mut rng);
    let public_key = signing_key.verifying_key().to_bytes();

    let result = registry
        .register_peer(
            "not-a-valid-did",
            "https://factory.local",
            vec![],
            public_key,
        )
        .await;
    assert!(matches!(result, Err(AnpError::InvalidDidFormat(_))));
}

#[tokio::test]
async fn test_anp_authenticate_valid_signature() {
    let registry = AnpRegistry::new();
    let mut rng = rand::thread_rng();
    let signing_key = SigningKey::generate(&mut rng);
    let public_key = signing_key.verifying_key().to_bytes();

    let did = format!("did:sovereign:{}", Uuid::new_v4());
    let _ = registry
        .register_peer(&did, "https://factory.local", vec![], public_key)
        .await
        .unwrap();

    let payload = b"test payload";
    let signature = signing_key.sign(payload);
    let sig_bytes: [u8; 64] = signature.to_bytes();

    let result = registry.authenticate_peer(&did, payload, &sig_bytes).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_anp_authenticate_invalid_signature() {
    let registry = AnpRegistry::new();
    let mut rng = rand::thread_rng();
    let signing_key = SigningKey::generate(&mut rng);
    let public_key = signing_key.verifying_key().to_bytes();

    let did = format!("did:sovereign:{}", Uuid::new_v4());
    let _ = registry
        .register_peer(&did, "https://factory.local", vec![], public_key)
        .await
        .unwrap();

    let payload = b"test payload";
    let mut bad_sig = [0u8; 64];
    bad_sig[0] = 0xFF;

    let result = registry.authenticate_peer(&did, payload, &bad_sig).await;
    assert_eq!(
        result,
        Err(AnpError::UnauthorizedPeer {
            reason: "invalid_signature".to_string()
        })
    );
}

#[tokio::test]
async fn test_anp_authenticate_unregistered_peer() {
    let registry = AnpRegistry::new();
    let did = format!("did:sovereign:{}", Uuid::new_v4());
    let payload = b"test";
    let sig = [0u8; 64];

    let result = registry.authenticate_peer(&did, payload, &sig).await;
    assert_eq!(
        result,
        Err(AnpError::UnauthorizedPeer {
            reason: "peer_not_registered".to_string()
        })
    );
}

#[tokio::test]
async fn test_anp_lookup_finds_registered_peer() {
    let registry = AnpRegistry::new();
    let mut rng = rand::thread_rng();
    let signing_key = SigningKey::generate(&mut rng);
    let public_key = signing_key.verifying_key().to_bytes();

    let did = format!("did:sovereign:{}", Uuid::new_v4());
    let _ = registry
        .register_peer(&did, "https://factory.local", vec![], public_key)
        .await
        .unwrap();

    let result = registry.lookup_by_did(&did).await;
    assert!(result.is_some());
}

#[tokio::test]
async fn test_anp_lookup_unknown_returns_none() {
    let registry = AnpRegistry::new();
    let did = format!("did:sovereign:{}", Uuid::new_v4());

    let result = registry.lookup_by_did(&did).await;
    assert!(result.is_none());
}

#[tokio::test]
async fn test_anp_deregister_removes_peer() {
    let registry = AnpRegistry::new();
    let mut rng = rand::thread_rng();
    let signing_key = SigningKey::generate(&mut rng);
    let public_key = signing_key.verifying_key().to_bytes();

    let did = format!("did:sovereign:{}", Uuid::new_v4());
    let peer_id = registry
        .register_peer(&did, "https://factory.local", vec![], public_key)
        .await
        .unwrap();
    let _ = registry.deregister_peer(peer_id).await.unwrap();

    let result = registry.lookup_by_did(&did).await;
    assert!(result.is_none());
}

#[tokio::test]
async fn test_anp_duplicate_did_rejected() {
    let registry = AnpRegistry::new();
    let mut rng = rand::thread_rng();
    let signing_key = SigningKey::generate(&mut rng);
    let public_key = signing_key.verifying_key().to_bytes();

    let did = format!("did:sovereign:{}", Uuid::new_v4());
    let _ = registry
        .register_peer(&did, "https://factory.local", vec![], public_key)
        .await
        .unwrap();

    let result = registry
        .register_peer(&did, "https://other.local", vec![], public_key)
        .await;
    assert!(matches!(result, Err(AnpError::AlreadyRegistered(_))));
}

// ─── A2A DISPATCHER TESTS (10–18) ──────────────────────────

#[test]
fn test_json_rpc_request_version_is_2_0() {
    let req = A2ADispatcher::build_request("task/run", serde_json::json!({}));
    assert_eq!(req.jsonrpc, "2.0");
}

#[test]
fn test_json_rpc_request_serializes_correctly() {
    let req = A2ADispatcher::build_request("test", serde_json::json!({}));
    let json = serde_json::to_string(&req).unwrap();
    assert!(json.contains("\"jsonrpc\":\"2.0\""));
}

#[test]
fn test_json_rpc_response_deserializes_result() {
    let json =
        r#"{"jsonrpc":"2.0","id":"550e8400-e29b-41d4-a716-446655440000","result":{"foo":"bar"}}"#;
    let response: JsonRpcResponse = serde_json::from_str(json).unwrap();
    assert!(response.result.is_some());
}

#[test]
fn test_json_rpc_response_deserializes_error() {
    let json = r#"{"jsonrpc":"2.0","id":"550e8400-e29b-41d4-a716-446655440000","error":{"code":-32601,"message":"not found"}}"#;
    let response: JsonRpcResponse = serde_json::from_str(json).unwrap();
    assert!(response.error.is_some());
    assert!(response.result.is_none());
}

#[test]
fn test_dispatch_rejects_missing_mandate() {
    let result = A2ADispatcher::validate_dispatch(None, 100);
    assert_eq!(result, Err(DispatchError::MandateRequired));
}

#[test]
fn test_dispatch_rejects_insufficient_budget() {
    let mandate = IntentMandate {
        id: Uuid::new_v4(),
        budget_limit: 100,
        budget_spent: 50,
        risk_class: "LOW".to_string(),
        allowed_tools: vec![],
    };
    let result = A2ADispatcher::validate_dispatch(Some(&mandate), 100);
    assert_eq!(
        result,
        Err(DispatchError::InsufficientBudget {
            required: 100,
            available: 50
        })
    );
}

#[test]
fn test_dispatch_accepts_sufficient_budget() {
    let mandate = IntentMandate {
        id: Uuid::new_v4(),
        budget_limit: 500,
        budget_spent: 0,
        risk_class: "LOW".to_string(),
        allowed_tools: vec![],
    };
    let result = A2ADispatcher::validate_dispatch(Some(&mandate), 100);
    assert!(result.is_ok());
}

#[test]
fn test_sse_parse_skips_keep_alive() {
    let result = A2ADispatcher::parse_sse_line(": keep-alive");
    assert_eq!(result, None);
}

#[test]
fn test_sse_parse_done_event() {
    let result = A2ADispatcher::parse_sse_line("data: done");
    assert_eq!(result, Some(A2AStreamEvent::Done));
}

// ─── CRDT SYNC TESTS (19–27) ──────────────────────────────

#[test]
fn test_crdt_merge_identical_atoms_no_fork() {
    let atom_a = create_test_atom("same content", 5);
    let atom_b = create_test_atom("same content", 3);

    let result = CrdtSync::merge(atom_a, Uuid::new_v4(), atom_b, Uuid::new_v4());
    assert!(result.fork.is_none());
    assert_eq!(result.merged.reinforcement_count, 5);
}

#[test]
fn test_crdt_merge_different_content_creates_fork() {
    let atom_a = create_test_atom("content A", 5);
    let atom_b = create_test_atom("content B", 3);

    let result = CrdtSync::merge(atom_a, Uuid::new_v4(), atom_b, Uuid::new_v4());
    assert!(result.fork.is_some());
}

#[test]
fn test_crdt_merge_lww_later_wins() {
    let atom_a = create_test_atom("A content", 5);
    let mut atom_b = create_test_atom("B content", 3);
    atom_b.discovered_at = atom_a.discovered_at + chrono::Duration::seconds(1);

    let result = CrdtSync::merge(
        atom_a.clone(),
        Uuid::new_v4(),
        atom_b.clone(),
        Uuid::new_v4(),
    );
    assert_eq!(result.merged.content, atom_b.content);
}

#[test]
fn test_crdt_merge_lww_earlier_loses() {
    let mut atom_a = create_test_atom("A content", 5);
    let atom_b = create_test_atom("B content", 3);
    atom_a.discovered_at = atom_b.discovered_at + chrono::Duration::seconds(1);

    let result = CrdtSync::merge(
        atom_a.clone(),
        Uuid::new_v4(),
        atom_b.clone(),
        Uuid::new_v4(),
    );
    assert_eq!(result.merged.content, atom_a.content);
}

#[test]
fn test_crdt_merge_empty_content_never_wins() {
    let mut atom_a = create_test_atom("", 5);
    let atom_b = create_test_atom("valid content", 3);
    atom_a.discovered_at = atom_b.discovered_at + chrono::Duration::seconds(1);

    let result = CrdtSync::merge(atom_a, Uuid::new_v4(), atom_b.clone(), Uuid::new_v4());
    assert_eq!(result.merged.content, atom_b.content);
}

#[test]
fn test_crdt_merge_g_counter_takes_max() {
    let atom_a = create_test_atom("same content", 3);
    let atom_b = create_test_atom("same content", 7);

    let result = CrdtSync::merge(atom_a, Uuid::new_v4(), atom_b, Uuid::new_v4());
    assert_eq!(result.merged.reinforcement_count, 7);
}

#[test]
fn test_crdt_fork_preserves_both_hashes() {
    let atom_a = create_test_atom("A content", 5);
    let atom_b = create_test_atom("B content", 3);

    let result = CrdtSync::merge(atom_a, Uuid::new_v4(), atom_b, Uuid::new_v4());
    if let Some(fork) = result.fork {
        assert_ne!(fork.actor_a_hash, fork.actor_b_hash);
        assert!(!fork.actor_a_hash.is_empty());
        assert!(!fork.actor_b_hash.is_empty());
    } else {
        panic!("expected fork");
    }
}

#[test]
fn test_crdt_fork_unresolved_by_default() {
    let atom_a = create_test_atom("A content", 5);
    let atom_b = create_test_atom("B content", 3);

    let result = CrdtSync::merge(atom_a, Uuid::new_v4(), atom_b, Uuid::new_v4());
    if let Some(fork) = result.fork {
        assert!(!fork.resolved);
    } else {
        panic!("expected fork");
    }
}

#[test]
fn test_crdt_merge_commutative() {
    let atom_a = create_test_atom("A content", 5);
    let atom_b = create_test_atom("B content", 3);
    let fa = Uuid::new_v4();
    let fb = Uuid::new_v4();

    let result1 = CrdtSync::merge(atom_a.clone(), fa, atom_b.clone(), fb);
    let result2 = CrdtSync::merge(atom_b, fb, atom_a, fa);

    assert_eq!(result1.merged.content, result2.merged.content);
}

// ─── HELPER FUNCTIONS ──────────────────────────────────────

fn create_test_atom(content: &str, count: u32) -> KnowledgeAtom {
    use std::collections::hash_map::DefaultHasher;
    use std::hash::{Hash, Hasher};

    let mut hasher = DefaultHasher::new();
    content.hash(&mut hasher);
    let hash_value = hasher.finish();

    KnowledgeAtom {
        atom_id: Uuid::new_v4(),
        kind: siss_agent_shell::swarm_knowledge::KnowledgeKind::ArchitecturalPattern,
        source_worktree: "test".to_string(),
        symbol_path: "test::symbol".to_string(),
        content: content.to_string(),
        confidence: 0.8,
        provenance_hash: format!("{:x}", hash_value),
        reinforcement_count: count,
        discovered_at: chrono::Utc::now(),
    }
}
