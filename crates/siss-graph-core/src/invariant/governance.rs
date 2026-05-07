use crate::node::governance::{GovernanceRule, Severity};

/// The outcome of evaluating a governance rule violation.
#[derive(Debug, Clone)]
pub struct ViolationOutcome {
    pub blocked: bool,
    pub freeze_persona: bool,
}

/// Find all active GovernanceRules that apply to a given node type.
pub fn find_applicable_rules<'a>(rules: &'a [GovernanceRule], node_type: &str) -> Vec<&'a GovernanceRule> {
    rules
        .iter()
        .filter(|r| r.is_active && r.applies_to.iter().any(|t| t == node_type))
        .collect()
}

/// Determine the enforcement outcome for a given severity level.
pub fn evaluate_violation(severity: Severity) -> ViolationOutcome {
    ViolationOutcome {
        blocked: severity.blocks_operation(),
        freeze_persona: severity.freezes_persona(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::node::NodeId;
    use crate::node::governance::RuleType;

    fn make_rule(name: &str, severity: Severity, applies_to: Vec<&str>) -> GovernanceRule {
        GovernanceRule::new(
            name.into(),
            RuleType::Custom,
            "true".into(),
            severity,
            applies_to.into_iter().map(String::from).collect(),
            NodeId::new(),
            NodeId::new(),
        )
    }

    #[test]
    fn test_find_applicable_rules() {
        let r1 = make_rule("rule1", Severity::Enforced, vec!["IntentMandate"]);
        let r2 = make_rule("rule2", Severity::Advisory, vec!["Task"]);
        let r3 = make_rule("rule3", Severity::Critical, vec!["IntentMandate", "PaymentMandate"]);
        let rules = vec![r1, r2, r3];

        let applicable = find_applicable_rules(&rules, "IntentMandate");
        assert_eq!(applicable.len(), 2);
        assert_eq!(applicable[0].name, "rule1");
        assert_eq!(applicable[1].name, "rule3");
    }

    #[test]
    fn test_find_applicable_rules_no_match() {
        let r1 = make_rule("rule1", Severity::Enforced, vec!["Task"]);
        let rules = vec![r1];

        let applicable = find_applicable_rules(&rules, "Session");
        assert!(applicable.is_empty());
    }

    #[test]
    fn test_find_skips_inactive_rules() {
        let mut r1 = make_rule("rule1", Severity::Enforced, vec!["Task"]);
        r1.deactivate();
        let rules = vec![r1];

        let applicable = find_applicable_rules(&rules, "Task");
        assert!(applicable.is_empty());
    }

    #[test]
    fn test_evaluate_violation_advisory_does_not_block() {
        let result = evaluate_violation(Severity::Advisory);
        assert!(!result.blocked);
        assert!(!result.freeze_persona);
    }

    #[test]
    fn test_evaluate_violation_enforced_blocks() {
        let result = evaluate_violation(Severity::Enforced);
        assert!(result.blocked);
        assert!(!result.freeze_persona);
    }

    #[test]
    fn test_evaluate_violation_critical_blocks_and_freezes() {
        let result = evaluate_violation(Severity::Critical);
        assert!(result.blocked);
        assert!(result.freeze_persona);
    }
}
