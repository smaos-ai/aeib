/// AP2 Mandate validation pipeline stage.
/// Validates that the mandate is valid, budget is available, and tools are authorized.

use crate::types::GatekeeperError;
use crate::tokens::{AuthorizedJob, IntentMandate};
use uuid::Uuid;

/// Validate an IntentMandate and authorize a task.
/// Returns AuthorizedJob (task_id + mandate_id) if validation succeeds.
pub fn validate_mandate(
    task_id: Uuid,
    mandate: &IntentMandate,
) -> Result<AuthorizedJob, GatekeeperError> {
    // Check: mandate must have remaining budget
    if mandate.is_budget_exhausted() {
        return Err(GatekeeperError::BudgetExceeded {
            requested: 1,
            remaining: mandate.budget_remaining(),
        });
    }

    // Check: mandate must have non-empty risk_class
    if mandate.risk_class.is_empty() {
        return Err(GatekeeperError::DatabaseError {
            message: "mandate has invalid (empty) risk_class".to_string(),
        });
    }

    // Check: mandate must have allowed_tools (at least one)
    // Note: If no tools, the task has no authorized actions.
    // Depending on use case, this may be valid (e.g., read-only task).
    // For now, we allow empty allowed_tools (validation at execution time).

    Ok(AuthorizedJob {
        task_id,
        mandate_id: mandate.id,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_validate_mandate_succeeds_with_valid_budget() {
        let mandate = IntentMandate {
            id: Uuid::new_v4(),
            budget_limit: 10000,
            budget_spent: 1000,
            risk_class: "low".to_string(),
            allowed_tools: vec![Uuid::new_v4()],
        };
        let task_id = Uuid::new_v4();

        let result = validate_mandate(task_id, &mandate);
        assert!(result.is_ok());

        let authorized = result.unwrap();
        assert_eq!(authorized.task_id, task_id);
        assert_eq!(authorized.mandate_id, mandate.id);
    }

    #[test]
    fn test_validate_mandate_fails_with_exhausted_budget() {
        let mandate = IntentMandate {
            id: Uuid::new_v4(),
            budget_limit: 100,
            budget_spent: 100,
            risk_class: "low".to_string(),
            allowed_tools: vec![],
        };
        let task_id = Uuid::new_v4();

        let result = validate_mandate(task_id, &mandate);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_mandate_fails_with_invalid_risk_class() {
        let mandate = IntentMandate {
            id: Uuid::new_v4(),
            budget_limit: 10000,
            budget_spent: 0,
            risk_class: "".to_string(), // empty
            allowed_tools: vec![],
        };
        let task_id = Uuid::new_v4();

        let result = validate_mandate(task_id, &mandate);
        assert!(result.is_err());
    }

    #[test]
    fn test_manifest_methods_available() {
        let mandate = IntentMandate {
            id: Uuid::new_v4(),
            budget_limit: 1000,
            budget_spent: 100,
            risk_class: "medium".to_string(),
            allowed_tools: vec![Uuid::new_v4()],
        };

        assert_eq!(mandate.budget_remaining(), 900);
        assert!(!mandate.is_budget_exhausted());
        assert!(mandate.can_use_tool(mandate.allowed_tools[0]));
        assert!(!mandate.can_use_tool(Uuid::new_v4())); // different tool
    }
}
