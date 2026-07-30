pub mod enforcer;
pub mod mandates;

pub use enforcer::{Ap2Enforcer, EnforcementError, ToolInvokeRequest, ToolInvokeResult};
pub use mandates::{
    AP2MandateEngine, AuditEvent, AuditEventType, IntentMandate, PaymentMandate, PaymentStatus,
    ResourceType,
};

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;
    use uuid::Uuid;

    #[test]
    fn test_tool_invoke_without_token_rejected() {
        let mut enforcer = Ap2Enforcer::new();
        let req = ToolInvokeRequest {
            tool_name: "test_tool".to_string(),
            agent_id: "agent_1".to_string(),
            token: None,
            budget_limit: 1000,
            budget_spent: 500,
            parameters: HashMap::new(),
        };

        let result = enforcer.invoke(req);
        assert!(result.is_err(), "Should reject when token is missing");
        assert!(matches!(
            result.unwrap_err(),
            EnforcementError::MissingToken
        ));
    }

    #[test]
    fn test_tool_invoke_exceeds_budget_blocked() {
        let mut enforcer = Ap2Enforcer::new();
        let capsule_id = Uuid::new_v4();
        let req = ToolInvokeRequest {
            tool_name: "test_tool".to_string(),
            agent_id: "agent_1".to_string(),
            token: Some(capsule_id.to_string()),
            budget_limit: 100,
            budget_spent: 100, // equals limit → must reject (fail-closed)
            parameters: HashMap::new(),
        };

        let result = enforcer.invoke(req);
        assert!(result.is_err(), "Should reject when budget is exhausted");
        assert!(matches!(
            result.unwrap_err(),
            EnforcementError::BudgetExceeded
        ));
    }

    #[test]
    fn test_valid_token_authorizes_tool_execution() {
        let mut enforcer = Ap2Enforcer::new();
        let capsule_id = Uuid::new_v4();
        let req = ToolInvokeRequest {
            tool_name: "test_tool".to_string(),
            agent_id: "agent_1".to_string(),
            token: Some(capsule_id.to_string()),
            budget_limit: 1000,
            budget_spent: 500,
            parameters: HashMap::new(),
        };

        let result = enforcer.invoke(req);
        assert!(
            result.is_ok(),
            "Should authorize with valid token and budget"
        );
        let tool_result = result.unwrap();
        assert_eq!(tool_result.capsule_id, capsule_id);
        assert_eq!(tool_result.tool_name, "test_tool");
    }
}
