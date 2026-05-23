use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use thiserror::Error;
use uuid::Uuid;
use siss_capsule_commit::{CapsuleCommitActor, PrepareRequest};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolInvokeRequest {
    pub tool_name: String,
    pub agent_id: String,
    pub token: Option<String>,
    pub budget_limit: u64,
    pub budget_spent: u64,
    pub parameters: HashMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolInvokeResult {
    pub capsule_id: Uuid,
    pub tool_name: String,
}

#[derive(Debug, Error)]
pub enum EnforcementError {
    #[error("Missing token")]
    MissingToken,

    #[error("Budget exceeded")]
    BudgetExceeded,

    #[error("Commit failed")]
    CommitFailed(String),
}

#[allow(dead_code)]
pub struct Ap2Enforcer {
    actor: CapsuleCommitActor,
}

impl Ap2Enforcer {
    pub fn new() -> Self {
        Ap2Enforcer {
            actor: CapsuleCommitActor::new(),
        }
    }

    pub fn invoke(
        &mut self,
        req: ToolInvokeRequest,
    ) -> Result<ToolInvokeResult, EnforcementError> {
        // 1. Extract and validate token
        let token_str = req.token.ok_or(EnforcementError::MissingToken)?;

        // Parse token string to UUID (for capsule_id)
        let capsule_id = Uuid::parse_str(&token_str)
            .map_err(|_| EnforcementError::MissingToken)?;

        // 2. Create and validate prepare request
        let prepare_req = PrepareRequest {
            capsule_id,
            budget_limit: req.budget_limit,
            budget_spent: req.budget_spent,
            risk_class: 0,
        };

        // 3. Validate the prepare request (budget check)
        let token = prepare_req.validate()
            .map_err(|_| EnforcementError::BudgetExceeded)?;

        // 4. Commit the token
        let entry = self.actor.commit(token)
            .map_err(|e| EnforcementError::CommitFailed(e))?;

        // Return result with capsule_id and tool_name
        Ok(ToolInvokeResult {
            capsule_id: entry.capsule_id,
            tool_name: req.tool_name,
        })
    }
}
