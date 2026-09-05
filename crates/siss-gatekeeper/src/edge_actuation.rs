/// Wave 3: AP2-Governed Edge Actuation
/// Physical device commands require authorization from an active, unexhausted IntentMandate.
use crate::tokens::IntentMandate;
use uuid::Uuid;

pub struct EdgeActuationCommand {
    pub command_id: Uuid,
    pub device_id: String,
    pub action: String,
    pub cost_ap2_units: i64,
}

pub struct AuthorizedActuation {
    pub command_id: Uuid,
    pub approved_budget: i64,
}

#[derive(Debug, PartialEq, Eq)]
pub enum ActuationError {
    MandateExhausted,
    InsufficientBudget { required: i64, available: i64 },
    ToolNotAuthorized(Uuid),
}

pub struct EdgeActuationGuard;

impl EdgeActuationGuard {
    /// Authorize a physical actuation against an IntentMandate.
    /// RULE 1: mandate.is_budget_exhausted() → Err(MandateExhausted)
    /// RULE 2: command.cost_ap2_units > mandate.budget_remaining() → Err(InsufficientBudget)
    /// RULE 3: mandate.can_use_tool(device_tool_id) must be true → Err(ToolNotAuthorized)
    pub fn authorize(
        command: &EdgeActuationCommand,
        mandate: &IntentMandate,
        device_tool_id: Uuid,
    ) -> Result<AuthorizedActuation, ActuationError> {
        // RULE 1: Budget must not be exhausted
        if mandate.is_budget_exhausted() {
            return Err(ActuationError::MandateExhausted);
        }

        // RULE 2: Cost must not exceed remaining budget
        let remaining = mandate.budget_remaining();
        if command.cost_ap2_units > remaining {
            return Err(ActuationError::InsufficientBudget {
                required: command.cost_ap2_units,
                available: remaining,
            });
        }

        // RULE 3: Tool must be authorized
        if !mandate.can_use_tool(device_tool_id) {
            return Err(ActuationError::ToolNotAuthorized(device_tool_id));
        }

        Ok(AuthorizedActuation {
            command_id: command.command_id,
            approved_budget: remaining,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_authorize_within_budget() {
        let device_tool_id = Uuid::new_v4();
        let mandate = IntentMandate {
            id: Uuid::new_v4(),
            budget_limit: 500,
            budget_spent: 100,
            risk_class: "low".to_string(),
            allowed_tools: vec![device_tool_id],
        };

        let command = EdgeActuationCommand {
            command_id: Uuid::new_v4(),
            device_id: "ACT_001".to_string(),
            action: "set_temp".to_string(),
            cost_ap2_units: 200,
        };

        let result = EdgeActuationGuard::authorize(&command, &mandate, device_tool_id);
        assert!(result.is_ok());
        let auth = result.unwrap();
        assert_eq!(auth.approved_budget, 400);
    }

    #[test]
    fn test_reject_exceeds_budget() {
        let device_tool_id = Uuid::new_v4();
        let mandate = IntentMandate {
            id: Uuid::new_v4(),
            budget_limit: 1000,
            budget_spent: 950,
            risk_class: "low".to_string(),
            allowed_tools: vec![device_tool_id],
        };

        let command = EdgeActuationCommand {
            command_id: Uuid::new_v4(),
            device_id: "ACT_001".to_string(),
            action: "set_temp".to_string(),
            cost_ap2_units: 200,
        };

        assert!(matches!(
            EdgeActuationGuard::authorize(&command, &mandate, device_tool_id),
            Err(ActuationError::InsufficientBudget {
                required: 200,
                available: 50
            })
        ));
    }

    #[test]
    fn test_reject_unauthorized_tool() {
        let device_tool_id = Uuid::new_v4();
        let unauthorized_tool_id = Uuid::new_v4();

        let mandate = IntentMandate {
            id: Uuid::new_v4(),
            budget_limit: 500,
            budget_spent: 100,
            risk_class: "low".to_string(),
            allowed_tools: vec![device_tool_id],
        };

        let command = EdgeActuationCommand {
            command_id: Uuid::new_v4(),
            device_id: "ACT_001".to_string(),
            action: "set_temp".to_string(),
            cost_ap2_units: 200,
        };

        assert!(matches!(
            EdgeActuationGuard::authorize(&command, &mandate, unauthorized_tool_id),
            Err(ActuationError::ToolNotAuthorized(_))
        ));
    }

    #[test]
    fn test_reject_exhausted_mandate() {
        let device_tool_id = Uuid::new_v4();
        let mandate = IntentMandate {
            id: Uuid::new_v4(),
            budget_limit: 500,
            budget_spent: 500,
            risk_class: "low".to_string(),
            allowed_tools: vec![device_tool_id],
        };

        let command = EdgeActuationCommand {
            command_id: Uuid::new_v4(),
            device_id: "ACT_001".to_string(),
            action: "set_temp".to_string(),
            cost_ap2_units: 1,
        };

        assert!(matches!(
            EdgeActuationGuard::authorize(&command, &mandate, device_tool_id),
            Err(ActuationError::MandateExhausted)
        ));
    }
}
