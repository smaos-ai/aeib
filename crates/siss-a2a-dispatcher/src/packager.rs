use serde::{Deserialize, Serialize};
use siss_memory_plane::operators::{ProjectedEntry, AnnotatedEntry, CartographicOperatorSet};

/// A2A (Agent-to-Agent) payload containing packaged context for inter-agent communication
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct A2APayload {
    pub entries: Vec<ProjectedEntry>,
    pub token_budget_used: usize,
}

/// ContextPackager handles packaging and unpacking context for agent-to-agent communication
pub struct ContextPackager {
    ops: CartographicOperatorSet,
}

impl ContextPackager {
    /// Create a new ContextPackager
    pub fn new(ops: CartographicOperatorSet) -> Self {
        ContextPackager { ops }
    }

    /// Package context for agent dispatch, excluding foreign namespaces
    pub fn package(
        &self,
        annotated: Vec<AnnotatedEntry>,
        namespace: &str,
        token_budget: usize,
    ) -> A2APayload {
        let projected: Vec<ProjectedEntry> = annotated.into_iter().map(|a| self.ops.pi_project(a)).collect();
        let mut filtered = self.ops.lambda_layer(projected, namespace);
        filtered.truncate(token_budget);
        let used = filtered.len();
        A2APayload { entries: filtered, token_budget_used: used }
    }

    /// Check if payload is within budget
    pub fn is_within_budget(&self, payload: &A2APayload, budget: usize) -> bool {
        payload.token_budget_used <= budget
    }
}
