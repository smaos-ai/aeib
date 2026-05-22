/// Phase 50: A2A Handshake & Discovery — Agent-to-Agent Delegation Membrane
/// Ports-and-adapters: real impl fetches /.well-known/agent.json;
/// tests use MockAgentRegistry with preset cards.

use chrono::{DateTime, Utc};
use siss_gatekeeper::tokens::IntentMandate;
use uuid::Uuid;

pub trait AgentRegistry: Send + Sync {
    fn discover(&self, skill_id: &str) -> Option<RemoteAgentCard>;
}

#[derive(Debug, Clone)]
pub struct RemoteAgentCard {
    pub agent_id: Uuid,
    pub endpoint_url: String,
    pub skill_ids: Vec<String>,
    pub auth_scheme: String,
}

#[derive(Debug, Clone)]
pub struct DelegatedMandate {
    pub mandate_id: Uuid,
    pub budget_allocated: i64,
    pub skill_id: String,
    pub expires_at: DateTime<Utc>,
}

#[derive(Debug, Clone)]
pub struct A2AHandshakeResult {
    pub remote_agent: RemoteAgentCard,
    pub delegated_mandate: DelegatedMandate,
}

#[derive(Debug, PartialEq, Eq)]
pub enum A2AError {
    AgentNotFound { skill_id: String },
    HandshakeFailed { reason: String },
    InsufficientBudget { required: i64, available: i64 },
    MandateExhausted,
}

pub struct A2ADelegator<R: AgentRegistry> {
    pub registry: R,
    pub mandate: IntentMandate,
}

impl<R: AgentRegistry> A2ADelegator<R> {
    /// RULE 1: mandate not exhausted → Err(MandateExhausted)
    /// RULE 2: registry can discover skill → Err(AgentNotFound) if None
    /// RULE 3: budget_required ≤ mandate.budget_remaining() → Err(InsufficientBudget) if exceeds
    /// RULE 4: Ok(A2AHandshakeResult) with delegated_mandate capping spend at budget_required
    pub fn delegate(
        &self,
        skill_id: &str,
        budget_required: i64,
    ) -> Result<A2AHandshakeResult, A2AError> {
        // RULE 1: Check mandate exhaustion
        if self.mandate.is_budget_exhausted() {
            return Err(A2AError::MandateExhausted);
        }

        // RULE 2: Discover agent
        let remote_agent = self
            .registry
            .discover(skill_id)
            .ok_or_else(|| A2AError::AgentNotFound {
                skill_id: skill_id.to_string(),
            })?;

        // RULE 3: Check budget headroom
        let available = self.mandate.budget_remaining();
        if budget_required > available {
            return Err(A2AError::InsufficientBudget {
                required: budget_required,
                available,
            });
        }

        // RULE 4: Return handshake result with delegated mandate
        let delegated_mandate = DelegatedMandate {
            mandate_id: Uuid::new_v4(),
            budget_allocated: budget_required,
            skill_id: skill_id.to_string(),
            expires_at: Utc::now() + chrono::Duration::hours(24),
        };

        Ok(A2AHandshakeResult {
            remote_agent,
            delegated_mandate,
        })
    }
}
