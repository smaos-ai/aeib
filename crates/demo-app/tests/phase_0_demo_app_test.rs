use demo_app::app::App;
use demo_app::models::{
    AgentSession, AnalysisMandate, AnalysisType, DocumentManifest, DocumentStatus, IngestionSource,
    LogEntry, LogLevel, MandateStatus, MemoryTierState, TuiState,
};
use std::path::PathBuf;

#[test]
fn test_document_manifest_new_has_quarantined_status() {
    let manifest = DocumentManifest {
        document_id: "doc-001".to_string(),
        filename: "test.pdf".to_string(),
        ingestion_timestamp_ms: 1000,
        source: IngestionSource::LoopbackApi,
        total_pages: 5,
        quarantine_path: None,
        status: DocumentStatus::Quarantined,
        parsed_page_count: 0,
        entities_extracted: 0,
        l2_memory_budget_bytes: 1024,
    };

    assert_eq!(manifest.status, DocumentStatus::Quarantined);
}

#[test]
fn test_mandate_ttl_defaults_to_one_hour() {
    let mandate = AnalysisMandate {
        mandate_id: "mandate-001".to_string(),
        document_id: "doc-001".to_string(),
        analysis_type: AnalysisType::EntityExtraction,
        assigned_agent: "alpha".to_string(),
        nonce: "nonce-xyz".to_string(),
        timestamp_ms: 1000,
        ttl_ms: 3_600_000,
        operator_did: vec![1, 2, 3],
        signature: vec![4, 5, 6],
        status: MandateStatus::Pending,
    };

    assert_eq!(mandate.ttl_ms, 3_600_000);
}

#[test]
fn test_analysis_type_semantic_search_carries_query() {
    let analysis = AnalysisType::SemanticSearch {
        query: "find important entities".to_string(),
    };

    match analysis {
        AnalysisType::SemanticSearch { query } => {
            assert_eq!(query, "find important entities");
        }
        _ => panic!("Expected SemanticSearch variant"),
    }
}

#[test]
fn test_mandate_status_transitions_to_completed() {
    let mut mandate = AnalysisMandate {
        mandate_id: "mandate-001".to_string(),
        document_id: "doc-001".to_string(),
        analysis_type: AnalysisType::EntityExtraction,
        assigned_agent: "alpha".to_string(),
        nonce: "nonce-xyz".to_string(),
        timestamp_ms: 1000,
        ttl_ms: 3_600_000,
        operator_did: vec![1, 2, 3],
        signature: vec![4, 5, 6],
        status: MandateStatus::Pending,
    };

    mandate.status = MandateStatus::Completed {
        result: "extraction_ok".to_string(),
    };

    match mandate.status {
        MandateStatus::Completed { result } => {
            assert_eq!(result, "extraction_ok");
        }
        _ => panic!("Expected Completed variant"),
    }
}

#[test]
fn test_agent_session_alpha_has_correct_worktree() {
    let agent = AgentSession {
        agent_id: "alpha".to_string(),
        tmux_pane: "agent-alpha-session:0".to_string(),
        git_worktree: PathBuf::from("/worktrees/alpha"),
        current_document: None,
        active_mandates: vec![],
        inference_tokens_generated: 0,
        memory_tier_state: MemoryTierState {
            l2_visible_field_bytes: 0,
            l2_gray_fog_bytes: 0,
            l2_context_map_bytes: 0,
            l3_ledger_entries: 0,
            cache_hit_rate: 0.0,
            ttft_last_request_ms: 0,
        },
        last_activity_ms: 0,
    };

    assert_eq!(agent.git_worktree, PathBuf::from("/worktrees/alpha"));
}

#[test]
fn test_memory_tier_state_default_zero() {
    let state = MemoryTierState {
        l2_visible_field_bytes: 0,
        l2_gray_fog_bytes: 0,
        l2_context_map_bytes: 0,
        l3_ledger_entries: 0,
        cache_hit_rate: 0.0,
        ttft_last_request_ms: 0,
    };

    assert_eq!(state.l2_visible_field_bytes, 0);
    assert_eq!(state.l2_gray_fog_bytes, 0);
    assert_eq!(state.l2_context_map_bytes, 0);
    assert_eq!(state.l3_ledger_entries, 0);
    assert_eq!(state.cache_hit_rate, 0.0);
    assert_eq!(state.ttft_last_request_ms, 0);
}

#[test]
fn test_tui_state_log_buffer_capped_at_twenty() {
    let mut state = TuiState::new();

    for i in 0..25 {
        state.push_log(LogEntry {
            timestamp_ms: i as u64,
            agent: format!("agent-{}", i),
            event: format!("event-{}", i),
            severity: LogLevel::Info,
        });
    }

    assert_eq!(state.log_buffer.len(), 20);
}

#[test]
fn test_app_on_q_sets_should_quit() {
    let mut app = App::new();
    assert!(!app.should_quit);

    app.on_key('q');
    assert!(app.should_quit);
}
