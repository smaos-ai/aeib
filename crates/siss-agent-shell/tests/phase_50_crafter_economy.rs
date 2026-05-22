/// Phase 50: The Crafter Economy — A2A, UCP, and AP2 Syndication
/// RED gate: 9 failing tests define expected behavior for economic sovereignty.
/// Invariants: (1) A2A delegation membrane gates on agent discovery & budget
///             (2) UCP/AP2 checkout enforces cryptographic contracts
///             (3) A2UI escalation wires budget-overflow to operator approval

use chrono::Utc;
use siss_agent_shell::a2a::{
    A2ADelegator, A2AError, A2AHandshakeResult, AgentRegistry, DelegatedMandate, RemoteAgentCard,
};
use siss_agent_shell::a2ui::escalation::{EscalationComposer, EscalationReason, EscalationRequest};
use siss_agent_shell::a2ui::A2UIComponent;
use siss_agent_shell::ucp::{UcpCheckout, UcpContract, UcpError, SignedUcpContract};
use siss_gatekeeper::signer::MockSigner;
use siss_gatekeeper::tokens::IntentMandate;
use std::collections::HashMap;
use uuid::Uuid;

// MockAgentRegistry: preset HashMap for testing
struct MockAgentRegistry {
    cards: HashMap<String, RemoteAgentCard>,
}

impl AgentRegistry for MockAgentRegistry {
    fn discover(&self, skill_id: &str) -> Option<RemoteAgentCard> {
        self.cards.get(skill_id).cloned()
    }
}

// Test 1: A2A discovers agent by skill
#[test]
fn test_a2a_discovers_agent_by_skill() {
    let security_audit_card = RemoteAgentCard {
        agent_id: Uuid::new_v4(),
        endpoint_url: "https://security-auditor.example.com".to_string(),
        skill_ids: vec!["security_audit".to_string()],
        auth_scheme: "Bearer".to_string(),
    };

    let mut cards = HashMap::new();
    cards.insert("security_audit".to_string(), security_audit_card.clone());

    let registry = MockAgentRegistry { cards };
    let mandate = IntentMandate {
        id: Uuid::new_v4(),
        budget_limit: 1000,
        budget_spent: 0,
        risk_class: "High".to_string(),
        allowed_tools: vec![],
    };

    let delegator = A2ADelegator { registry, mandate };
    let result = delegator.delegate("security_audit", 200);

    assert!(result.is_ok());
    let handshake = result.unwrap();
    assert!(handshake.remote_agent.skill_ids.contains(&"security_audit".to_string()));
    assert_eq!(handshake.delegated_mandate.budget_allocated, 200);
}

// Test 2: A2A fails when agent not found
#[test]
fn test_a2a_fails_agent_not_found() {
    let registry = MockAgentRegistry {
        cards: HashMap::new(),
    };
    let mandate = IntentMandate {
        id: Uuid::new_v4(),
        budget_limit: 1000,
        budget_spent: 0,
        risk_class: "High".to_string(),
        allowed_tools: vec![],
    };

    let delegator = A2ADelegator { registry, mandate };
    let result = delegator.delegate("unknown_skill", 200);

    assert!(matches!(result, Err(A2AError::AgentNotFound { .. })));
}

// Test 3: A2A fails when mandate exhausted
#[test]
fn test_a2a_fails_exhausted_mandate() {
    let card = RemoteAgentCard {
        agent_id: Uuid::new_v4(),
        endpoint_url: "https://example.com".to_string(),
        skill_ids: vec!["audit".to_string()],
        auth_scheme: "Bearer".to_string(),
    };

    let mut cards = HashMap::new();
    cards.insert("audit".to_string(), card);

    let registry = MockAgentRegistry { cards };
    let mandate = IntentMandate {
        id: Uuid::new_v4(),
        budget_limit: 1000,
        budget_spent: 1000,
        risk_class: "High".to_string(),
        allowed_tools: vec![],
    };

    let delegator = A2ADelegator { registry, mandate };
    let result = delegator.delegate("audit", 200);

    assert!(matches!(result, Err(A2AError::MandateExhausted)));
}

// Test 4: A2A fails when insufficient budget
#[test]
fn test_a2a_fails_insufficient_budget() {
    let card = RemoteAgentCard {
        agent_id: Uuid::new_v4(),
        endpoint_url: "https://example.com".to_string(),
        skill_ids: vec!["audit".to_string()],
        auth_scheme: "Bearer".to_string(),
    };

    let mut cards = HashMap::new();
    cards.insert("audit".to_string(), card);

    let registry = MockAgentRegistry { cards };
    let mandate = IntentMandate {
        id: Uuid::new_v4(),
        budget_limit: 100,
        budget_spent: 0,
        risk_class: "High".to_string(),
        allowed_tools: vec![],
    };

    let delegator = A2ADelegator { registry, mandate };
    let result = delegator.delegate("audit", 200);

    assert!(matches!(
        result,
        Err(A2AError::InsufficientBudget {
            required: 200,
            available: 100
        })
    ));
}

