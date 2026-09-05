use demo_app::models::{MemoryTier, MemoryWrite};
use demo_app::orchestration::{Agent, L2SemanticNode, MemoryQuery, OrchestrationError};
use std::path::PathBuf;

#[test]
fn test_ap2_rejection_missing_operator_signature() {
    let memory_write = MemoryWrite {
        memory_type: MemoryTier::L2Semantic,
        task_id: "doc-001".to_string(),
        raw_span: "[Phi-Compressed]: Entity X mentioned in context Y".to_string(),
        structured_fields: std::collections::HashMap::new(),
        operator_signature: None, // CRITICAL: Missing AP2 signature
    };

    // Attempt to commit to L2 without cryptographic proof
    let result = Agent::validate_and_commit(&memory_write);

    // Must be Err because operator_signature is None
    assert!(
        result.is_err(),
        "L2Semantic write must be rejected without AP2 operator_signature"
    );
    assert_eq!(
        result.unwrap_err(),
        OrchestrationError::MissingOperatorSignature
    );
}

#[test]
fn test_ap2_rejection_nonce_already_burned() {
    let mut memory_write = MemoryWrite {
        memory_type: MemoryTier::L2Semantic,
        task_id: "doc-002".to_string(),
        raw_span: "[Phi-Compressed]: Critical intelligence summary".to_string(),
        structured_fields: std::collections::HashMap::new(),
        operator_signature: Some("ed25519_sig_abc123".to_string()),
    };

    // First write: nonce "burn-001" is burned
    memory_write
        .structured_fields
        .insert("nonce".to_string(), "burn-001".to_string());

    let agent = Agent::new(
        "alpha".to_string(),
        PathBuf::from("/worktrees/alpha"),
        "sqlite:///var/lib/smaos/memory.db".to_string(),
    );

    let result1 = agent.commit_l2_semantic(&memory_write);
    assert!(
        result1.is_ok(),
        "First write with unique nonce must succeed"
    );

    // Second write: same nonce "burn-001" — replay attack
    let result2 = agent.commit_l2_semantic(&memory_write);

    assert!(
        result2.is_err(),
        "L2Semantic write must reject nonce replay attack"
    );
    assert_eq!(result2.unwrap_err(), OrchestrationError::NonceAlreadyBurned);
}

#[test]
fn test_state_synchronization_beta_queries_alpha_chunk() {
    // Agent Alpha writes a semantic chunk
    let alpha = Agent::new(
        "alpha".to_string(),
        PathBuf::from("/worktrees/alpha"),
        "sqlite:///var/lib/smaos/memory.db".to_string(),
    );

    let alpha_write = MemoryWrite {
        memory_type: MemoryTier::L2Semantic,
        task_id: "doc-003".to_string(),
        raw_span: "[Phi-Compressed]: Pages 1-50 contain classified network topology".to_string(),
        structured_fields: {
            let mut fields = std::collections::HashMap::new();
            fields.insert("source_document".to_string(), "doc-003".to_string());
            fields.insert("chunk_index".to_string(), "0".to_string());
            fields.insert("nonce".to_string(), "alpha-nonce-001".to_string());
            fields
        },
        operator_signature: Some("alpha_sig_xyz789".to_string()),
    };

    let commit_result = alpha.commit_l2_semantic(&alpha_write);
    assert!(
        commit_result.is_ok(),
        "Alpha must successfully commit L2 chunk"
    );

    // Agent Beta queries for chunks from same document
    let beta = Agent::new(
        "beta".to_string(),
        PathBuf::from("/worktrees/beta"),
        "sqlite:///var/lib/smaos/memory.db".to_string(),
    );

    let query = MemoryQuery {
        document_id: "doc-003".to_string(),
        search_term: "network topology".to_string(),
        max_results: 10,
    };

    let results = beta.query_l2_semantic(&query);

    assert!(results.is_ok(), "Beta must query L2Semantic successfully");
    let nodes = results.unwrap();
    assert!(
        !nodes.is_empty(),
        "Beta must retrieve Alpha's L2Semantic chunk"
    );
    assert_eq!(
        nodes[0].raw_span,
        "[Phi-Compressed]: Pages 1-50 contain classified network topology"
    );
}

