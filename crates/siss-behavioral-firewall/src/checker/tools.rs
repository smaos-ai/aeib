use siss_graph_core::node::governance::Severity;
use uuid::Uuid;

use crate::context::InspectionContext;
use crate::types::Violation;
use super::FirewallChecker;

pub struct ToolComplianceChecker;

impl FirewallChecker for ToolComplianceChecker {
    fn name(&self) -> &str {
        "tool_compliance"
    }

    fn check(&self, context: &InspectionContext) -> Vec<Violation> {
        if context.authorized_tools.is_empty() {
            return vec![];
        }

        let output_str = context.output.to_string();
        let mut violations = Vec::new();

        for uuid_str in extract_uuids(&output_str) {
            if let Ok(found_uuid) = Uuid::parse_str(&uuid_str)
                && !context.authorized_tools.contains(&found_uuid)
            {
                violations.push(Violation {
                    checker: self.name().into(),
                    severity: Severity::Enforced,
                    message: format!("Output references unauthorized tool {}", found_uuid),
                });
            }
        }

        violations
    }
}

fn extract_uuids(text: &str) -> Vec<String> {
    let mut uuids = Vec::new();
    let len = text.len();
    let mut i = 0;

    while i + 36 <= len {
        let candidate = &text[i..i + 36];
        if is_uuid_format(candidate) {
            uuids.push(candidate.to_string());
            i += 36;
        } else {
            i += 1;
        }
    }

    uuids
}

fn is_uuid_format(s: &str) -> bool {
    if s.len() != 36 {
        return false;
    }
    let bytes = s.as_bytes();
    for (i, &b) in bytes.iter().enumerate() {
        match i {
            8 | 13 | 18 | 23 => {
                if b != b'-' { return false; }
            }
            _ => {
                if !b.is_ascii_hexdigit() { return false; }
            }
        }
    }
    true
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_context_with_output(output: serde_json::Value, tools: Vec<Uuid>) -> InspectionContext {
        InspectionContext {
            task_id: Uuid::nil(),
            token_cost: 100,
            output,
            authorized_tools: tools,
            budget_remaining: 1000,
        }
    }

    #[test]
    fn test_no_uuids_in_output_no_violation() {
        let checker = ToolComplianceChecker;
        let ctx = make_context_with_output(serde_json::json!({"result": "hello"}), vec![Uuid::new_v4()]);
        assert!(checker.check(&ctx).is_empty());
    }

    #[test]
    fn test_authorized_uuid_no_violation() {
        let tool_id = Uuid::new_v4();
        let checker = ToolComplianceChecker;
        let ctx = make_context_with_output(serde_json::json!({"tool": tool_id.to_string()}), vec![tool_id]);
        assert!(checker.check(&ctx).is_empty());
    }

    #[test]
    fn test_unauthorized_uuid_enforced_violation() {
        let authorized = Uuid::new_v4();
        let unauthorized = Uuid::new_v4();
        let checker = ToolComplianceChecker;
        let ctx = make_context_with_output(serde_json::json!({"tool": unauthorized.to_string()}), vec![authorized]);
        let violations = checker.check(&ctx);
        assert_eq!(violations.len(), 1);
        assert_eq!(violations[0].severity, Severity::Enforced);
    }

    #[test]
    fn test_empty_authorized_tools_skips() {
        let checker = ToolComplianceChecker;
        let ctx = make_context_with_output(serde_json::json!({"tool": Uuid::new_v4().to_string()}), vec![]);
        assert!(checker.check(&ctx).is_empty());
    }

    #[test]
    fn test_is_uuid_format() {
        assert!(is_uuid_format("550e8400-e29b-41d4-a716-446655440000"));
        assert!(!is_uuid_format("not-a-uuid-at-all-nope-definitely"));
        assert!(!is_uuid_format("short"));
    }
}
