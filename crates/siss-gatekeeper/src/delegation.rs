/// Cryptographic Inheritance: DelegatedMandate bounds child agents within parent mandate limits.
///
/// Invariant 2: A child mandate cannot exceed parent's budget, tool scope, or delegation depth.
use crate::tokens::IntentMandate;
use thiserror::Error;
use uuid::Uuid;

pub const DELEGATION_DEPTH_MAX: u8 = 4;

/// A mandate delegated from a parent (e.g., TeamLead to Teammate).
/// Enforces budget, tool, and depth bounds at creation time.
#[derive(Debug, Clone)]
pub struct DelegatedMandate {
    pub id: Uuid,
    pub parent_mandate_id: Uuid,
    pub budget_limit: i64,
    pub budget_spent: i64,
    pub allowed_tools: Vec<Uuid>,
    pub risk_class: String,
    pub depth: u8,
}

/// Error type for delegation validation.
#[derive(Debug, Error, PartialEq)]
pub enum DelegationError {
    #[error("delegation budget {requested} exceeds parent remaining {available}")]
    BudgetExceeded { requested: i64, available: i64 },
    #[error("delegation includes tool not authorized in parent")]
    UnauthorizedTool(Uuid),
    #[error("delegation depth {depth} exceeds maximum {max}")]
    DepthExceeded { depth: u8, max: u8 },
}

impl DelegatedMandate {
    /// Create a delegated mandate from a parent, enforcing all three bounds.
    pub fn from_parent(
        parent: &IntentMandate,
        allowed_tools: Vec<Uuid>,
        budget_limit: i64,
        depth: u8,
    ) -> Result<Self, DelegationError> {
        // Bound 1: budget ≤ parent.budget_remaining()
        let parent_remaining = parent.budget_limit - parent.budget_spent;
        if budget_limit > parent_remaining {
            return Err(DelegationError::BudgetExceeded {
                requested: budget_limit,
                available: parent_remaining,
            });
        }

        // Bound 2: tools ⊆ parent.allowed_tools
        for tool_id in &allowed_tools {
            if !parent.allowed_tools.contains(tool_id) {
                return Err(DelegationError::UnauthorizedTool(*tool_id));
            }
        }

        // Bound 3: depth < DELEGATION_DEPTH_MAX
        if depth >= DELEGATION_DEPTH_MAX {
            return Err(DelegationError::DepthExceeded {
                depth,
                max: DELEGATION_DEPTH_MAX,
            });
        }

        Ok(DelegatedMandate {
            id: Uuid::new_v4(),
            parent_mandate_id: parent.id,
            budget_limit,
            budget_spent: 0,
            allowed_tools,
            risk_class: parent.risk_class.clone(),
            depth,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_delegation_all_bounds_satisfied() {
        let parent = IntentMandate {
            id: Uuid::new_v4(),
            budget_limit: 1000,
            budget_spent: 500,
            allowed_tools: vec![Uuid::new_v4(), Uuid::new_v4()],
            risk_class: "low".to_string(),
        };

        let result = DelegatedMandate::from_parent(&parent, vec![parent.allowed_tools[0]], 400, 1);

        assert!(result.is_ok());
        let delegate = result.unwrap();
        assert_eq!(delegate.budget_limit, 400);
        assert_eq!(delegate.depth, 1);
    }

    #[test]
    fn test_delegation_depth_max_boundary() {
        let parent = IntentMandate {
            id: Uuid::new_v4(),
            budget_limit: 1000,
            budget_spent: 0,
            allowed_tools: vec![Uuid::new_v4()],
            risk_class: "low".to_string(),
        };

        // depth == DELEGATION_DEPTH_MAX should fail
        let result = DelegatedMandate::from_parent(
            &parent,
            vec![parent.allowed_tools[0]],
            100,
            DELEGATION_DEPTH_MAX,
        );

        assert!(matches!(result, Err(DelegationError::DepthExceeded { .. })));
    }
}
