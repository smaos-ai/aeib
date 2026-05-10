use serde::{Deserialize, Serialize};
use thiserror::Error;
use uuid::Uuid;

use siss_behavioral_firewall::types::Verdict;
use siss_graph_core::node::NodeId;
use siss_graph_core::node::execution::TaskStatus;
use siss_graph_core::node::memory::ConsolidationTier;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompletionRequest {
    pub task_id: NodeId,
    pub persona_id: NodeId,
    pub intent_mandate_id: NodeId,
    pub tenant_id: NodeId,
    pub verdict: Verdict,
    pub execution_output: serde_json::Value,
    pub token_cost: i64,
    pub estimated_cost: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompletionResult {
    pub task_id: NodeId,
    pub quality_score: f64,
    pub crystallized_memories: Vec<CrystallizedMemory>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CrystallizedMemory {
    pub memory_id: Uuid,
    pub tier: ConsolidationTier,
    pub content: String,
}

#[derive(Debug, Error)]
pub enum FeedbackError {
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

    #[error("database error: {message}")]
    DatabaseError { message: String },
}

impl From<sqlx::Error> for FeedbackError {
    fn from(e: sqlx::Error) -> Self {
        Self::DatabaseError {
            message: e.to_string(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_crystallized_memory() {
        let mem = CrystallizedMemory {
            memory_id: Uuid::new_v4(),
            tier: ConsolidationTier::Episodic,
            content: "test memory".into(),
        };
        assert_eq!(mem.tier, ConsolidationTier::Episodic);
    }
}
