/// Phase 49: Blast Radius Gate — PreToolUse structural edit validation
/// Prevents silent HIGH/CRITICAL impact edits to core files via GitNexus impact analysis.
use crate::hooks::{HookResult, LifecycleHook, ToolUseContext};

/// BlastRadiusAnalyzer trait for pluggable impact analysis.
/// Tests use MockBlastRadiusAnalyzer; production uses gitnexus_impact MCP tool.
pub trait BlastRadiusAnalyzer: Send + Sync {
    fn analyze(&self, symbol_path: &str) -> BlastRadiusReport;
}

/// Risk level ordered by severity (PartialOrd derives correct ordering).
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum BlastRiskLevel {
    Low,
    Medium,
    High,
    Critical,
}

/// Single affected symbol with call graph depth and confidence.
#[derive(Debug, Clone)]
pub struct AffectedSymbol {
    pub name: String,
    pub depth: u8,       // 1=direct, 2=indirect, 3=transitive
    pub confidence: f64, // 0.0–1.0 from GitNexus edge weight
}

/// Impact analysis report from GitNexus or mock analyzer.
#[derive(Debug, Clone)]
pub struct BlastRadiusReport {
    pub target_symbol: String,
    pub affected_symbols: Vec<AffectedSymbol>,
    pub affected_process_count: usize,
    pub risk_level: BlastRiskLevel,
}

/// Threshold configuration for gate decisions.
#[derive(Debug, Clone)]
pub struct BlastRadiusThresholds {
    pub low_symbol_cap: usize,                  // Below this → Low risk
    pub medium_symbol_cap: usize,               // Between caps → Medium
    pub require_approval_above: BlastRiskLevel, // Defer if risk > this
}

/// Phase 49 BlastRadiusHook: PreToolUse gate for structural edits.
pub struct BlastRadiusHook<A: BlastRadiusAnalyzer> {
    pub analyzer: A,
    pub thresholds: BlastRadiusThresholds,
    pub core_file_patterns: &'static [&'static str],
}

impl<A: BlastRadiusAnalyzer> LifecycleHook for BlastRadiusHook<A> {
    fn name(&self) -> &str {
        "blast_radius"
    }

    fn on_pre_tool_use(&self, ctx: &ToolUseContext) -> HookResult {
        // RULE 1: Non-structural tools → Continue
        if ctx.tool_name != "Edit" && ctx.tool_name != "Write" {
            return HookResult::Continue;
        }

        // RULE 2: Extract file_path and check if core file
        let file_path = match ctx.tool_input.get("file_path").and_then(|v| v.as_str()) {
            Some(p) => p,
            None => return HookResult::Continue,
        };

        if !self
            .core_file_patterns
            .iter()
            .any(|pattern| file_path.ends_with(pattern))
        {
            return HookResult::Continue;
        }

        // RULE 3: Analyze impact
        let report = self.analyzer.analyze(file_path);

        // RULE 4: Check threshold
        if report.risk_level > self.thresholds.require_approval_above {
            return HookResult::Defer {
                reason: format!("blast_radius:{} symbols", report.affected_symbols.len()),
                severity: "HIGH".to_string(),
            };
        }

        // RULE 5: Within threshold → Continue
        HookResult::Continue
    }
}