#[test]
fn test_worktree_isolation_independent_task_id_frontiers() {
    let mut alpha = Agent::new(
        "alpha".to_string(),
        PathBuf::from("/worktrees/alpha"),
        "sqlite:///var/lib/smaos/memory.db".to_string(),
    );

    let mut beta = Agent::new(
        "beta".to_string(),
        PathBuf::from("/worktrees/beta"),
        "sqlite:///var/lib/smaos/memory.db".to_string(),
    );

    // Alpha and Beta have different git worktrees
    assert_eq!(alpha.git_worktree, PathBuf::from("/worktrees/alpha"));
    assert_eq!(beta.git_worktree, PathBuf::from("/worktrees/beta"));

    // But they share the same SQLite database URI
    assert_eq!(alpha.sqlite_uri, "sqlite:///var/lib/smaos/memory.db");
    assert_eq!(beta.sqlite_uri, "sqlite:///var/lib/smaos/memory.db");

    // Alpha and Beta maintain independent task_id counters
    let alpha_task_id_1 = alpha.generate_task_id();
    let alpha_task_id_2 = alpha.generate_task_id();
    let beta_task_id_1 = beta.generate_task_id();

    // Alpha's task IDs should be sequential within Alpha's frontier
    assert!(alpha_task_id_2 > alpha_task_id_1);

    // Beta's task IDs are independent and should not overlap
    // (in practice, scoped by agent_id)
    assert!(alpha_task_id_1.contains("alpha"));
    assert!(beta_task_id_1.contains("beta"));
}

#[test]
fn test_concurrent_l2_writes_both_agents_with_unique_nonces() {
    let alpha = Agent::new(
        "alpha".to_string(),
        PathBuf::from("/worktrees/alpha"),
        "sqlite:///var/lib/smaos/memory.db".to_string(),
    );

    let beta = Agent::new(
        "beta".to_string(),
        PathBuf::from("/worktrees/beta"),
        "sqlite:///var/lib/smaos/memory.db".to_string(),
    );

    // Alpha writes chunk for doc-004
    let alpha_write = MemoryWrite {
        memory_type: MemoryTier::L2Semantic,
        task_id: "doc-004".to_string(),
        raw_span: "[Phi-Compressed]: Alpha's analysis of pages 1-25".to_string(),
        structured_fields: {
            let mut fields = std::collections::HashMap::new();
            fields.insert(
                "nonce".to_string(),
                "alpha-nonce-concurrent-001".to_string(),
            );
            fields
        },
        operator_signature: Some("alpha_concurrent_sig".to_string()),
    };

    // Beta writes different chunk for doc-004
    let beta_write = MemoryWrite {
        memory_type: MemoryTier::L2Semantic,
        task_id: "doc-004".to_string(),
        raw_span: "[Phi-Compressed]: Beta's analysis of pages 26-50".to_string(),
        structured_fields: {
            let mut fields = std::collections::HashMap::new();
            fields.insert("nonce".to_string(), "beta-nonce-concurrent-001".to_string());
            fields
        },
        operator_signature: Some("beta_concurrent_sig".to_string()),
    };

    // Both writes should succeed because nonces are unique
    let alpha_result = alpha.commit_l2_semantic(&alpha_write);
    let beta_result = beta.commit_l2_semantic(&beta_write);

    assert!(alpha_result.is_ok(), "Alpha concurrent write must succeed");
    assert!(beta_result.is_ok(), "Beta concurrent write must succeed");
}

#[test]
fn test_ap2_signature_validation_structural_check() {
    let memory_write = MemoryWrite {
        memory_type: MemoryTier::L2Semantic,
        task_id: "doc-005".to_string(),
        raw_span: "[Phi-Compressed]: Test content".to_string(),
        structured_fields: {
            let mut fields = std::collections::HashMap::new();
            fields.insert("nonce".to_string(), "test-nonce-001".to_string());
            fields
        },
        operator_signature: Some("invalid_format_not_ed25519".to_string()), // Invalid signature format
    };

    let agent = Agent::new(
        "alpha".to_string(),
        PathBuf::from("/worktrees/alpha"),
        "sqlite:///var/lib/smaos/memory.db".to_string(),
    );

    let result = agent.commit_l2_semantic(&memory_write);

    // Should reject invalid signature format
    assert!(
        result.is_err(),
        "L2Semantic write must reject invalid operator_signature format"
    );
    assert_eq!(
        result.unwrap_err(),
        OrchestrationError::InvalidSignatureFormat
    );
}

#[test]
fn test_memory_query_returns_empty_for_nonexistent_document() {
    let beta = Agent::new(
        "beta".to_string(),
        PathBuf::from("/worktrees/beta"),
        "sqlite:///var/lib/smaos/memory.db".to_string(),
    );

    let query = MemoryQuery {
        document_id: "nonexistent-doc-999".to_string(),
        search_term: "irrelevant".to_string(),
        max_results: 10,
    };

    let results = beta.query_l2_semantic(&query);

    assert!(results.is_ok());
    let nodes = results.unwrap();
    assert!(
        nodes.is_empty(),
        "Query for nonexistent document should return empty list"
    );
}