// Test 5: UCP checkout signs contract
#[test]
fn test_ucp_checkout_signs_contract() {
    let signer = MockSigner;
    let mandate = IntentMandate {
        id: Uuid::new_v4(),
        budget_limit: 1000,
        budget_spent: 0,
        risk_class: "High".to_string(),
        allowed_tools: vec![],
    };

    let mut checkout = UcpCheckout { signer, mandate };

    let contract = UcpContract {
        contract_id: Uuid::new_v4(),
        buyer_agent_id: Uuid::new_v4(),
        seller_agent_id: Uuid::new_v4(),
        skill_id: "security_audit".to_string(),
        agreed_price: 50,
        terms: "Standard security audit with 48-hour turnaround".to_string(),
        created_at: Utc::now(),
    };

    let result = checkout.checkout(contract);

    assert!(result.is_ok());
    let signed = result.unwrap();
    assert_eq!(signed.buyer_signature, vec![0xAA; 64]);
}

// Test 6: UCP checkout fails when price exceeds budget
#[test]
fn test_ucp_checkout_fails_price_exceeds_budget() {
    let signer = MockSigner;
    let mandate = IntentMandate {
        id: Uuid::new_v4(),
        budget_limit: 100,
        budget_spent: 0,
        risk_class: "High".to_string(),
        allowed_tools: vec![],
    };

    let mut checkout = UcpCheckout { signer, mandate };

    let contract = UcpContract {
        contract_id: Uuid::new_v4(),
        buyer_agent_id: Uuid::new_v4(),
        seller_agent_id: Uuid::new_v4(),
        skill_id: "security_audit".to_string(),
        agreed_price: 200,
        terms: "Premium audit".to_string(),
        created_at: Utc::now(),
    };

    let result = checkout.checkout(contract);

    assert!(matches!(
        result,
        Err(UcpError::ContractPriceExceedsBudget { price: 200, budget: 100 })
    ));
}

// Test 7: UCP checkout fails when mandate exhausted
#[test]
fn test_ucp_checkout_fails_exhausted_mandate() {
    let signer = MockSigner;
    let mandate = IntentMandate {
        id: Uuid::new_v4(),
        budget_limit: 1000,
        budget_spent: 1000,
        risk_class: "High".to_string(),
        allowed_tools: vec![],
    };

    let mut checkout = UcpCheckout { signer, mandate };

    let contract = UcpContract {
        contract_id: Uuid::new_v4(),
        buyer_agent_id: Uuid::new_v4(),
        seller_agent_id: Uuid::new_v4(),
        skill_id: "audit".to_string(),
        agreed_price: 50,
        terms: "Standard".to_string(),
        created_at: Utc::now(),
    };

    let result = checkout.checkout(contract);

    assert!(matches!(result, Err(UcpError::MandateExhausted)));
}

// Test 8: A2UI escalation composes card with alert when budget exceeded
#[test]
fn test_a2ui_escalation_budget_exceeded_composes_card_and_alert() {
    let contract = UcpContract {
        contract_id: Uuid::new_v4(),
        buyer_agent_id: Uuid::new_v4(),
        seller_agent_id: Uuid::new_v4(),
        skill_id: "security_audit".to_string(),
        agreed_price: 200,
        terms: "Full security audit".to_string(),
        created_at: Utc::now(),
    };

    let request = EscalationRequest {
        task_id: Uuid::new_v4(),
        contract,
        reason: EscalationReason::BudgetExceeded {
            required: 200,
            available: 100,
        },
    };

    let components = EscalationComposer::compose(&request);

    // Should contain Card + 2 Buttons
    assert!(components.iter().any(|c| matches!(c, A2UIComponent::Card { .. })));
    let button_count = components.iter().filter(|c| matches!(c, A2UIComponent::Button { .. })).count();
    assert_eq!(button_count, 2);

    // Card should contain Alert
    for component in &components {
        if let A2UIComponent::Card { children, .. } = component {
            assert!(children.iter().any(|c| matches!(c, A2UIComponent::Alert { .. })));
        }
    }
}

// Test 9: A2UI escalation card contains contract fields
#[test]
fn test_a2ui_escalation_card_contains_contract_fields() {
    let seller_id = Uuid::new_v4();
    let contract = UcpContract {
        contract_id: Uuid::new_v4(),
        buyer_agent_id: Uuid::new_v4(),
        seller_agent_id: seller_id,
        skill_id: "security_audit".to_string(),
        agreed_price: 150,
        terms: "Full audit with report".to_string(),
        created_at: Utc::now(),
    };

    let request = EscalationRequest {
        task_id: Uuid::new_v4(),
        contract: contract.clone(),
        reason: EscalationReason::HumanApprovalRequired {
            policy: "Executive approval required for audits over 100 units".to_string(),
        },
    };

    let components = EscalationComposer::compose(&request);

    // Find the Card and check its children contain contract details
    for component in &components {
        if let A2UIComponent::Card { children, .. } = component {
            let content: Vec<String> = children
                .iter()
                .filter_map(|c| {
                    if let A2UIComponent::Text { content, .. } = c {
                        Some(content.clone())
                    } else {
                        None
                    }
                })
                .collect();

            // Should contain seller_id, skill, and price info
            assert!(content.iter().any(|s| s.contains(&seller_id.to_string())));
            assert!(content.iter().any(|s| s.contains("security_audit")));
            assert!(content.iter().any(|s| s.contains("150")));
        }
    }
}
