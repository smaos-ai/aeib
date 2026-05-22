/// Phase 49: GitNexus & The Structural Knowledge Graph (π++)
/// RED gate: 8 failing tests that define expected behavior.
/// Invariants: (1) PreToolUse blast radius gate blocks HIGH/CRITICAL edits to core files
///             (2) BlastRiskLevel PartialOrd enforces threshold enforcement
///             (3) KnowledgeAtom protocol enables cross-worktree swarm sync

use siss_agent_shell::hooks::blast_radius::{
    AffectedSymbol, BlastRadiusAnalyzer, BlastRadiusHook, BlastRadiusReport, BlastRadiusThresholds,
    BlastRiskLevel,
};
use siss_agent_shell::hooks::{HookResult, LifecycleHook, ToolUseContext};
use siss_agent_shell::swarm_knowledge::{KnowledgeAtom, KnowledgeKind, SwarmKnowledgeBus};
use siss_graph_core::node::NodeId;
use uuid::Uuid;

// MockBlastRadiusAnalyzer: returns preset report regardless of input
struct MockBlastRadiusAnalyzer {
    pub report: BlastRadiusReport,
}

impl BlastRadiusAnalyzer for MockBlastRadiusAnalyzer {
    fn analyze(&self, _symbol_path: &str) -> BlastRadiusReport {
        self.report.clone()
    }
}

static CORE_PATTERNS: &[&str] = &["mod.rs", "lib.rs", "tokens.rs", "session.rs"];

fn make_tight_thresholds() -> BlastRadiusThresholds {
    BlastRadiusThresholds {
        low_symbol_cap: 5,
        medium_symbol_cap: 15,
        require_approval_above: BlastRiskLevel::Low, // Defer on Medium+
    }
}

fn make_relaxed_thresholds() -> BlastRadiusThresholds {
    BlastRadiusThresholds {
        low_symbol_cap: 5,
        medium_symbol_cap: 15,
        require_approval_above: BlastRiskLevel::High, // Defer only on Critical
    }
}

// Test 1: Low risk → Continue
#[test]
fn test_blast_low_risk_allows_edit() {
    let analyzer = MockBlastRadiusAnalyzer {
        report: BlastRadiusReport {
            target_symbol: "lib.rs".to_string(),
            affected_symbols: vec![
                AffectedSymbol {
                    name: "caller1".to_string(),
                    depth: 1,
                    confidence: 0.9,
                },
                AffectedSymbol {
                    name: "caller2".to_string(),
                    depth: 1,
                    confidence: 0.8,
                },
                AffectedSymbol {
                    name: "caller3".to_string(),
                    depth: 1,
                    confidence: 0.7,
                },
            ],
            affected_process_count: 2,
            risk_level: BlastRiskLevel::Low,
        },
    };

    let hook = BlastRadiusHook {
        analyzer,
        thresholds: make_tight_thresholds(),
        core_file_patterns: CORE_PATTERNS,
    };

    let ctx = ToolUseContext {
        task_id: NodeId::new(),
        tool_id: Uuid::new_v4(),
        tool_name: "Edit".to_string(),
        tool_input: serde_json::json!({ "file_path": "/path/to/lib.rs" }),
        tool_output: None,
    };

    let result = hook.on_pre_tool_use(&ctx);
    assert_eq!(result, HookResult::Continue);
}

// Test 2: High risk with low threshold → Defer
#[test]
fn test_blast_high_risk_defers_edit() {
    let analyzer = MockBlastRadiusAnalyzer {
        report: BlastRadiusReport {
            target_symbol: "lib.rs".to_string(),
            affected_symbols: (0..16)
                .map(|i| AffectedSymbol {
                    name: format!("caller_{}", i),
                    depth: 1,
                    confidence: 0.9,
                })
                .collect(),
            affected_process_count: 8,
            risk_level: BlastRiskLevel::High,
        },
    };

    let hook = BlastRadiusHook {
        analyzer,
        thresholds: make_tight_thresholds(),
        core_file_patterns: CORE_PATTERNS,
    };

    let ctx = ToolUseContext {
        task_id: NodeId::new(),
        tool_id: Uuid::new_v4(),
        tool_name: "Edit".to_string(),
        tool_input: serde_json::json!({ "file_path": "/path/to/lib.rs" }),
        tool_output: None,
    };

    let result = hook.on_pre_tool_use(&ctx);
    assert!(
        matches!(result, HookResult::Defer { ref severity, .. } if severity == "HIGH"),
        "Expected Defer with HIGH severity, got {:?}",
        result
    );
}

// Test 3: Non-core file → Continue (skip analysis)
#[test]
fn test_blast_non_core_file_skips_analysis() {
    let analyzer = MockBlastRadiusAnalyzer {
        report: BlastRadiusReport {
            target_symbol: "should_not_be_used".to_string(),
            affected_symbols: vec![],
            affected_process_count: 999,
            risk_level: BlastRiskLevel::Critical,
        },
    };

    let hook = BlastRadiusHook {
        analyzer,
        thresholds: make_tight_thresholds(),
        core_file_patterns: CORE_PATTERNS,
    };

    let ctx = ToolUseContext {
        task_id: NodeId::new(),
        tool_id: Uuid::new_v4(),
        tool_name: "Edit".to_string(),
        tool_input: serde_json::json!({ "file_path": "/path/to/auto_research.rs" }),
        tool_output: None,
    };

    let result = hook.on_pre_tool_use(&ctx);
    assert_eq!(result, HookResult::Continue);
}

