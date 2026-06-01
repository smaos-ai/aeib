use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use thiserror::Error;
use uuid::Uuid;

use siss_graph_core::node::NodeId;
use siss_graph_core::node::execution::TaskStatus;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthorizationRequest {
    pub task_id: NodeId,
    pub persona_id: NodeId,
    pub intent_mandate_id: NodeId,
    pub requested_tools: Vec<NodeId>,
    pub estimated_cost: i64,
    pub tenant_id: NodeId,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthorizationResult {
    pub task_id: NodeId,
    pub payment_mandate_id: NodeId,
    pub signature: Vec<u8>,
    pub authorized_at: DateTime<Utc>,
}

#[derive(Debug, Error)]
pub enum GatekeeperError {
    // Hard failures — Task transitions to failed
    #[error("cross-tenant violation: source {source_tenant} != target {target_tenant}")]
    TenantViolation {
        source_tenant: Uuid,
        target_tenant: Uuid,
    },

    #[error("persona {persona_id} is frozen")]
    PersonaFrozen { persona_id: Uuid },

    #[error("sovereign associated with tenant {tenant_id} is quarantined")]
    SovereignQuarantined { tenant_id: Uuid },

    #[error("critical rule '{rule_name}' violated, persona_frozen={persona_frozen}")]
    CriticalRuleViolation {
        rule_name: String,
        persona_frozen: bool,
    },

    #[error("covenant violation: merkle_root={merkle_root}, violation={violation}")]
    CovenantViolation {
        merkle_root: String,
        violation: String,
    },

    #[error("intent mismatch for task {task_id}: {reason}")]
    IntentMismatch { task_id: String, reason: String },

    #[error("policy violation '{policy_id}': {reason}")]
    PolicyViolation { policy_id: String, reason: String },

    #[error("temporal violation: {0}")]
    TemporalViolation(String),

    #[error("human gate required for task {task_id}: {reason}")]
    HumanGateRequired { task_id: String, reason: String },

    // Soft failures — Task stays pending
    #[error("access denied for tool {tool_id}")]
    AccessDenied { tool_id: Uuid },

    #[error("budget exceeded: requested {requested}, remaining {remaining}")]
    BudgetExceeded { requested: i64, remaining: i64 },

    #[error("tool {tool_id} not authorized by mandate {mandate_id}")]
    ToolNotAuthorized { tool_id: Uuid, mandate_id: Uuid },

    #[error("enforced rule '{rule_name}' violated")]
    EnforcedRuleViolation { rule_name: String },

    // Infrastructure
    #[error("task {task_id} not found")]
    TaskNotFound { task_id: Uuid },

    #[error("invalid task status: current={current:?}, expected={expected:?}")]
    InvalidTaskStatus {
        current: TaskStatus,
        expected: TaskStatus,
    },

    #[error("signing error: {message}")]
    SigningError { message: String },

    #[error("database error: {message}")]
    DatabaseError { message: String },
}

impl GatekeeperError {
    pub fn is_hard_failure(&self) -> bool {
        matches!(
            self,
            Self::TenantViolation { .. }
                | Self::PersonaFrozen { .. }
                | Self::SovereignQuarantined { .. }
                | Self::CriticalRuleViolation { .. }
                | Self::CovenantViolation { .. }
                | Self::IntentMismatch { .. }
                | Self::PolicyViolation { .. }
                | Self::TemporalViolation(_)
                | Self::HumanGateRequired { .. }
        )
    }
}

impl From<sqlx::Error> for GatekeeperError {
    fn from(e: sqlx::Error) -> Self {
        Self::DatabaseError {
            message: e.to_string(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use siss_graph_core::node::NodeId;

    #[test]
    fn test_create_authorization_request() {
        let req = AuthorizationRequest {
            task_id: NodeId::new(),
            persona_id: NodeId::new(),
            intent_mandate_id: NodeId::new(),
            requested_tools: vec![NodeId::new(), NodeId::new()],
            estimated_cost: 500,
            tenant_id: NodeId::new(),
        };
        assert_eq!(req.estimated_cost, 500);
        assert_eq!(req.requested_tools.len(), 2);
    }

    #[test]
    fn test_gatekeeper_error_is_hard_failure() {
        assert!(
            GatekeeperError::TenantViolation {
                source_tenant: uuid::Uuid::new_v4(),
                target_tenant: uuid::Uuid::new_v4(),
            }
            .is_hard_failure()
        );

        assert!(
            GatekeeperError::PersonaFrozen {
                persona_id: uuid::Uuid::new_v4(),
            }
            .is_hard_failure()
        );

        assert!(
            GatekeeperError::CriticalRuleViolation {
                rule_name: "test".into(),
                persona_frozen: true,
            }
            .is_hard_failure()
        );

        assert!(
            !GatekeeperError::AccessDenied {
                tool_id: uuid::Uuid::new_v4(),
            }
            .is_hard_failure()
        );

        assert!(
            !GatekeeperError::BudgetExceeded {
                requested: 100,
                remaining: 50,
            }
            .is_hard_failure()
        );
    }
}
