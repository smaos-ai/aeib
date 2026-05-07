use regex::Regex;
use siss_graph_core::node::governance::Severity;

use crate::context::InspectionContext;
use crate::types::Violation;
use super::FirewallChecker;

#[derive(Debug, Clone)]
pub struct ForbiddenPattern {
    pub name: String,
    pub pattern: String,
    pub severity: Severity,
}

#[derive(Debug, Clone)]
pub struct ContentSafetyConfig {
    pub patterns: Vec<ForbiddenPattern>,
}

impl Default for ContentSafetyConfig {
    fn default() -> Self {
        Self {
            patterns: vec![
                ForbiddenPattern {
                    name: "shell_dangerous".into(),
                    pattern: r"rm\s+-rf|sudo\s+|chmod\s+777".into(),
                    severity: Severity::Critical,
                },
                ForbiddenPattern {
                    name: "sql_destructive".into(),
                    pattern: r"(?i)DROP\s+TABLE|DELETE\s+FROM\s+\w+\s*$".into(),
                    severity: Severity::Enforced,
                },
                ForbiddenPattern {
                    name: "code_injection".into(),
                    pattern: r"eval\s*\(|exec\s*\(".into(),
                    severity: Severity::Enforced,
                },
            ],
        }
    }
}

pub struct ContentSafetyChecker {
    config: ContentSafetyConfig,
}

impl ContentSafetyChecker {
    pub fn new(config: ContentSafetyConfig) -> Self {
        Self { config }
    }

    pub fn with_defaults() -> Self {
        Self::new(ContentSafetyConfig::default())
    }
}

impl FirewallChecker for ContentSafetyChecker {
    fn name(&self) -> &str {
        "content_safety"
    }

    fn check(&self, context: &InspectionContext) -> Vec<Violation> {
        let output_str = context.output.to_string();
        let mut violations = Vec::new();

        for fp in &self.config.patterns {
            if let Ok(re) = Regex::new(&fp.pattern)
                && re.is_match(&output_str)
            {
                violations.push(Violation {
                    checker: self.name().into(),
                    severity: fp.severity,
                    message: format!("Forbidden pattern '{}' detected in output", fp.name),
                });
            }
        }

        violations
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_context(output: serde_json::Value) -> InspectionContext {
        InspectionContext {
            task_id: uuid::Uuid::nil(),
            token_cost: 100,
            output,
            authorized_tools: vec![],
            budget_remaining: 1000,
        }
    }

    #[test]
    fn test_clean_output_no_violations() {
        let checker = ContentSafetyChecker::with_defaults();
        assert!(checker.check(&make_context(serde_json::json!({"result": "hello"}))).is_empty());
    }

    #[test]
    fn test_rm_rf_critical() {
        let checker = ContentSafetyChecker::with_defaults();
        let v = checker.check(&make_context(serde_json::json!({"cmd": "rm -rf /"})));
        assert_eq!(v.len(), 1);
        assert_eq!(v[0].severity, Severity::Critical);
    }

    #[test]
    fn test_sudo_critical() {
        let checker = ContentSafetyChecker::with_defaults();
        let v = checker.check(&make_context(serde_json::json!({"cmd": "sudo apt install"})));
        assert_eq!(v.len(), 1);
        assert_eq!(v[0].severity, Severity::Critical);
    }

    #[test]
    fn test_eval_enforced() {
        let checker = ContentSafetyChecker::with_defaults();
        let v = checker.check(&make_context(serde_json::json!({"code": "eval('bad')"})));
        assert_eq!(v.len(), 1);
        assert_eq!(v[0].severity, Severity::Enforced);
    }

    #[test]
    fn test_drop_table_enforced() {
        let checker = ContentSafetyChecker::with_defaults();
        let v = checker.check(&make_context(serde_json::json!({"sql": "DROP TABLE users"})));
        assert_eq!(v.len(), 1);
        assert_eq!(v[0].severity, Severity::Enforced);
    }

    #[test]
    fn test_multiple_patterns() {
        let checker = ContentSafetyChecker::with_defaults();
        let v = checker.check(&make_context(serde_json::json!({"cmd": "sudo rm -rf / && eval('x')"})));
        assert!(v.len() >= 2);
    }

    #[test]
    fn test_custom_pattern() {
        let config = ContentSafetyConfig {
            patterns: vec![ForbiddenPattern {
                name: "custom".into(),
                pattern: r"FORBIDDEN".into(),
                severity: Severity::Advisory,
            }],
        };
        let checker = ContentSafetyChecker::new(config);
        let v = checker.check(&make_context(serde_json::json!({"text": "FORBIDDEN word"})));
        assert_eq!(v.len(), 1);
        assert_eq!(v[0].severity, Severity::Advisory);
    }
}
