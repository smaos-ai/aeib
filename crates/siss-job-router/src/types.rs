use serde::{Deserialize, Serialize};
use thiserror::Error;
use uuid::Uuid;

use siss_graph_core::node::NodeId;
use siss_graph_core::node::execution::{HardwareTarget, TaskStatus};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RoutingRequest {
    pub task_id: NodeId,
    pub persona_id: NodeId,
    pub tenant_id: NodeId,
    #[serde(default)]
    pub depends_on: Vec<Uuid>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RoutingResult {
    pub task_id: NodeId,
    pub hardware_target: HardwareTarget,
    pub execution: ExecutionResult,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionResult {
    pub output: serde_json::Value,
    pub token_cost: i64,
    pub duration_ms: u64,
}

#[derive(Debug, Error)]
pub enum RouterError {
    #[error("task {task_id} not found")]
    TaskNotFound { task_id: Uuid },

    #[error("invalid task status: current={current:?}, expected={expected:?}")]
    InvalidTaskStatus {
        current: TaskStatus,
        expected: TaskStatus,
    },

    #[error("cross-tenant violation: source {source_tenant} != target {target_tenant}")]
    TenantViolation {
        source_tenant: Uuid,
        target_tenant: Uuid,
    },

    #[error("execution failed: {message}")]
    ExecutionFailed { message: String },

    #[error("database error: {message}")]
    DatabaseError { message: String },
}

impl From<sqlx::Error> for RouterError {
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
    fn test_create_routing_request() {
        let req = RoutingRequest {
            task_id: NodeId::new(),
            persona_id: NodeId::new(),
            tenant_id: NodeId::new(),
        };
        assert!(!req.task_id.0.is_nil());
    }

    #[test]
    fn test_create_execution_result() {
        let result = ExecutionResult {
            output: serde_json::json!({"status": "done"}),
            token_cost: 100,
            duration_ms: 50,
        };
        assert_eq!(result.token_cost, 100);
        assert_eq!(result.duration_ms, 50);
    }
}
