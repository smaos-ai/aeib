use thiserror::Error;

use crate::node::NodeId;
use crate::node::transaction::IntentMandate;

#[derive(Debug, Error)]
pub enum Ap2Error {
    #[error("budget exceeded: requested {requested}, remaining {remaining}")]
    BudgetExceeded { requested: i64, remaining: i64 },

    #[error("tool {tool_id} not authorized by mandate {mandate_id}")]
    ToolNotAuthorized {
        tool_id: uuid::Uuid,
        mandate_id: uuid::Uuid,
    },
}

/// Attempt to debit `amount` from an IntentMandate's budget.
/// Returns Ok(()) and updates budget_spent on success.
/// Returns Err and leaves budget_spent unchanged if insufficient funds.
pub fn debit_budget(mandate: &mut IntentMandate, amount: i64) -> Result<(), Ap2Error> {
    let remaining = mandate.remaining_budget();
    if amount > remaining {
        return Err(Ap2Error::BudgetExceeded {
            requested: amount,
            remaining,
        });
    }
    mandate.budget_spent += amount;
    Ok(())
}

/// Check if a tool is authorized by the given IntentMandate.
pub fn check_tool_authorized(mandate: &IntentMandate, tool_id: NodeId) -> Result<(), Ap2Error> {
    if mandate.allowed_tools.contains(&tool_id) {
        Ok(())
    } else {
        Err(Ap2Error::ToolNotAuthorized {
            tool_id: tool_id.0,
            mandate_id: mandate.id.0,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::node::resource::RiskClass;

    #[test]
    fn test_debit_within_budget() {
        let tenant = NodeId::new();
        let mut mandate = IntentMandate::new(1000, RiskClass::Low, vec![], tenant);
        let result = debit_budget(&mut mandate, 500);
        assert!(result.is_ok());
        assert_eq!(mandate.budget_spent, 500);
    }

    #[test]
    fn test_debit_exact_budget() {
        let tenant = NodeId::new();
        let mut mandate = IntentMandate::new(1000, RiskClass::Low, vec![], tenant);
        let result = debit_budget(&mut mandate, 1000);
        assert!(result.is_ok());
        assert_eq!(mandate.budget_spent, 1000);
    }

    #[test]
    fn test_debit_exceeds_budget() {
        let tenant = NodeId::new();
        let mut mandate = IntentMandate::new(1000, RiskClass::Low, vec![], tenant);
        let result = debit_budget(&mut mandate, 1001);
        assert!(result.is_err());
        assert_eq!(mandate.budget_spent, 0);
    }

    #[test]
    fn test_debit_cumulative() {
        let tenant = NodeId::new();
        let mut mandate = IntentMandate::new(1000, RiskClass::Low, vec![], tenant);
        assert!(debit_budget(&mut mandate, 400).is_ok());
        assert!(debit_budget(&mut mandate, 400).is_ok());
        assert_eq!(mandate.budget_spent, 800);
        assert!(debit_budget(&mut mandate, 201).is_err());
        assert_eq!(mandate.budget_spent, 800);
        assert!(debit_budget(&mut mandate, 200).is_ok());
        assert_eq!(mandate.budget_spent, 1000);
    }

    #[test]
    fn test_tool_authorization_allowed() {
        let tenant = NodeId::new();
        let tool_a = NodeId::new();
        let tool_b = NodeId::new();
        let mandate = IntentMandate::new(1000, RiskClass::Low, vec![tool_a, tool_b], tenant);
        assert!(check_tool_authorized(&mandate, tool_a).is_ok());
        assert!(check_tool_authorized(&mandate, tool_b).is_ok());
    }

    #[test]
    fn test_tool_authorization_denied() {
        let tenant = NodeId::new();
        let tool_a = NodeId::new();
        let tool_c = NodeId::new();
        let mandate = IntentMandate::new(1000, RiskClass::Low, vec![tool_a], tenant);
        assert!(check_tool_authorized(&mandate, tool_c).is_err());
    }

    #[test]
    fn test_empty_allowed_tools_denies_all() {
        let tenant = NodeId::new();
        let mandate = IntentMandate::new(1000, RiskClass::Low, vec![], tenant);
        assert!(check_tool_authorized(&mandate, NodeId::new()).is_err());
    }
}
