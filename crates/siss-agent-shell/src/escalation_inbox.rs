/// Phase 51: Centralized Escalation Inbox
/// Routes Phase 50 approval cards to the SwarmMcpServer bus with phase filtering.
use crate::a2ui::escalation::{EscalationReason, EscalationRequest};
use crate::swarm_mcp_server::{GlobalStateFilter, SwarmMcpServer, SwarmStatePayload};
use std::sync::Arc;
use uuid::Uuid;

#[derive(Debug, PartialEq, Eq)]
pub enum InboxError {
    SerializationFailed(String),
    StoreFailed(String),
    DeserializationFailed(String),
}

pub struct EscalationInbox {
    server: Arc<SwarmMcpServer>,
}

impl EscalationInbox {
    pub fn new(server: Arc<SwarmMcpServer>) -> Self {
        EscalationInbox { server }
    }

    /// Route EscalationRequest to the shared bus.
    /// idempotency_key = format!("escalation:{}:{}", agent_id, request.task_id)
    /// phase           = "ESCALATION_INBOX"
    /// status          = EscalationReason variant name ("BudgetExceeded" | "HumanApprovalRequired")
    /// payload_json    = serde_json::to_string(&request)
    pub async fn submit(
        &self,
        agent_id: &str,
        request: EscalationRequest,
    ) -> Result<(), InboxError> {
        let idempotency_key = format!("escalation:{}:{}", agent_id, request.task_id);
        let status = match request.reason {
            EscalationReason::BudgetExceeded { .. } => "BudgetExceeded".to_string(),
            EscalationReason::HumanApprovalRequired { .. } => "HumanApprovalRequired".to_string(),
        };

        let payload_json = serde_json::to_string(&request)
            .map_err(|e| InboxError::SerializationFailed(e.to_string()))?;

        let payload = SwarmStatePayload {
            idempotency_key,
            agent_id: agent_id.to_string(),
            phase: "ESCALATION_INBOX".to_string(),
            status,
            payload_json: Some(payload_json),
        };

        self.server
            .update_swarm_state(payload)
            .await
            .map_err(|e| InboxError::StoreFailed(e.to_string()))
    }

    /// Query all pending escalations (phase = "ESCALATION_INBOX").
    /// Deserializes payload_json → Vec<EscalationRequest>.
    pub async fn pending(&self) -> Result<Vec<EscalationRequest>, InboxError> {
        let filter = GlobalStateFilter {
            phase_filter: Some("ESCALATION_INBOX".to_string()),
        };

        let states = self
            .server
            .get_global_state(filter)
            .await
            .map_err(|e| InboxError::StoreFailed(e.to_string()))?;

        let mut requests = Vec::new();
        for state in states {
            if let Some(json) = state.payload_json {
                let request: EscalationRequest = serde_json::from_str(&json)
                    .map_err(|e| InboxError::DeserializationFailed(e.to_string()))?;
                requests.push(request);
            }
        }

        Ok(requests)
    }

    /// Dismiss a specific escalation by task_id.
    /// Re-writes the entry with phase = "ESCALATION_DISMISSED" (idempotency_key unchanged).
    pub async fn dismiss(&self, agent_id: &str, task_id: Uuid) -> Result<(), InboxError> {
        let idempotency_key = format!("escalation:{}:{}", agent_id, task_id);

        let payload = SwarmStatePayload {
            idempotency_key,
            agent_id: agent_id.to_string(),
            phase: "ESCALATION_DISMISSED".to_string(),
            status: "Dismissed".to_string(),
            payload_json: None,
        };

        self.server
            .update_swarm_state(payload)
            .await
            .map_err(|e| InboxError::StoreFailed(e.to_string()))
    }
}
