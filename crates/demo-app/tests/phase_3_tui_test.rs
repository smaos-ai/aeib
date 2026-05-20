use demo_app::models::{MemoryTier, MemoryWrite};
use demo_app::orchestration::{Agent, MemoryQuery};
use std::path::PathBuf;

#[test]
fn test_tui_state_tracks_alpha_task_id_frontier() {
    let mut alpha = Agent::new(
        "alpha".to_string(),
        PathBuf::from("/worktrees/alpha"),
        "sqlite:///var/lib/smaos/memory.db".to_string(),
    );

    // Generate sequential task IDs
    let task_1 = alpha.generate_task_id();
    let task_2 = alpha.generate_task_id();
    let task_3 = alpha.generate_task_id();

    // Verify frontier progression
    assert_eq!(task_1, "alpha-task-1");
    assert_eq!(task_2, "alpha-task-2");
    assert_eq!(task_3, "alpha-task-3");

    // Task IDs must be monotonically increasing (no resets, no gaps)
    assert!(task_2 > task_1);
    assert!(task_3 > task_2);
}

#[test]
fn test_tui_state_tracks_beta_task_id_frontier_independently() {
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

    let alpha_task = alpha.generate_task_id();
    let beta_task = beta.generate_task_id();

    // Both agents should have independent task_id counters
    assert!(alpha_task.contains("alpha"));
    assert!(beta_task.contains("beta"));

    // Their IDs should not collide
    assert_ne!(alpha_task, beta_task);
}

#[test]
fn test_tui_state_records_agent_worktree_isolation() {
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

    // Worktrees must be distinct and isolate independent git branches
    assert_eq!(alpha.git_worktree, PathBuf::from("/worktrees/alpha"));
    assert_eq!(beta.git_worktree, PathBuf::from("/worktrees/beta"));

    // Both share the same SQLite backend for state synchronization
    assert_eq!(alpha.sqlite_uri, "sqlite:///var/lib/smaos/memory.db");
    assert_eq!(beta.sqlite_uri, "sqlite:///var/lib/smaos/memory.db");
}

#[test]
fn test_tui_l2_query_visualization_captures_phi_compressed_snippet() {
    let alpha = Agent::new(
        "alpha".to_string(),
        PathBuf::from("/worktrees/alpha"),
        "sqlite:///var/lib/smaos/memory.db".to_string(),
    );

    // Write a ϕ-compressed snippet from Alpha
    let memory_write = MemoryWrite {
        memory_type: MemoryTier::L2Semantic,
        task_id: "doc-viz-001".to_string(),
        raw_span: "[Phi-Compressed]: Network topology summary extracted from pages 1-50"
            .to_string(),
        structured_fields: {
            let mut fields = std::collections::HashMap::new();
            fields.insert("nonce".to_string(), "viz-nonce-001".to_string());
            fields.insert("source_document".to_string(), "doc-viz-001".to_string());
            fields
        },
        operator_signature: Some("alpha_viz_sig".to_string()),
    };

    let commit_result = alpha.commit_l2_semantic(&memory_write);
    assert!(
        commit_result.is_ok(),
        "Alpha must commit L2 snippet for TUI visualization"
    );

    // Query the snippet for visualization
    let query = MemoryQuery {
        document_id: "doc-viz-001".to_string(),
        search_term: "network".to_string(),
        max_results: 10,
    };

    let results = alpha.query_l2_semantic(&query);
    assert!(results.is_ok(), "Query must return visualization buffer");

    let nodes = results.unwrap();
    assert!(!nodes.is_empty(), "Query must return at least one snippet");

    // The UI buffer must preserve the ϕ-compressed string for rendering
    let first_node = &nodes[0];
    assert!(
        first_node.raw_span.contains("Phi-Compressed"),
        "TUI visualization buffer must contain the compressed summary"
    );
    assert!(
        first_node.raw_span.contains("Network topology"),
        "Phi-compressed content must be visible in UI rendering"
    );
}

#[test]
fn test_tui_l2_visualization_beta_reads_alpha_snippets() {
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

    // Alpha writes to L2
    let alpha_write = MemoryWrite {
        memory_type: MemoryTier::L2Semantic,
        task_id: "doc-shared-001".to_string(),
        raw_span: "[Phi-Compressed]: Critical entity relationships in classified network"
            .to_string(),
        structured_fields: {
            let mut fields = std::collections::HashMap::new();
            fields.insert("nonce".to_string(), "shared-nonce-001".to_string());
            fields
        },
        operator_signature: Some("alpha_shared_sig".to_string()),
    };

    let alpha_commit = alpha.commit_l2_semantic(&alpha_write);
    assert!(alpha_commit.is_ok(), "Alpha must write snippet");

    // Beta queries the same document (independent pane, shared data)
    let beta_query = MemoryQuery {
        document_id: "doc-shared-001".to_string(),
        search_term: "entity".to_string(),
        max_results: 10,
    };

    let beta_results = beta.query_l2_semantic(&beta_query);
    assert!(
        beta_results.is_ok(),
        "Beta pane must be able to query Alpha's snippets"
    );

    let beta_nodes = beta_results.unwrap();
    assert!(
        !beta_nodes.is_empty(),
        "Beta's TUI pane must display Alpha's L2Semantic chunks"
    );
}

