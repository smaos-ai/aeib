use serde::{Deserialize, Serialize};
use thiserror::Error;

use siss_graph_core::node::NodeId;
use siss_behavioral_firewall::types::{Verdict, Violation};
use siss_feedback_router::types::CrystallizedMemory;
use siss_context_cartography::config::RetrievalConfig;

/// Configuration for creating an AgentSession.
#[derive(Debug, Clone)]
pub struct SessionConfig {
    pub persona_id: NodeId,
    pub tenant_id: NodeId,
    pub budget_limit: i64,
    pub token_budget: i64,
    pub retrieval_config: RetrievalConfig,
}

/// The result of a successfully completed intent.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IntentResult {
    pub task_id: NodeId,
    pub output: serde_json::Value,
    pub verdict: Verdict,
    pub quality_score: f64,
    pub crystallized_memories: Vec<CrystallizedMemory>,
}

/// Parameters for submitting an intent.
#[derive(Debug, Clone)]
pub struct IntentParams {
    pub intent: String,
    pub requested_tools: Vec<NodeId>,
    pub estimated_cost: i64,
}

#[derive(Debug, Error)]
pub enum AgentShellError {
    #[error("session start denied: {reason}")]
    SessionStartDenied { reason: String },

    #[error("intent denied: {reason}")]
    IntentDenied { reason: String },

    #[error("intent halted: {reason}")]
    IntentHalted { reason: String },

    #[error("gatekeeper error: {0}")]
    GatekeeperError(#[from] siss_gatekeeper::types::GatekeeperError),

    #[error("router error: {0}")]
    RouterError(#[from] siss_job_router::types::RouterError),

    #[error("firewall blocked: verdict={verdict:?}, violations={}", violations.len())]
    FirewallBlocked { verdict: Verdict, violations: Vec<Violation> },

    #[error("feedback error: {0}")]
    FeedbackError(#[from] siss_feedback_router::types::FeedbackError),

    #[error("cartography error: {0}")]
    CartographyError(#[from] siss_context_cartography::types::CartographyError),

    #[error("database error: {message}")]
    DatabaseError { message: String },
}

impl From<sqlx::Error> for AgentShellError {
    fn from(e: sqlx::Error) -> Self {
        Self::DatabaseError { message: e.to_string() }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_session_config() {
        let config = SessionConfig {
            persona_id: NodeId::new(),
            tenant_id: NodeId::new(),
            budget_limit: 100_000,
            token_budget: 50_000,
            retrieval_config: RetrievalConfig::default(),
        };
        assert_eq!(config.budget_limit, 100_000);
        assert_eq!(config.token_budget, 50_000);
    }

    #[test]
    fn test_create_intent_params() {
        let params = IntentParams {
            intent: "Summarize this".into(),
            requested_tools: vec![NodeId::new()],
            estimated_cost: 500,
        };
        assert_eq!(params.estimated_cost, 500);
    }
}
