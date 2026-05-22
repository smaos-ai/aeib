/// Phase 39: δ⁺ Security Gate Hook
/// PreToolUse interception with pattern-based deterministic decisions

use regex::Regex;
use crate::hooks::{HookResult, LifecycleHook, ToolUseContext};

/// Configuration for SecurityGateHook
#[derive(Debug, Clone)]
pub struct SecurityGateConfig {
    pub banned_tool_names: Vec<String>,      // Exact match on tool_name → Deny
    pub dangerous_patterns: Vec<String>,     // Regex on tool_input.to_string() → Deny
    pub defer_patterns: Vec<String>,         // Regex on tool_input.to_string() → Defer
    pub defer_severity: String,              // "High" | "Critical"
}

impl Default for SecurityGateConfig {
    fn default() -> Self {
        Self {
            banned_tool_names: vec![],
            dangerous_patterns: vec![],
            defer_patterns: vec![],
            defer_severity: "High".to_string(),
        }
    }
}

/// SecurityGateHook: PreToolUse gate enforcing allow/deny/defer decisions
pub struct SecurityGateHook {
    pub config: SecurityGateConfig,
    banned_regex: Option<Vec<Regex>>,
    dangerous_regex: Option<Vec<Regex>>,
    defer_regex: Option<Vec<Regex>>,
}

impl SecurityGateHook {
    pub fn new(config: SecurityGateConfig) -> Self {
        let banned_regex = if !config.dangerous_patterns.is_empty() {
            Some(
                config
                    .dangerous_patterns
                    .iter()
                    .filter_map(|p| Regex::new(p).ok())
                    .collect(),
            )
        } else {
            None
        };

        let dangerous_regex = if !config.dangerous_patterns.is_empty() {
            Some(
                config
                    .dangerous_patterns
                    .iter()
                    .filter_map(|p| Regex::new(p).ok())
                    .collect(),
            )
        } else {
            None
        };

        let defer_regex = if !config.defer_patterns.is_empty() {
            Some(
                config
                    .defer_patterns
                    .iter()
                    .filter_map(|p| Regex::new(p).ok())
                    .collect(),
            )
        } else {
            None
        };

        Self {
            config,
            banned_regex,
            dangerous_regex,
            defer_regex,
        }
    }
}

impl LifecycleHook for SecurityGateHook {
    fn name(&self) -> &str {
        "security_gate"
    }

    fn on_pre_tool_use(&self, ctx: &ToolUseContext) -> HookResult {
        // Decision priority:
        // 1. Banned tool name (exact match) → Deny
        // 2. Dangerous pattern in input → Deny
        // 3. Defer pattern in input → Defer
        // 4. Continue (allowed)

        // Check banned tool names (exact match)
        if self.config.banned_tool_names.contains(&ctx.tool_name) {
            return HookResult::Deny {
                reason: "banned_tool".to_string(),
            };
        }

        let input_str = ctx.tool_input.to_string();

        // Check dangerous patterns
        if let Some(ref patterns) = self.dangerous_regex {
            for pattern in patterns {
                if pattern.is_match(&input_str) {
                    return HookResult::Deny {
                        reason: "dangerous_pattern".to_string(),
                    };
                }
            }
        }

        // Check defer patterns
        if let Some(ref patterns) = self.defer_regex {
            for pattern in patterns {
                if pattern.is_match(&input_str) {
                    return HookResult::Defer {
                        reason: "defer_required".to_string(),
                        severity: self.config.defer_severity.clone(),
                    };
                }
            }
        }

        HookResult::Continue
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use siss_graph_core::node::NodeId;
    use uuid::Uuid;

    #[test]
    fn test_security_gate_banned_tool() {
        let config = SecurityGateConfig {
            banned_tool_names: vec!["bash_dangerous".to_string()],
            dangerous_patterns: vec![],
            defer_patterns: vec![],
            defer_severity: "High".to_string(),
        };

        let hook = SecurityGateHook::new(config);
        let ctx = ToolUseContext {
            task_id: NodeId::new(),
            tool_id: Uuid::new_v4(),
            tool_name: "bash_dangerous".to_string(),
            tool_input: serde_json::json!({}),
            tool_output: None,
        };

        let result = hook.on_pre_tool_use(&ctx);
        assert!(matches!(result, HookResult::Deny { .. }));
    }

    #[test]
    fn test_security_gate_dangerous_pattern() {
        let config = SecurityGateConfig {
            banned_tool_names: vec![],
            dangerous_patterns: vec!["rm -rf".to_string()],
            defer_patterns: vec![],
            defer_severity: "High".to_string(),
        };

        let hook = SecurityGateHook::new(config);
        let ctx = ToolUseContext {
            task_id: NodeId::new(),
            tool_id: Uuid::new_v4(),
            tool_name: "bash".to_string(),
            tool_input: serde_json::json!({ "cmd": "rm -rf /" }),
            tool_output: None,
        };

        let result = hook.on_pre_tool_use(&ctx);
        assert!(matches!(result, HookResult::Deny { .. }));
    }

    #[test]
    fn test_security_gate_defer_pattern() {
        let config = SecurityGateConfig {
            banned_tool_names: vec![],
            dangerous_patterns: vec![],
            defer_patterns: vec!["DROP TABLE".to_string()],
            defer_severity: "High".to_string(),
        };

        let hook = SecurityGateHook::new(config);
        let ctx = ToolUseContext {
            task_id: NodeId::new(),
            tool_id: Uuid::new_v4(),
            tool_name: "sql".to_string(),
            tool_input: serde_json::json!({ "query": "DROP TABLE users" }),
            tool_output: None,
        };

        let result = hook.on_pre_tool_use(&ctx);
        assert!(matches!(result, HookResult::Defer { .. }));
    }

    #[test]
    fn test_security_gate_continue() {
        let config = SecurityGateConfig::default();
        let hook = SecurityGateHook::new(config);
        let ctx = ToolUseContext {
            task_id: NodeId::new(),
            tool_id: Uuid::new_v4(),
            tool_name: "safe_tool".to_string(),
            tool_input: serde_json::json!({}),
            tool_output: None,
        };

        let result = hook.on_pre_tool_use(&ctx);
        assert_eq!(result, HookResult::Continue);
    }
}
