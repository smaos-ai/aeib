use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use crate::node::NodeId;
use crate::node::resource::RiskClass;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum MandateStatus {
    Pending,
    Approved,
    Rejected,
    Expired,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IntentMandate {
    pub id: NodeId,
    pub tenant_id: NodeId,
    pub budget_limit: i64,
    pub budget_spent: i64,
    pub risk_class: RiskClass,
    pub allowed_tools: Vec<NodeId>,
    pub created_at: DateTime<Utc>,
}

impl IntentMandate {
    pub fn new(budget_limit: i64, risk_class: RiskClass, allowed_tools: Vec<NodeId>, tenant_id: NodeId) -> Self {
        Self {
            id: NodeId::new(),
            tenant_id,
            budget_limit,
            budget_spent: 0,
            risk_class,
            allowed_tools,
            created_at: Utc::now(),
        }
    }

    pub fn remaining_budget(&self) -> i64 {
        self.budget_limit - self.budget_spent
    }

    pub fn has_budget(&self, amount: i64) -> bool {
        self.remaining_budget() >= amount
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PaymentMandate {
    pub id: NodeId,
    pub tenant_id: NodeId,
    pub intent_mandate_id: NodeId,
    pub amount: i64,
    pub risk_class: RiskClass,
    pub status: MandateStatus,
    pub cryptographic_signature: Vec<u8>,
    pub created_at: DateTime<Utc>,
}

impl PaymentMandate {
    pub fn new(amount: i64, risk_class: RiskClass, intent_mandate_id: NodeId, tenant_id: NodeId) -> Self {
        Self {
            id: NodeId::new(),
            tenant_id,
            intent_mandate_id,
            amount,
            risk_class,
            status: MandateStatus::Pending,
            cryptographic_signature: Vec::new(),
            created_at: Utc::now(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PaymentReceipt {
    pub id: NodeId,
    pub tenant_id: NodeId,
    pub payment_mandate_id: NodeId,
    pub amount: i64,
    pub cryptographic_signature: Vec<u8>,
    pub executed_at: DateTime<Utc>,
}

impl PaymentReceipt {
    pub fn new(amount: i64, payment_mandate_id: NodeId, cryptographic_signature: Vec<u8>, tenant_id: NodeId) -> Self {
        Self {
            id: NodeId::new(),
            tenant_id,
            payment_mandate_id,
            amount,
            cryptographic_signature,
            executed_at: Utc::now(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_intent_mandate() {
        let tenant_id = NodeId::new();
        let tool_a = NodeId::new();
        let mandate = IntentMandate::new(
            1_000_000,
            RiskClass::Medium,
            vec![tool_a],
            tenant_id,
        );
        assert_eq!(mandate.budget_limit, 1_000_000);
        assert_eq!(mandate.budget_spent, 0);
        assert_eq!(mandate.risk_class, RiskClass::Medium);
        assert_eq!(mandate.allowed_tools, vec![tool_a]);
    }

    #[test]
    fn test_intent_mandate_remaining_budget() {
        let tenant_id = NodeId::new();
        let mut mandate = IntentMandate::new(1000, RiskClass::Low, vec![], tenant_id);
        mandate.budget_spent = 400;
        assert_eq!(mandate.remaining_budget(), 600);
    }

    #[test]
    fn test_intent_mandate_has_budget() {
        let tenant_id = NodeId::new();
        let mut mandate = IntentMandate::new(1000, RiskClass::Low, vec![], tenant_id);
        assert!(mandate.has_budget(1000));
        assert!(!mandate.has_budget(1001));
        mandate.budget_spent = 500;
        assert!(mandate.has_budget(500));
        assert!(!mandate.has_budget(501));
    }

    #[test]
    fn test_create_payment_mandate() {
        let tenant_id = NodeId::new();
        let intent_id = NodeId::new();
        let pm = PaymentMandate::new(500, RiskClass::Low, intent_id, tenant_id);
        assert_eq!(pm.amount, 500);
        assert_eq!(pm.status, MandateStatus::Pending);
        assert_eq!(pm.intent_mandate_id, intent_id);
    }

    #[test]
    fn test_create_payment_receipt() {
        let tenant_id = NodeId::new();
        let pm_id = NodeId::new();
        let receipt = PaymentReceipt::new(500, pm_id, vec![0xAB, 0xCD], tenant_id);
        assert_eq!(receipt.amount, 500);
        assert_eq!(receipt.payment_mandate_id, pm_id);
        assert_eq!(receipt.cryptographic_signature, vec![0xAB, 0xCD]);
    }
}
