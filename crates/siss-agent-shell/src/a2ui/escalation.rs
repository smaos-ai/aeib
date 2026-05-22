/// Phase 50: A2UI Interactive Escalation — Operator Approval UI Composition
/// Wires UIRequested event into the operator plane when budget is exceeded.

use super::schema::A2UIComponent;
use crate::ucp::UcpContract;

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub enum EscalationReason {
    BudgetExceeded { required: i64, available: i64 },
    HumanApprovalRequired { policy: String },
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct EscalationRequest {
    pub task_id: uuid::Uuid,
    pub contract: UcpContract,
    pub reason: EscalationReason,
}

pub struct EscalationComposer;

impl EscalationComposer {
    /// Compose interactive approval UI from an escalation request.
    /// RULE A: Always produce a Card with "Contract Review Required" title
    /// RULE B: Include Text nodes for seller, skill, price, terms
    /// RULE C: If BudgetExceeded, include Alert with warning level
    /// RULE D: Always append two Buttons (approve, reject) as siblings
    pub fn compose(request: &EscalationRequest) -> Vec<A2UIComponent> {
        let contract = &request.contract;

        // RULE B: Build contract detail Text components
        let contract_details = vec![
            A2UIComponent::Text {
                id: "seller".to_string(),
                content: format!("Seller: {}", contract.seller_agent_id),
                size: None,
            },
            A2UIComponent::Text {
                id: "skill".to_string(),
                content: format!("Skill: {}", contract.skill_id),
                size: None,
            },
            A2UIComponent::Text {
                id: "price".to_string(),
                content: format!("Price: {} AP2 units", contract.agreed_price),
                size: None,
            },
            A2UIComponent::Text {
                id: "terms".to_string(),
                content: format!("Terms: {}", contract.terms),
                size: None,
            },
        ];

        // RULE C: Add Alert if BudgetExceeded
        let mut card_children = contract_details;
        if let EscalationReason::BudgetExceeded { required, available } = request.reason {
            card_children.push(A2UIComponent::Alert {
                id: "budget_warning".to_string(),
                message: format!("Budget exceeded: requires {}, have {}", required, available),
                level: "warning".to_string(),
            });
        }

        // RULE A: Create Card with all children
        let card = A2UIComponent::Card {
            id: "contract_review".to_string(),
            title: Some("Contract Review Required".to_string()),
            children: card_children,
        };

        // RULE D: Append approve and reject buttons as siblings
        vec![
            card,
            A2UIComponent::Button {
                id: "approve".to_string(),
                label: "Approve".to_string(),
                action: Some("approve_contract".to_string()),
            },
            A2UIComponent::Button {
                id: "reject".to_string(),
                label: "Reject".to_string(),
                action: Some("reject_contract".to_string()),
            },
        ]
    }
}
