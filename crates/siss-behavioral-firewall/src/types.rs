use serde::{Deserialize, Serialize};
use thiserror::Error;
use uuid::Uuid;

use siss_graph_core::node::NodeId;
use siss_graph_core::node::execution::TaskStatus;
use siss_graph_core::node::governance::Severity;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InspectionRequest {
    pub task_id: NodeId,
    pub persona_id: NodeId,
    pub intent_mandate_id: NodeId,
    pub tenant_id: NodeId,
    pub execution_output: serde_json::Value,
    pub token_cost: i64,
    pub authorized_tools: Vec<Uuid>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InspectionResult {
    pub task_id: NodeId,
    pub verdict: Verdict,
    pub violations: Vec<Violation>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Verdict {
    Clear,
    Blocked,
    CriticalBlocked,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Violation {
    pub checker: String,
    pub severity: Severity,
    pub message: String,
}

#[derive(Debug, Error)]
pub enum FirewallError {
    #[error("task {task_id} not found")]
    TaskNotFound { task_id: Uuid },

    #[error("invalid task status: current={current:?}, expected={expected:?}")]
    InvalidTaskStatus { current: TaskStatus, expected: TaskStatus },

    #[error("cross-tenant violation: source {source_tenant} != target {target_tenant}")]
    TenantViolation { source_tenant: Uuid, target_tenant: Uuid },

    #[error("database error: {message}")]
    DatabaseError { message: String },
}

impl From<sqlx::Error> for FirewallError {
    fn from(e: sqlx::Error) -> Self {
        Self::DatabaseError { message: e.to_string() }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_verdict_equality() {
        assert_eq!(Verdict::Clear, Verdict::Clear);
        assert_ne!(Verdict::Clear, Verdict::Blocked);
        assert_ne!(Verdict::Blocked, Verdict::CriticalBlocked);
    }

    #[test]
    fn test_create_violation() {
        let v = Violation {
            checker: "budget_compliance".into(),
            severity: Severity::Critical,
            message: "overspent".into(),
        };
        assert_eq!(v.checker, "budget_compliance");
        assert_eq!(v.severity, Severity::Critical);
    }
}
