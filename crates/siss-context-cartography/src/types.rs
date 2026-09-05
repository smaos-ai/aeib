use serde::{Deserialize, Serialize};
use thiserror::Error;
use uuid::Uuid;

use siss_graph_core::node::NodeId;
use siss_graph_core::node::memory::ConsolidationTier;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CartographyRequest {
    pub task_id: NodeId,
    pub persona_id: NodeId,
    pub tenant_id: NodeId,
    pub token_budget: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AffectiveSignature {
    pub valence: f64,             // [-1.0, +1.0] negative=threat, positive=opportunity
    pub arousal: f64,             // [0.0, 1.0] activation intensity
    pub sovereign_relevance: f64, // [0.0, 1.0] alignment to user's core values
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VisibleField {
    pub session_id: NodeId,
    pub procedural: Vec<MemoryEntry>,
    pub semantic: Vec<MemoryEntry>,
    pub episodic: Vec<MemoryEntry>,
    pub total_tokens_estimated: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryEntry {
    pub memory_id: Uuid,
    pub content: String,
    pub confidence_score: f64,
    pub tier: ConsolidationTier,
    pub affective_signature: Option<AffectiveSignature>,
}

impl MemoryEntry {
    pub fn estimate_tokens(&self, tokens_per_char: f64) -> i64 {
        (self.content.len() as f64 * tokens_per_char).ceil() as i64
    }
}

#[derive(Debug, Error)]
pub enum CartographyError {
    #[error("task {task_id} not found")]
    TaskNotFound { task_id: Uuid },

    #[error("persona {persona_id} not found")]
    PersonaNotFound { persona_id: Uuid },

    #[error("cross-tenant violation: source {source_tenant} != target {target_tenant}")]
    TenantViolation {
        source_tenant: Uuid,
        target_tenant: Uuid,
    },

    #[error("no memories available for persona")]
    NoMemoriesAvailable,

    #[error("database error: {message}")]
    DatabaseError { message: String },
}

impl From<sqlx::Error> for CartographyError {
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
    fn test_memory_entry_estimate_tokens() {
        let entry = MemoryEntry {
            memory_id: Uuid::new_v4(),
            content: "hello world".into(),
            confidence_score: 0.9,
            tier: ConsolidationTier::Semantic,
            affective_signature: None,
        };
        assert_eq!(entry.estimate_tokens(0.25), 3);
    }

    #[test]
    fn test_memory_entry_estimate_tokens_empty() {
        let entry = MemoryEntry {
            memory_id: Uuid::new_v4(),
            content: "".into(),
            confidence_score: 0.5,
            tier: ConsolidationTier::Episodic,
            affective_signature: None,
        };
        assert_eq!(entry.estimate_tokens(0.25), 0);
    }

    #[test]
    fn test_create_cartography_request() {
        let req = CartographyRequest {
            task_id: NodeId::new(),
            persona_id: NodeId::new(),
            tenant_id: NodeId::new(),
            token_budget: 10000,
        };
        assert_eq!(req.token_budget, 10000);
    }
}
