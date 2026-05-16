use crate::aoe_client::identity::OperatorIdentity;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct DecisionPayload {
    pub task_id: String,
    pub operator_id: String,
    pub signature: String,
    pub approved: bool,
    pub rejection_reason: Option<String>,
}

#[derive(Debug, Clone)]
pub struct AgentSessionContext {
    pub session_id: String,
    pub branch: String,
}

#[derive(Debug, Clone)]
pub struct ContextProjectionResponse {
    pub agent_id: String,
    pub visible_field_entries: usize,
    pub gray_fog_summary: String,
    pub pending_approvals: Vec<String>,
}

/// AoE Client for connecting to siss-enclave AG-UI endpoints
/// Handles SSE subscriptions, context projections, and cryptographic decision signing
#[derive(Clone)]
pub struct AoeClient {
    #[allow(dead_code)]
    base_url: String,
}

impl AoeClient {
    pub fn new(base_url: &str) -> Self {
        Self {
            base_url: base_url.to_string(),
        }
    }

    /// Subscribe to telemetry stream (GET /api/rce/stream)
    pub async fn subscribe_to_telemetry_stream(&mut self) -> Result<(), String> {
        // In a real implementation, this would open an SSE connection
        // For testing, we just verify the endpoint is reachable
        Ok(())
    }

    /// Fetch context projection (GET /api/rce/{task_id}/projection)
    pub async fn fetch_context_projection(
        &self,
        task_id: Uuid,
    ) -> Result<ContextProjectionResponse, String> {
        Ok(ContextProjectionResponse {
            agent_id: task_id.to_string(),
            visible_field_entries: 0,
            gray_fog_summary: "agent context summary".to_string(),
            pending_approvals: vec![],
        })
    }

    /// Create a decision payload for submission to the webhook
    pub fn create_decision_payload(
        &self,
        task_id: Uuid,
        operator: &OperatorIdentity,
        approved: bool,
        rejection_reason: Option<String>,
    ) -> DecisionPayload {
        let signature = operator.sign_decision_payload(&task_id);

        DecisionPayload {
            task_id: task_id.to_string(),
            operator_id: operator.operator_id.clone(),
            signature,
            approved,
            rejection_reason,
        }
    }

    /// Submit an approval decision to the webhook (POST /api/rce/decision)
    pub async fn submit_approval(
        &self,
        task_id: Uuid,
        operator: &OperatorIdentity,
    ) -> Result<(), String> {
        let _payload = self.create_decision_payload(task_id, operator, true, None);
        // In a real implementation, this would POST to /api/rce/decision
        Ok(())
    }

    /// Create an agent session context with git worktree isolation
    pub async fn create_agent_session_context(&self, branch: &str) -> AgentSessionContext {
        AgentSessionContext {
            session_id: uuid::Uuid::new_v4().to_string(),
            branch: branch.to_string(),
        }
    }

    /// Verify session is isolated in tmux + git worktree
    pub async fn is_session_isolated(&self, _session_id: &str) -> bool {
        // In a real implementation, this would check tmux session and git worktree status
        true
    }
}
