use siss_agent_shell::hooks::blast_radius::BlastRiskLevel;
use siss_agent_shell::hooks::gitnexus_detect_changes::{
    ChangeDetector, CommitRiskLevel, CommitRiskReport, DetectChangesError, PreCommitGate,
};
/// Phase 61: GitNexus Structural Awareness & Blast-Radius Governance — 27 TDD Tests
use siss_agent_shell::hooks::gitnexus_impact::{
    GitNexusImpactGate, ImpactAnalyzer, ImpactGateConfig, ImpactGateError, ImpactReport,
};
use siss_agent_shell::hooks::gitnexus_rename::{
    CoordinatedRenameGate, RenameError, RenamePreview, RenameScope, RenameTarget,
};
use siss_agent_shell::hooks::{HookResult, LifecycleHook, ToolUseContext};
use siss_graph_core::node::NodeId;
use uuid::Uuid;

// ─── Helpers ──────────────────────────────────────────────────────────────────

fn make_tool_ctx(tool_name: &str, input: serde_json::Value) -> ToolUseContext {
    ToolUseContext {
        task_id: NodeId::new(),
        tool_id: Uuid::new_v4(),
        tool_name: tool_name.to_string(),
        tool_input: input,
        tool_output: None,
    }
}

// ─── Mock ImpactAnalyzer ──────────────────────────────────────────────────────

struct MockImpactAnalyzer {
    report: ImpactReport,
}

impl ImpactAnalyzer for MockImpactAnalyzer {
    fn analyze_impact(&self, _symbol: &str) -> ImpactReport {
        self.report.clone()
    }
}

fn make_impact_report(
    caller_count: usize,
    risk_level: BlastRiskLevel,
    confidence: f64,
) -> ImpactReport {
    ImpactReport {
        symbol: "test_symbol".to_string(),
        caller_count,
        affected_process_count: 1,
        risk_level,
        confidence,
    }
}

// ─── Mock ChangeDetector ──────────────────────────────────────────────────────

struct MockChangeDetector {
    report: CommitRiskReport,
}