// Test 4: Core file triggers analysis
#[test]
fn test_blast_core_file_triggers_analysis() {
    let analyzer = MockBlastRadiusAnalyzer {
        report: BlastRadiusReport {
            target_symbol: "tokens.rs".to_string(),
            affected_symbols: vec![AffectedSymbol {
                name: "caller1".to_string(),
                depth: 1,
                confidence: 0.95,
            }],
            affected_process_count: 1,
            risk_level: BlastRiskLevel::Low,
        },
    };

    let hook = BlastRadiusHook {
        analyzer,
        thresholds: make_tight_thresholds(),
        core_file_patterns: CORE_PATTERNS,
    };

    let ctx = ToolUseContext {
        task_id: NodeId::new(),
        tool_id: Uuid::new_v4(),
        tool_name: "Edit".to_string(),
        tool_input: serde_json::json!({ "file_path": "/path/to/tokens.rs" }),
        tool_output: None,
    };

    let result = hook.on_pre_tool_use(&ctx);
    assert_eq!(result, HookResult::Continue);
}

// Test 5: Medium risk at tight threshold → Defer
#[test]
fn test_blast_medium_at_tight_threshold_defers() {
    let analyzer = MockBlastRadiusAnalyzer {
        report: BlastRadiusReport {
            target_symbol: "lib.rs".to_string(),
            affected_symbols: (0..8)
                .map(|i| AffectedSymbol {
                    name: format!("caller_{}", i),
                    depth: 1,
                    confidence: 0.9,
                })
                .collect(),
            affected_process_count: 3,
            risk_level: BlastRiskLevel::Medium,
        },
    };

    let hook = BlastRadiusHook {
        analyzer,
        thresholds: make_tight_thresholds(), // require_approval_above = Low
        core_file_patterns: CORE_PATTERNS,
    };

    let ctx = ToolUseContext {
        task_id: NodeId::new(),
        tool_id: Uuid::new_v4(),
        tool_name: "Edit".to_string(),
        tool_input: serde_json::json!({ "file_path": "/path/to/lib.rs" }),
        tool_output: None,
    };

    let result = hook.on_pre_tool_use(&ctx);
    assert!(matches!(result, HookResult::Defer { .. }));
}

// Test 6: Medium risk at relaxed threshold → Continue
#[test]
fn test_blast_medium_at_relaxed_threshold_continues() {
    let analyzer = MockBlastRadiusAnalyzer {
        report: BlastRadiusReport {
            target_symbol: "lib.rs".to_string(),
            affected_symbols: (0..8)
                .map(|i| AffectedSymbol {
                    name: format!("caller_{}", i),
                    depth: 1,
                    confidence: 0.9,
                })
                .collect(),
            affected_process_count: 3,
            risk_level: BlastRiskLevel::Medium,
        },
    };

    let hook = BlastRadiusHook {
        analyzer,
        thresholds: make_relaxed_thresholds(), // require_approval_above = High
        core_file_patterns: CORE_PATTERNS,
    };

    let ctx = ToolUseContext {
        task_id: NodeId::new(),
        tool_id: Uuid::new_v4(),
        tool_name: "Edit".to_string(),
        tool_input: serde_json::json!({ "file_path": "/path/to/lib.rs" }),
        tool_output: None,
    };

    let result = hook.on_pre_tool_use(&ctx);
    assert_eq!(result, HookResult::Continue);
}

// Test 7: Cross-worktree knowledge atom queryable by kind
#[tokio::test]
async fn test_knowledge_atom_cross_worktree_queryable() {
    use std::sync::Arc;
    use siss_agent_shell::swarm_mcp_server::SwarmMcpServer;

    let server = Arc::new(
        SwarmMcpServer::new("sqlite::memory:")
            .await
            .expect("failed to create server"),
    );
    let bus_alpha = SwarmKnowledgeBus::new(server.clone());
    let bus_beta = SwarmKnowledgeBus::new(server.clone());

    let atom = KnowledgeAtom::new(
        KnowledgeKind::VulnerabilityFound,
        "alpha",
        "IntentMandate",
        "Found 16 upstream callers",
        0.95,
    );

    bus_alpha
        .publish(atom.clone(), "alpha")
        .await
        .expect("publish failed");

    let results = bus_beta
        .query_by_kind(&KnowledgeKind::VulnerabilityFound)
        .await
        .expect("query failed");

    assert_eq!(results.len(), 1);
    assert_eq!(results[0].source_worktree, "alpha");
    assert_eq!(results[0].symbol_path, "IntentMandate");
}

// Test 8: Knowledge bus filters by symbol path
#[tokio::test]
async fn test_knowledge_bus_query_by_symbol_filters_correctly() {
    use std::sync::Arc;
    use siss_agent_shell::swarm_mcp_server::SwarmMcpServer;

    let server = Arc::new(
        SwarmMcpServer::new("sqlite::memory:")
            .await
            .expect("failed to create server"),
    );
    let bus = SwarmKnowledgeBus::new(server.clone());

    let atom1 = KnowledgeAtom::new(
        KnowledgeKind::BlastRadiusWarning,
        "alpha",
        "IntentMandate",
        "16 callers",
        0.9,
    );

    let atom2 = KnowledgeAtom::new(
        KnowledgeKind::BlastRadiusWarning,
        "alpha",
        "IntentMandate",
        "nested call chain",
        0.85,
    );

    let atom3 = KnowledgeAtom::new(
        KnowledgeKind::RefactoringOpportunity,
        "beta",
        "FleetRouter",
        "consolidate logic",
        0.7,
    );

    bus.publish(atom1, "alpha").await.expect("publish 1 failed");
    bus.publish(atom2, "alpha").await.expect("publish 2 failed");
    bus.publish(atom3, "beta").await.expect("publish 3 failed");

    let results = bus
        .query_by_symbol("IntentMandate")
        .await
        .expect("query failed");

    assert_eq!(results.len(), 2);
    assert!(results
        .iter()
        .all(|a| a.symbol_path.contains("IntentMandate")));
}
