use parking_lot::RwLock;
use std::collections::HashMap;
use std::sync::Arc;
use thiserror::Error;

#[derive(Debug, Clone, PartialEq)]
pub enum AccessDecision {
    Allow,
    Deny,
}

#[derive(Debug, Clone)]
pub struct TrustContext {
    pub user_id: String,
    pub agent_id: String,
}

impl TrustContext {
    pub fn new(user_id: String, agent_id: String) -> Self {
        Self { user_id, agent_id }
    }
}

#[derive(Debug, Error)]
pub enum TrustBoundaryError {
    #[error("Policy error: {0}")]
    PolicyError(String),
    #[error("Evaluation error: {0}")]
    EvaluationError(String),
}

pub struct TrustBoundary {
    policies: Arc<RwLock<HashMap<String, Vec<String>>>>,
}

impl TrustBoundary {
    pub fn new() -> Self {
        Self {
            policies: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    pub fn add_trust_policy(
        &mut self,
        user_id: String,
        agent_id: String,
    ) -> Result<(), TrustBoundaryError> {
        let mut policies = self.policies.write();
        policies
            .entry(user_id)
            .or_insert_with(Vec::new)
            .push(agent_id);
        Ok(())
    }

    pub fn evaluate(&self, _context: &TrustContext) -> Result<AccessDecision, TrustBoundaryError> {
        // Default deny - sync version
        Ok(AccessDecision::Deny)
    }

    pub fn evaluate_with_policies(
        &self,
        context: &TrustContext,
    ) -> Result<AccessDecision, TrustBoundaryError> {
        let policies = self.policies.read();

        if let Some(allowed_agents) = policies.get(&context.user_id) {
            if allowed_agents.contains(&context.agent_id) {
                return Ok(AccessDecision::Allow);
            }
        }

        Ok(AccessDecision::Deny)
    }
}

impl Default for TrustBoundary {
    fn default() -> Self {
        Self::new()
    }
}

impl Clone for TrustBoundary {
    fn clone(&self) -> Self {
        Self {
            policies: self.policies.clone(),
        }
    }
}
