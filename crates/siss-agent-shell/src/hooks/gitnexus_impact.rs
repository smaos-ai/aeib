/// Phase 61: GitNexus Impact Gate — AST-Driven PreToolUse Governance
use crate::hooks::blast_radius::BlastRiskLevel;
use crate::hooks::{HookResult, LifecycleHook, ToolUseContext};

pub trait ImpactAnalyzer: Send + Sync {
    fn analyze_impact(&self, symbol: &str) -> ImpactReport;
}

#[derive(Debug, Clone, PartialEq)]
pub struct ImpactReport {
    pub symbol: String,
    pub caller_count: usize,
    pub affected_process_count: usize,
    pub risk_level: BlastRiskLevel,
    pub confidence: f64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ImpactGateError {
    BlastRadiusExceeded {
        symbol: String,
        caller_count: usize,
        risk_level: BlastRiskLevel,
    },
    ConfidenceTooLow {
        required: i64,
        actual: i64,
    },
    AnalysisFailed(String),
}

#[derive(Debug, Clone)]
pub struct ImpactGateConfig {
    pub max_safe_caller_count: usize,
    pub require_approval_above: BlastRiskLevel,
    pub confidence_threshold: f64,
}

impl Default for ImpactGateConfig {
    fn default() -> Self {
        ImpactGateConfig {
            max_safe_caller_count: 10,
            require_approval_above: BlastRiskLevel::Medium,
            confidence_threshold: 0.80,
        }
    }
}

pub struct GitNexusImpactGate<A: ImpactAnalyzer> {
    pub analyzer: A,
    pub config: ImpactGateConfig,
}

impl<A: ImpactAnalyzer> GitNexusImpactGate<A> {
    pub fn new(analyzer: A, config: ImpactGateConfig) -> Self {
        Self { analyzer, config }
    }

    pub fn evaluate(&self, symbol: &str) -> Result<ImpactReport, ImpactGateError> {
        let report = self.analyzer.analyze_impact(symbol);

        let required = (self.config.confidence_threshold * 100.0) as i64;
        let actual = (report.confidence * 100.0) as i64;
        if actual < required {
            return Err(ImpactGateError::ConfidenceTooLow { required, actual });
        }

        if report.risk_level > self.config.require_approval_above {
            return Err(ImpactGateError::BlastRadiusExceeded {
                symbol: report.symbol.clone(),
                caller_count: report.caller_count,
                risk_level: report.risk_level,
            });
        }

        if report.caller_count > self.config.max_safe_caller_count {
            return Err(ImpactGateError::BlastRadiusExceeded {
                symbol: report.symbol.clone(),
                caller_count: report.caller_count,
                risk_level: report.risk_level,
            });
        }

        Ok(report)
    }
}

impl<A: ImpactAnalyzer + Send + Sync> LifecycleHook for GitNexusImpactGate<A> {
    fn name(&self) -> &str {
        "gitnexus_impact_gate"
    }

    fn on_pre_tool_use(&self, ctx: &ToolUseContext) -> HookResult {
        if ctx.tool_name != "Edit" && ctx.tool_name != "Write" {
            return HookResult::Continue;
        }

        let file_path = match ctx.tool_input.get("file_path").and_then(|v| v.as_str()) {
            Some(p) => p,
            None => return HookResult::Continue,
        };

        match self.evaluate(file_path) {
            Ok(_) => HookResult::Continue,
            Err(ImpactGateError::BlastRadiusExceeded {
                symbol,
                caller_count,
                risk_level,
            }) => HookResult::Defer {
                reason: format!(
                    "gitnexus_impact:{}:callers={}:risk={:?}",
                    symbol, caller_count, risk_level
                ),
                severity: "HIGH".to_string(),
            },
            Err(ImpactGateError::ConfidenceTooLow { required, actual }) => HookResult::Defer {
                reason: format!(
                    "gitnexus_impact:confidence_too_low:required={}:actual={}",
                    required, actual
                ),
                severity: "MEDIUM".to_string(),
            },
            Err(ImpactGateError::AnalysisFailed(msg)) => HookResult::Deny {
                reason: format!("gitnexus_impact:analysis_failed:{}", msg),
            },
        }
    }
}
