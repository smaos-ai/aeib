/// Phase 61: Pre-Commit Risk Gate — Structural Risk Analysis Before Commit

use crate::hooks::{HookResult, LifecycleHook, ToolUseContext};

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub enum CommitRiskLevel {
    Safe,
    ReviewRequired,
    Blocked,
}

pub trait ChangeDetector: Send + Sync {
    fn detect_changes(&self, diff_context: &str) -> CommitRiskReport;
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CommitRiskReport {
    pub affected_symbol_count: usize,
    pub affected_process_count: usize,
    pub risk_level: CommitRiskLevel,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DetectChangesError {
    RiskLevelTooHigh {
        level: CommitRiskLevel,
        affected_count: usize,
    },
    EmptyDiff,
    DetectionFailed(String),
}

pub struct PreCommitGate<D: ChangeDetector> {
    pub detector: D,
    pub max_safe_risk: CommitRiskLevel,
}

impl<D: ChangeDetector> PreCommitGate<D> {
    pub fn new(detector: D, max_safe_risk: CommitRiskLevel) -> Self {
        Self {
            detector,
            max_safe_risk,
        }
    }

    pub fn evaluate(&self, diff_context: &str) -> Result<CommitRiskReport, DetectChangesError> {
        if diff_context.is_empty() {
            return Err(DetectChangesError::EmptyDiff);
        }

        let report = self.detector.detect_changes(diff_context);

        if report.risk_level > self.max_safe_risk {
            return Err(DetectChangesError::RiskLevelTooHigh {
                level: report.risk_level,
                affected_count: report.affected_symbol_count,
            });
        }

        Ok(report)
    }
}

impl<D: ChangeDetector + Send + Sync> LifecycleHook for PreCommitGate<D> {
    fn name(&self) -> &str {
        "pre_commit_gate"
    }

    fn on_pre_tool_use(&self, ctx: &ToolUseContext) -> HookResult {
        if ctx.tool_name != "Bash" {
            return HookResult::Continue;
        }

        let command = match ctx.tool_input.get("command").and_then(|v| v.as_str()) {
            Some(c) => c,
            None => return HookResult::Continue,
        };

        if !command.contains("git commit") {
            return HookResult::Continue;
        }

        let diff_context = ctx
            .tool_input
            .get("diff_context")
            .and_then(|v| v.as_str())
            .unwrap_or("");

        match self.evaluate(diff_context) {
            Ok(_) => HookResult::Continue,
            Err(DetectChangesError::EmptyDiff) => HookResult::Defer {
                reason: "pre_commit_gate:empty_diff:analysis_required".to_string(),
                severity: "MEDIUM".to_string(),
            },
            Err(DetectChangesError::RiskLevelTooHigh {
                level,
                affected_count,
            }) => HookResult::Defer {
                reason: format!(
                    "pre_commit_gate:risk={:?}:affected_symbols={}",
                    level, affected_count
                ),
                severity: "HIGH".to_string(),
            },
            Err(DetectChangesError::DetectionFailed(msg)) => HookResult::Deny {
                reason: format!("pre_commit_gate:detection_failed:{}", msg),
            },
        }
    }
}