impl ChangeDetector for MockChangeDetector {
    fn detect_changes(&self, _diff_context: &str) -> CommitRiskReport {
        self.report.clone()
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// MODULE 1: gitnexus_impact — Tests 1–9
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_impact_gate_low_risk_allows_edit() {
    let gate = GitNexusImpactGate::new(
        MockImpactAnalyzer {
            report: make_impact_report(3, BlastRiskLevel::Low, 0.95),
        },
        ImpactGateConfig {
            max_safe_caller_count: 10,
            require_approval_above: BlastRiskLevel::Medium,
            confidence_threshold: 0.80,
        },
    );

    let ctx = make_tool_ctx("Edit", serde_json::json!({ "file_path": "/src/lib.rs" }));
    assert_eq!(gate.on_pre_tool_use(&ctx), HookResult::Continue);
}

#[test]
fn test_impact_gate_high_risk_defers_with_high_severity() {
    let gate = GitNexusImpactGate::new(
        MockImpactAnalyzer {
            report: make_impact_report(5, BlastRiskLevel::High, 0.90),
        },
        ImpactGateConfig {
            max_safe_caller_count: 10,
            require_approval_above: BlastRiskLevel::Medium,
            confidence_threshold: 0.80,
        },
    );

    let ctx = make_tool_ctx("Edit", serde_json::json!({ "file_path": "/src/lib.rs" }));
    let result = gate.on_pre_tool_use(&ctx);
    assert!(
        matches!(result, HookResult::Defer { ref severity, .. } if severity == "HIGH"),
        "Expected Defer with HIGH, got {:?}",
        result
    );
}

#[test]
fn test_impact_gate_caller_count_exceeded_triggers_defer() {
    let gate = GitNexusImpactGate::new(
        MockImpactAnalyzer {
            report: make_impact_report(100, BlastRiskLevel::Low, 0.95),
        },
        ImpactGateConfig {
            max_safe_caller_count: 10,
            require_approval_above: BlastRiskLevel::Medium,
            confidence_threshold: 0.80,
        },
    );

    let ctx = make_tool_ctx("Edit", serde_json::json!({ "file_path": "/src/lib.rs" }));
    let result = gate.on_pre_tool_use(&ctx);
    assert!(
        matches!(result, HookResult::Defer { .. }),
        "High caller count must defer: {:?}",
        result
    );
}

#[test]
fn test_impact_gate_low_confidence_defers() {
    let gate = GitNexusImpactGate::new(
        MockImpactAnalyzer {
            report: make_impact_report(2, BlastRiskLevel::Low, 0.50),
        },
        ImpactGateConfig {
            max_safe_caller_count: 10,
            require_approval_above: BlastRiskLevel::Medium,
            confidence_threshold: 0.80,
        },
    );

    let ctx = make_tool_ctx("Edit", serde_json::json!({ "file_path": "/src/lib.rs" }));
    let result = gate.on_pre_tool_use(&ctx);
    assert!(
        matches!(result, HookResult::Defer { .. }),
        "Low confidence must defer: {:?}",
        result
    );
}

#[test]
fn test_impact_gate_non_edit_tool_passes_through() {
    let gate = GitNexusImpactGate::new(
        MockImpactAnalyzer {
            report: make_impact_report(9999, BlastRiskLevel::Critical, 0.0),
        },
        ImpactGateConfig::default(),
    );

    let ctx = make_tool_ctx("Bash", serde_json::json!({ "command": "ls" }));
    assert_eq!(gate.on_pre_tool_use(&ctx), HookResult::Continue);
}

#[test]
fn test_impact_gate_intercepts_write_tool() {
    let gate = GitNexusImpactGate::new(
        MockImpactAnalyzer {
            report: make_impact_report(5, BlastRiskLevel::High, 0.90),
        },
        ImpactGateConfig {
            max_safe_caller_count: 10,
            require_approval_above: BlastRiskLevel::Medium,
            confidence_threshold: 0.80,
        },
    );

    let ctx = make_tool_ctx("Write", serde_json::json!({ "file_path": "/src/lib.rs" }));
    let result = gate.on_pre_tool_use(&ctx);
    assert!(
        matches!(result, HookResult::Defer { .. }),
        "Write tool must also be intercepted: {:?}",
        result
    );
}

#[test]
fn test_impact_gate_critical_risk_always_defers() {
    let gate = GitNexusImpactGate::new(
        MockImpactAnalyzer {
            report: make_impact_report(1, BlastRiskLevel::Critical, 0.99),
        },
        ImpactGateConfig {
            max_safe_caller_count: 100,
            require_approval_above: BlastRiskLevel::Medium,
            confidence_threshold: 0.50,
        },
    );

    let ctx = make_tool_ctx(
        "Edit",
        serde_json::json!({ "file_path": "/src/hooks/mod.rs" }),
    );
    let result = gate.on_pre_tool_use(&ctx);
    assert!(
        matches!(result, HookResult::Defer { .. }),
        "Critical risk must defer: {:?}",
        result
    );
}

#[test]
fn test_impact_evaluate_confidence_error_has_correct_scaled_values() {
    let gate = GitNexusImpactGate::new(
        MockImpactAnalyzer {
            report: make_impact_report(2, BlastRiskLevel::Low, 0.50),
        },
        ImpactGateConfig {
            max_safe_caller_count: 10,
            require_approval_above: BlastRiskLevel::Medium,
            confidence_threshold: 0.80,
        },
    );

    let result = gate.evaluate("test_symbol");
    assert_eq!(
        result,
        Err(ImpactGateError::ConfidenceTooLow {
            required: 80,
            actual: 50
        })
    );
}

#[test]
fn test_impact_evaluate_blast_radius_error_contains_symbol_and_count() {
    let gate = GitNexusImpactGate::new(
        MockImpactAnalyzer {
            report: make_impact_report(5, BlastRiskLevel::High, 0.90),
        },
        ImpactGateConfig {
            max_safe_caller_count: 10,
            require_approval_above: BlastRiskLevel::Medium,
            confidence_threshold: 0.80,
        },
    );

    let result = gate.evaluate("critical_fn");
    assert!(matches!(
        result,
        Err(ImpactGateError::BlastRadiusExceeded {
            caller_count: 5,
            risk_level: BlastRiskLevel::High,
            ..
        })
    ));
}

// ═══════════════════════════════════════════════════════════════════════════════
// MODULE 2: gitnexus_detect_changes — Tests 10–18
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_pre_commit_safe_diff_allows_commit() {
    let gate = PreCommitGate::new(
        MockChangeDetector {
            report: CommitRiskReport {
                affected_symbol_count: 1,
                affected_process_count: 1,
                risk_level: CommitRiskLevel::Safe,
            },
        },
        CommitRiskLevel::Safe,
    );

    let ctx = make_tool_ctx(
        "Bash",
        serde_json::json!({ "command": "git commit -m 'fix'", "diff_context": "fn foo() {}" }),
    );
    assert_eq!(gate.on_pre_tool_use(&ctx), HookResult::Continue);
}

#[test]
fn test_pre_commit_blocked_risk_defers_with_high_severity() {
    let gate = PreCommitGate::new(
        MockChangeDetector {
            report: CommitRiskReport {
                affected_symbol_count: 50,
                affected_process_count: 10,
                risk_level: CommitRiskLevel::Blocked,
            },
        },
        CommitRiskLevel::Safe,
    );

    let ctx = make_tool_ctx(
        "Bash",
        serde_json::json!({ "command": "git commit -m 'refactor'", "diff_context": "large diff" }),
    );
    let result = gate.on_pre_tool_use(&ctx);
    assert!(
        matches!(result, HookResult::Defer { ref severity, .. } if severity == "HIGH"),
        "Expected Defer HIGH, got {:?}",
        result
    );
}

#[test]
fn test_pre_commit_empty_diff_defers() {
    let gate = PreCommitGate::new(
        MockChangeDetector {
            report: CommitRiskReport {
                affected_symbol_count: 0,
                affected_process_count: 0,
                risk_level: CommitRiskLevel::Safe,
            },
        },
        CommitRiskLevel::Safe,
    );

    let ctx = make_tool_ctx(
        "Bash",
        serde_json::json!({ "command": "git commit -m 'empty'", "diff_context": "" }),
    );
    let result = gate.on_pre_tool_use(&ctx);
    assert!(
        matches!(result, HookResult::Defer { .. }),
        "Empty diff must defer: {:?}",
        result
    );
}

#[test]
fn test_pre_commit_non_bash_passes_through() {
    let gate = PreCommitGate::new(
        MockChangeDetector {
            report: CommitRiskReport {
                affected_symbol_count: 9999,
                affected_process_count: 100,
                risk_level: CommitRiskLevel::Blocked,
            },
        },
        CommitRiskLevel::Safe,
    );

    let ctx = make_tool_ctx("Edit", serde_json::json!({ "file_path": "/src/lib.rs" }));
    assert_eq!(gate.on_pre_tool_use(&ctx), HookResult::Continue);
}

#[test]
fn test_pre_commit_non_git_commit_bash_passes_through() {
    let gate = PreCommitGate::new(
        MockChangeDetector {
            report: CommitRiskReport {
                affected_symbol_count: 9999,
                affected_process_count: 100,
                risk_level: CommitRiskLevel::Blocked,
            },
        },
        CommitRiskLevel::Safe,
    );

    let ctx = make_tool_ctx("Bash", serde_json::json!({ "command": "cargo test" }));
    assert_eq!(gate.on_pre_tool_use(&ctx), HookResult::Continue);
}

#[test]
fn test_pre_commit_review_required_exceeds_safe_threshold() {
    let gate = PreCommitGate::new(
        MockChangeDetector {
            report: CommitRiskReport {
                affected_symbol_count: 10,
                affected_process_count: 3,
                risk_level: CommitRiskLevel::ReviewRequired,
            },
        },
        CommitRiskLevel::Safe,
    );

    let ctx = make_tool_ctx(
        "Bash",
        serde_json::json!({ "command": "git commit -am 'changes'", "diff_context": "some diff" }),
    );
    let result = gate.on_pre_tool_use(&ctx);
    assert!(
        matches!(result, HookResult::Defer { .. }),
        "ReviewRequired > Safe must defer: {:?}",
        result
    );
}

#[test]
fn test_pre_commit_review_required_at_threshold_continues() {
    let gate = PreCommitGate::new(
        MockChangeDetector {
            report: CommitRiskReport {
                affected_symbol_count: 10,
                affected_process_count: 3,
                risk_level: CommitRiskLevel::ReviewRequired,
            },
        },
        CommitRiskLevel::ReviewRequired,
    );

    let ctx = make_tool_ctx(
        "Bash",
        serde_json::json!({ "command": "git commit -m 'review'", "diff_context": "moderate diff" }),
    );
    assert_eq!(gate.on_pre_tool_use(&ctx), HookResult::Continue);
}

#[test]
fn test_pre_commit_evaluate_empty_diff_returns_error() {
    let gate = PreCommitGate::new(
        MockChangeDetector {
            report: CommitRiskReport {
                affected_symbol_count: 0,
                affected_process_count: 0,
                risk_level: CommitRiskLevel::Safe,
            },
        },
        CommitRiskLevel::Safe,
    );

    let result = gate.evaluate("");
    assert_eq!(result, Err(DetectChangesError::EmptyDiff));
}

#[test]
fn test_pre_commit_evaluate_risk_too_high_contains_correct_level_and_count() {
    let gate = PreCommitGate::new(
        MockChangeDetector {
            report: CommitRiskReport {
                affected_symbol_count: 42,
                affected_process_count: 7,
                risk_level: CommitRiskLevel::Blocked,
            },
        },
        CommitRiskLevel::Safe,
    );

    let result = gate.evaluate("some diff content");
    assert_eq!(
        result,
        Err(DetectChangesError::RiskLevelTooHigh {
            level: CommitRiskLevel::Blocked,
            affected_count: 42,
        })
    );
}

// ═══════════════════════════════════════════════════════════════════════════════
// MODULE 3: gitnexus_rename — Tests 19–27
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_rename_plan_dry_run_true_succeeds() {
    let gate = CoordinatedRenameGate::default();
    let target = RenameTarget {
        old_name: "old_fn".to_string(),
        new_name: "new_fn".to_string(),
        scope: RenameScope::SingleFile {
            path: "/src/lib.rs".to_string(),
        },
    };

    let result = gate.plan_rename(&target, true);
    assert!(result.is_ok(), "dry_run=true should succeed: {:?}", result);
}

#[test]
fn test_rename_plan_dry_run_false_returns_dry_run_mandatory() {
    let gate = CoordinatedRenameGate::default();
    let target = RenameTarget {
        old_name: "old_fn".to_string(),
        new_name: "new_fn".to_string(),
        scope: RenameScope::SingleFile {
            path: "/src/lib.rs".to_string(),
        },
    };

    let result = gate.plan_rename(&target, false);
    assert_eq!(result.unwrap_err(), RenameError::DryRunMandatory);
}

#[test]
fn test_rename_plan_single_file_is_safe() {
    let gate = CoordinatedRenameGate::default();
    let target = RenameTarget {
        old_name: "old_fn".to_string(),
        new_name: "new_fn".to_string(),
        scope: RenameScope::SingleFile {
            path: "/src/lib.rs".to_string(),
        },
    };

    let preview = gate.plan_rename(&target, true).unwrap();
    assert!(preview.is_safe, "SingleFile rename should be safe");
}

#[test]
fn test_rename_plan_full_crate_is_not_safe() {
    let gate = CoordinatedRenameGate::default();
    let target = RenameTarget {
        old_name: "old_trait".to_string(),
        new_name: "new_trait".to_string(),
        scope: RenameScope::FullCrate,
    };

    let preview = gate.plan_rename(&target, true).unwrap();
    assert!(!preview.is_safe, "FullCrate rename should not be safe");
}

#[test]
fn test_rename_execute_safe_preview_returns_change_count() {
    let gate = CoordinatedRenameGate::default();
    let target = RenameTarget {
        old_name: "old_fn".to_string(),
        new_name: "new_fn".to_string(),
        scope: RenameScope::SingleFile {
            path: "/src/lib.rs".to_string(),
        },
    };

    let preview = gate.plan_rename(&target, true).unwrap();
    let result = gate.execute_rename(&preview);
    assert!(result.is_ok(), "Safe preview should execute: {:?}", result);
    assert_eq!(result.unwrap(), preview.total_changes);
}

#[test]
fn test_rename_execute_unsafe_preview_returns_rename_blocked() {
    let gate = CoordinatedRenameGate::default();
    let target = RenameTarget {
        old_name: "old_trait".to_string(),
        new_name: "new_trait".to_string(),
        scope: RenameScope::FullCrate,
    };

    let preview = gate.plan_rename(&target, true).unwrap();
    let result = gate.execute_rename(&preview);
    assert!(matches!(
        result,
        Err(RenameError::LowConfidence { .. }) | Err(RenameError::RenameBlocked { .. })
    ));
}

#[test]
fn test_rename_plan_empty_old_name_returns_blocked() {
    let gate = CoordinatedRenameGate::default();
    let target = RenameTarget {
        old_name: "".to_string(),
        new_name: "new_fn".to_string(),
        scope: RenameScope::SingleFile {
            path: "/src/lib.rs".to_string(),
        },
    };

    let result = gate.plan_rename(&target, true);
    assert_eq!(
        result.unwrap_err(),
        RenameError::RenameBlocked {
            reason: "empty_symbol_name".to_string()
        }
    );
}

#[test]
fn test_rename_execute_low_confidence_returns_correct_scaled_values() {
    let gate = CoordinatedRenameGate::new(0.85, true);
    let preview = RenamePreview {
        affected_files: 1,
        total_changes: 1,
        confidence: 0.60,
        is_safe: true,
    };

    let result = gate.execute_rename(&preview);
    assert_eq!(
        result,
        Err(RenameError::LowConfidence {
            required: 85,
            actual: 60
        })
    );
}

#[test]
fn test_rename_plan_no_dry_run_required_passes_with_dry_run_false() {
    let gate = CoordinatedRenameGate::new(0.85, false);
    let target = RenameTarget {
        old_name: "old_fn".to_string(),
        new_name: "new_fn".to_string(),
        scope: RenameScope::SingleFile {
            path: "/src/lib.rs".to_string(),
        },
    };

    let result = gate.plan_rename(&target, false);
    assert!(
        result.is_ok(),
        "require_dry_run=false should allow dry_run=false: {:?}",
        result
    );
}