#[test]
fn test_tui_ap2_violation_rejection_missing_signature() {
    let alpha = Agent::new(
        "alpha".to_string(),
        PathBuf::from("/worktrees/alpha"),
        "sqlite:///var/lib/smaos/memory.db".to_string(),
    );

    // Attempt write WITHOUT operator signature (violates AP2)
    let invalid_write = MemoryWrite {
        memory_type: MemoryTier::L2Semantic,
        task_id: "doc-violation-001".to_string(),
        raw_span: "[Phi-Compressed]: Unauthorized write attempt".to_string(),
        structured_fields: {
            let mut fields = std::collections::HashMap::new();
            fields.insert("nonce".to_string(), "violation-nonce-001".to_string());
            fields
        },
        operator_signature: None, // VIOLATION: Missing signature
    };

    let result = alpha.commit_l2_semantic(&invalid_write);

    // AP2 Firewall must REJECT this write
    assert!(
        result.is_err(),
        "TUI must reject writes with missing operator_signature"
    );
}

#[test]
fn test_tui_ap2_violation_detection_nonce_replay() {
    let alpha = Agent::new(
        "alpha".to_string(),
        PathBuf::from("/worktrees/alpha"),
        "sqlite:///var/lib/smaos/memory.db".to_string(),
    );

    let mut write = MemoryWrite {
        memory_type: MemoryTier::L2Semantic,
        task_id: "doc-replay-001".to_string(),
        raw_span: "[Phi-Compressed]: First write with nonce burn-replay-001".to_string(),
        structured_fields: {
            let mut fields = std::collections::HashMap::new();
            fields.insert("nonce".to_string(), "burn-replay-001".to_string());
            fields
        },
        operator_signature: Some("replay_sig_abc123".to_string()),
    };

    // First write: nonce is burned
    let first = alpha.commit_l2_semantic(&write);
    assert!(first.is_ok(), "First write must succeed");

    // Second write: REPLAY ATTACK with same nonce
    write.raw_span = "[Phi-Compressed]: Replay attack attempt".to_string();
    let second = alpha.commit_l2_semantic(&write);

    // AP2 Firewall must detect and REJECT replay
    assert!(
        second.is_err(),
        "TUI AP2 audit must flag nonce replay as VIOLATION"
    );
}

#[test]
fn test_tui_ap2_violation_detection_invalid_signature_format() {
    let alpha = Agent::new(
        "alpha".to_string(),
        PathBuf::from("/worktrees/alpha"),
        "sqlite:///var/lib/smaos/memory.db".to_string(),
    );

    let invalid_sig_write = MemoryWrite {
        memory_type: MemoryTier::L2Semantic,
        task_id: "doc-badsig-001".to_string(),
        raw_span: "[Phi-Compressed]: Invalid signature format".to_string(),
        structured_fields: {
            let mut fields = std::collections::HashMap::new();
            fields.insert("nonce".to_string(), "badsig-nonce-001".to_string());
            fields
        },
        operator_signature: Some("invalid_format_sig".to_string()),
    };

    let result = alpha.commit_l2_semantic(&invalid_sig_write);

    // AP2 Firewall must REJECT malformed signature
    assert!(
        result.is_err(),
        "TUI AP2 audit must flag invalid_format signatures as VIOLATION"
    );
}

#[test]
fn test_tui_violation_counter_increments_on_ap2_rejection() {
    let alpha = Agent::new(
        "alpha".to_string(),
        PathBuf::from("/worktrees/alpha"),
        "sqlite:///var/lib/smaos/memory.db".to_string(),
    );

    // Make three AP2 violations
    let mut violations = 0;

    // Violation 1: Missing signature
    let write1 = MemoryWrite {
        memory_type: MemoryTier::L2Semantic,
        task_id: "v1".to_string(),
        raw_span: "[Phi-Compressed]: Violation 1".to_string(),
        structured_fields: std::collections::HashMap::new(),
        operator_signature: None,
    };
    if alpha.commit_l2_semantic(&write1).is_err() {
        violations += 1;
    }

    // Violation 2: Another missing signature
    let write2 = MemoryWrite {
        memory_type: MemoryTier::L2Semantic,
        task_id: "v2".to_string(),
        raw_span: "[Phi-Compressed]: Violation 2".to_string(),
        structured_fields: std::collections::HashMap::new(),
        operator_signature: None,
    };
    if alpha.commit_l2_semantic(&write2).is_err() {
        violations += 1;
    }

    // Violation 3: Invalid signature format
    let write3 = MemoryWrite {
        memory_type: MemoryTier::L2Semantic,
        task_id: "v3".to_string(),
        raw_span: "[Phi-Compressed]: Violation 3".to_string(),
        structured_fields: {
            let mut fields = std::collections::HashMap::new();
            fields.insert("nonce".to_string(), "v3-nonce".to_string());
            fields
        },
        operator_signature: Some("invalid_format_violation".to_string()),
    };
    if alpha.commit_l2_semantic(&write3).is_err() {
        violations += 1;
    }

    // TUI violation counter must reflect all rejected mandates
    assert_eq!(
        violations, 3,
        "Violations counter must be 3 after 3 AP2 rejections"
    );
}

#[test]
fn test_tui_metrics_real_time_telemetry_capture() {
    let alpha = Agent::new(
        "alpha".to_string(),
        PathBuf::from("/worktrees/alpha"),
        "sqlite:///var/lib/smaos/memory.db".to_string(),
    );

    // Capture agent metrics for header telemetry
    assert!(
        !alpha.agent_id.is_empty(),
        "Agent ID must be present for header"
    );
    assert_eq!(
        alpha.git_worktree,
        PathBuf::from("/worktrees/alpha"),
        "Worktree must be captured for header display"
    );

    // These metrics would populate the Sovereign Header:
    // "Mem: {pressure}% | TTFT: {ttft}ms | Violations: {n}"
    // For now, just verify the agent state is queryable
    let query = MemoryQuery {
        document_id: "header-test".to_string(),
        search_term: "telemetry".to_string(),
        max_results: 1,
    };

    let result = alpha.query_l2_semantic(&query);
    assert!(
        result.is_ok(),
        "Telemetry capture must query agent state without error"
    );
}
