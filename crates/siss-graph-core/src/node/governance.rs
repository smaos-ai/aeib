use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use crate::node::NodeId;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum RuleType {
    Rebac,
    Ap2,
    MemoryLifecycle,
    TaskFsm,
    Context,
    Custom,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Severity {
    Advisory,
    Enforced,
    Critical,
}

impl Severity {
    /// Returns true if a violation of this severity should block the operation.
    pub fn blocks_operation(&self) -> bool {
        matches!(self, Self::Enforced | Self::Critical)
    }

    /// Returns true if a violation of this severity should freeze the acting Persona.
    pub fn freezes_persona(&self) -> bool {
        matches!(self, Self::Critical)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GovernanceRule {
    pub id: NodeId,
    pub tenant_id: NodeId,
    pub name: String,
    pub rule_type: RuleType,
    pub expression: String,
    pub severity: Severity,
    pub applies_to: Vec<String>,
    pub version: i32,
    pub is_active: bool,
    pub created_by: NodeId,
    pub created_at: DateTime<Utc>,
}

impl GovernanceRule {
    pub fn new(
        name: String,
        rule_type: RuleType,
        expression: String,
        severity: Severity,
        applies_to: Vec<String>,
        created_by: NodeId,
        tenant_id: NodeId,
    ) -> Self {
        Self {
            id: NodeId::new(),
            tenant_id,
            name,
            rule_type,
            expression,
            severity,
            applies_to,
            version: 1,
            is_active: true,
            created_by,
            created_at: Utc::now(),
        }
    }

    pub fn deactivate(&mut self) {
        self.is_active = false;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_governance_rule() {
        let tenant_id = NodeId::new();
        let persona_id = NodeId::new();
        let rule = GovernanceRule::new(
            "budget_cannot_exceed_limit".into(),
            RuleType::Ap2,
            "IntentMandate.budget_spent <= IntentMandate.budget_limit".into(),
            Severity::Critical,
            vec!["IntentMandate".into(), "PaymentMandate".into()],
            persona_id,
            tenant_id,
        );
        assert_eq!(rule.name, "budget_cannot_exceed_limit");
        assert_eq!(rule.rule_type, RuleType::Ap2);
        assert_eq!(rule.severity, Severity::Critical);
        assert!(rule.is_active);
        assert_eq!(rule.version, 1);
        assert_eq!(rule.applies_to, vec!["IntentMandate", "PaymentMandate"]);
    }

    #[test]
    fn test_governance_rule_deactivate() {
        let tenant_id = NodeId::new();
        let persona_id = NodeId::new();
        let mut rule = GovernanceRule::new(
            "test".into(),
            RuleType::Custom,
            "true".into(),
            Severity::Advisory,
            vec![],
            persona_id,
            tenant_id,
        );
        assert!(rule.is_active);
        rule.deactivate();
        assert!(!rule.is_active);
    }

    #[test]
    fn test_severity_blocks_operation() {
        assert!(!Severity::Advisory.blocks_operation());
        assert!(Severity::Enforced.blocks_operation());
        assert!(Severity::Critical.blocks_operation());
    }

    #[test]
    fn test_severity_freezes_persona() {
        assert!(!Severity::Advisory.freezes_persona());
        assert!(!Severity::Enforced.freezes_persona());
        assert!(Severity::Critical.freezes_persona());
    }
}
