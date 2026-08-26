use serde::{Deserialize, Serialize};
use uuid::Uuid;
use chrono::{DateTime, Utc};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum GateDecision {
    Approved,
    Denied,
    PendingApproval,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PermitGate {
    pub id: String,
    pub gate_name: String,
    pub policy_article: String,
    pub required_approvals: u32,
    pub current_approvals: u32,
    pub decision: GateDecision,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

impl PermitGate {
    pub fn new(gate_name: String, policy_article: String, required_approvals: u32) -> Self {
        let now = Utc::now();
        Self {
            id: Uuid::new_v4().to_string(),
            gate_name,
            policy_article,
            required_approvals,
            current_approvals: 0,
            decision: GateDecision::PendingApproval,
            created_at: now,
            updated_at: now,
        }
    }

    pub fn add_approval(&mut self) -> GateDecision {
        if self.decision != GateDecision::PendingApproval {
            return self.decision;
        }

        self.current_approvals += 1;
        self.updated_at = Utc::now();

        if self.current_approvals >= self.required_approvals {
            self.decision = GateDecision::Approved;
        }

        self.decision
    }

    pub fn deny(&mut self) {
        self.decision = GateDecision::Denied;
        self.updated_at = Utc::now();
    }

    pub fn is_approved(&self) -> bool {
        self.decision == GateDecision::Approved
    }

    pub fn is_denied(&self) -> bool {
        self.decision == GateDecision::Denied
    }

    pub fn approval_status(&self) -> String {
        format!(
            "{}/{} approvals required for {}",
            self.current_approvals, self.required_approvals, self.gate_name
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_permit_gate_creation() {
        let gate = PermitGate::new(
            "credit_decision".to_string(),
            "Article50".to_string(),
            2,
        );

        assert_eq!(gate.gate_name, "credit_decision");
        assert_eq!(gate.required_approvals, 2);
        assert_eq!(gate.decision, GateDecision::PendingApproval);
    }

    #[test]
    fn test_add_approval() {
        let mut gate = PermitGate::new(
            "test_gate".to_string(),
            "Article50".to_string(),
            2,
        );

        assert_eq!(gate.add_approval(), GateDecision::PendingApproval);
        assert_eq!(gate.add_approval(), GateDecision::Approved);
        assert!(gate.is_approved());
    }

    #[test]
    fn test_deny_gate() {
        let mut gate = PermitGate::new(
            "test_gate".to_string(),
            "Article50".to_string(),
            2,
        );

        gate.deny();
        assert!(gate.is_denied());
    }

    #[test]
    fn test_approval_status() {
        let gate = PermitGate::new(
            "test_gate".to_string(),
            "Article50".to_string(),
            2,
        );

        let status = gate.approval_status();
        assert!(status.contains("0/2"));
    }
}
