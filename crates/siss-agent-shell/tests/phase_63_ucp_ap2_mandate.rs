/// Phase 63: UCP & AP2 Cryptographic Mandate Engine — 27 TDD Tests

use siss_agent_shell::ucp_checkout::{
    CartItem, CartRequest, CheckoutError, CheckoutPayload, CheckoutTransport, UcpCheckoutRouter,
};
use siss_agent_shell::ap2_mandate::{Ap2MandateGate, MandateError, PaymentMandate};
use siss_agent_shell::ap2_ledger::{Ap2BurnLedger, BurnError, MandateState};
use siss_agent_shell::hooks::HookResult;
use siss_gatekeeper::signer::MockSigner;
use siss_gatekeeper::tokens::IntentMandate;
use chrono::Utc;
use uuid::Uuid;

// ============================================================================
// HELPERS
// ============================================================================

fn make_cart_item(unit_price: i64, quantity: u32) -> CartItem {
    CartItem {
        item_id: Uuid::new_v4(),
        name: "item".to_string(),
        unit_price,
        quantity,
    }
}

fn make_cart_request(items: Vec<CartItem>, transport: CheckoutTransport) -> CartRequest {
    CartRequest {
        cart_id: Uuid::new_v4(),
        mandate_id: Uuid::new_v4(),
        items,
        transport,
    }
}

fn make_intent_mandate(budget_limit: i64) -> IntentMandate {
    IntentMandate {
        id: Uuid::new_v4(),
        budget_limit,
        budget_spent: 0,
        risk_class: "test".to_string(),
        allowed_tools: vec![],
    }
}

// ============================================================================
// Module 1: UcpCheckoutRouter — 9 Tests
// ============================================================================

#[test]
fn test_checkout_rest_produces_typed_payload() {
    let items = vec![make_cart_item(100, 1)];
    let request = make_cart_request(items, CheckoutTransport::Rest);

    let result = UcpCheckoutRouter::route(request);
    assert!(result.is_ok());
    let payload = result.unwrap();
    assert_eq!(payload.total, 100);
}

#[test]
fn test_checkout_mcp_produces_typed_payload() {
    let items = vec![make_cart_item(100, 1)];
    let request = make_cart_request(items, CheckoutTransport::Mcp);

    let result = UcpCheckoutRouter::route(request);
    assert!(result.is_ok());
    let payload = result.unwrap();
    assert_eq!(payload.total, 100);
}

#[test]
fn test_checkout_a2a_produces_typed_payload() {
    let items = vec![make_cart_item(100, 1)];
    let request = make_cart_request(items, CheckoutTransport::A2a);

    let result = UcpCheckoutRouter::route(request);
    assert!(result.is_ok());
    let payload = result.unwrap();
    assert_eq!(payload.total, 100);
}

#[test]
fn test_checkout_transport_agnostic_identical_payload() {
    let items1 = vec![make_cart_item(100, 1)];
    let items2 = vec![make_cart_item(100, 1)];
    let items3 = vec![make_cart_item(100, 1)];

    let cart_id = Uuid::new_v4();
    let mandate_id = Uuid::new_v4();

    let req_rest = CartRequest {
        cart_id,
        mandate_id,
        items: items1,
        transport: CheckoutTransport::Rest,
    };
    let req_mcp = CartRequest {
        cart_id,
        mandate_id,
        items: items2,
        transport: CheckoutTransport::Mcp,
    };
    let req_a2a = CartRequest {
        cart_id,
        mandate_id,
        items: items3,
        transport: CheckoutTransport::A2a,
    };

    let payload_rest = UcpCheckoutRouter::route(req_rest).unwrap();
    let payload_mcp = UcpCheckoutRouter::route(req_mcp).unwrap();
    let payload_a2a = UcpCheckoutRouter::route(req_a2a).unwrap();

    assert_eq!(payload_rest.total, payload_mcp.total);
    assert_eq!(payload_mcp.total, payload_a2a.total);
    assert_eq!(payload_rest.item_count, payload_mcp.item_count);
}

#[test]
fn test_checkout_empty_cart_returns_error() {
    let request = make_cart_request(vec![], CheckoutTransport::Rest);

    let result = UcpCheckoutRouter::route(request);
    assert!(result.is_err());
    assert!(matches!(result.unwrap_err(), CheckoutError::EmptyCart));
}

#[test]
fn test_checkout_total_is_sum_of_items() {
    let items = vec![make_cart_item(10, 2), make_cart_item(5, 3)];
    let request = make_cart_request(items, CheckoutTransport::Rest);

    let payload = UcpCheckoutRouter::route(request).unwrap();
    assert_eq!(payload.total, 35); // 10*2 + 5*3
}

#[test]
fn test_checkout_item_count_matches_items_vec() {
    let items = vec![
        make_cart_item(10, 1),
        make_cart_item(20, 1),
        make_cart_item(30, 1),
    ];
    let request = make_cart_request(items, CheckoutTransport::Rest);

    let payload = UcpCheckoutRouter::route(request).unwrap();
    assert_eq!(payload.item_count, 3);
}

#[test]
fn test_checkout_mandate_id_preserved() {
    let mandate_id = Uuid::new_v4();
    let items = vec![make_cart_item(100, 1)];

    let request = CartRequest {
        cart_id: Uuid::new_v4(),
        mandate_id,
        items,
        transport: CheckoutTransport::Rest,
    };

    let payload = UcpCheckoutRouter::route(request).unwrap();
    assert_eq!(payload.mandate_id, mandate_id);
}

#[test]
fn test_checkout_cart_id_preserved() {
    let cart_id = Uuid::new_v4();
    let items = vec![make_cart_item(100, 1)];

    let request = CartRequest {
        cart_id,
        mandate_id: Uuid::new_v4(),
        items,
        transport: CheckoutTransport::Rest,
    };

    let payload = UcpCheckoutRouter::route(request).unwrap();
    assert_eq!(payload.cart_id, cart_id);
}

// ============================================================================
// Module 2: Ap2MandateGate — 9 Tests
// ============================================================================

#[test]
fn test_mandate_under_limit_auto_signed() {
    let intent_mandate = make_intent_mandate(1000);
    let gate = Ap2MandateGate {
        signer: MockSigner,
        intent_mandate,
    };

    let (mandate, _) = gate.issue_mandate(Uuid::new_v4(), 500);
    assert!(mandate.signature.is_some());
}

#[test]
fn test_mandate_exactly_at_limit_auto_signed() {
    let intent_mandate = make_intent_mandate(500);
    let gate = Ap2MandateGate {
        signer: MockSigner,
        intent_mandate,
    };

    let (mandate, result) = gate.issue_mandate(Uuid::new_v4(), 500);
    assert!(mandate.signature.is_some());
    assert_eq!(result, HookResult::Continue);
}

#[test]
fn test_mandate_over_limit_unsigned() {
    let intent_mandate = make_intent_mandate(500);
    let gate = Ap2MandateGate {
        signer: MockSigner,
        intent_mandate,
    };

    let (mandate, _) = gate.issue_mandate(Uuid::new_v4(), 501);
    assert!(mandate.signature.is_none());
}

#[test]
fn test_mandate_over_limit_returns_halt() {
    let intent_mandate = make_intent_mandate(500);
    let gate = Ap2MandateGate {
        signer: MockSigner,
        intent_mandate,
    };

    let (_, result) = gate.issue_mandate(Uuid::new_v4(), 501);
    assert!(matches!(result, HookResult::Halt { .. }));
}

#[test]
fn test_mandate_cart_id_bound() {
    let cart_id = Uuid::new_v4();
    let intent_mandate = make_intent_mandate(1000);
    let gate = Ap2MandateGate {
        signer: MockSigner,
        intent_mandate,
    };

    let (mandate, _) = gate.issue_mandate(cart_id, 500);
    assert_eq!(mandate.cart_id, cart_id);
}

#[test]
fn test_mandate_human_approval_sets_signature() {
    let intent_mandate = make_intent_mandate(500);
    let gate = Ap2MandateGate {
        signer: MockSigner,
        intent_mandate,
    };

    let (mandate, _) = gate.issue_mandate(Uuid::new_v4(), 501);
    let human_sig = vec![0xAB; 64];

    let approved = gate.approve_with_signature(mandate, human_sig.clone());
    assert_eq!(approved.signature, Some(human_sig));
}

#[test]
fn test_mandate_signed_authorizes_execution() {
    let intent_mandate = make_intent_mandate(1000);
    let gate = Ap2MandateGate {
        signer: MockSigner,
        intent_mandate,
    };

    let (mandate, _) = gate.issue_mandate(Uuid::new_v4(), 500);
    let result = gate.authorize_execution(&mandate);
    assert_eq!(result, HookResult::Continue);
}

#[test]
fn test_mandate_unsigned_blocks_execution() {
    let intent_mandate = make_intent_mandate(500);
    let gate = Ap2MandateGate {
        signer: MockSigner,
        intent_mandate,
    };

    let (mandate, _) = gate.issue_mandate(Uuid::new_v4(), 501);
    let result = gate.authorize_execution(&mandate);
    assert!(matches!(result, HookResult::Halt { .. }));
}

#[test]
fn test_mandate_exhausted_budget_always_halts() {
    let intent_mandate = make_intent_mandate(0);
    let gate = Ap2MandateGate {
        signer: MockSigner,
        intent_mandate,
    };

    let (_, result) = gate.issue_mandate(Uuid::new_v4(), 1);
    assert!(matches!(result, HookResult::Halt { .. }));
}

// ============================================================================
// Module 3: Ap2BurnLedger — 9 Tests
// ============================================================================

#[test]
fn test_ledger_register_new_entry_succeeds() {
    let mut ledger = Ap2BurnLedger::new();
    let nonce = Uuid::new_v4();
    let mandate_id = Uuid::new_v4();
    let mandate_hash = Ap2BurnLedger::compute_mandate_hash(mandate_id, Uuid::new_v4(), 100);

    let result = ledger.register(mandate_id, nonce, mandate_hash, Utc::now());
    assert!(result.is_ok());
}

#[test]
fn test_ledger_register_duplicate_nonce_fails() {
    let mut ledger = Ap2BurnLedger::new();
    let nonce = Uuid::new_v4();
    let mandate_id = Uuid::new_v4();
    let mandate_hash = Ap2BurnLedger::compute_mandate_hash(mandate_id, Uuid::new_v4(), 100);

    ledger
        .register(mandate_id, nonce, mandate_hash.clone(), Utc::now())
        .unwrap();
    let result = ledger.register(mandate_id, nonce, mandate_hash, Utc::now());
    assert!(matches!(result.unwrap_err(), BurnError::NonceAlreadyBurned { .. }));
}

#[test]
fn test_ledger_entry_state_active_after_register() {
    let mut ledger = Ap2BurnLedger::new();
    let nonce = Uuid::new_v4();
    let mandate_id = Uuid::new_v4();
    let mandate_hash = Ap2BurnLedger::compute_mandate_hash(mandate_id, Uuid::new_v4(), 100);

    ledger.register(mandate_id, nonce, mandate_hash, Utc::now()).ok();
    let entry = ledger.get_entry(nonce);
    assert!(entry.is_some());
    assert_eq!(entry.unwrap().state, MandateState::Active);
}

#[test]
fn test_ledger_burn_transitions_to_executed() {
    let mut ledger = Ap2BurnLedger::new();
    let nonce = Uuid::new_v4();
    let mandate_id = Uuid::new_v4();
    let mandate_hash = Ap2BurnLedger::compute_mandate_hash(mandate_id, Uuid::new_v4(), 100);

    ledger.register(mandate_id, nonce, mandate_hash, Utc::now()).ok();
    ledger.burn(nonce).ok();

    let entry = ledger.get_entry(nonce);
    assert_eq!(entry.unwrap().state, MandateState::Executed);
}

#[test]
fn test_ledger_double_burn_same_nonce_fails() {
    let mut ledger = Ap2BurnLedger::new();
    let nonce = Uuid::new_v4();
    let mandate_id = Uuid::new_v4();
    let mandate_hash = Ap2BurnLedger::compute_mandate_hash(mandate_id, Uuid::new_v4(), 100);

    ledger.register(mandate_id, nonce, mandate_hash, Utc::now()).ok();
    ledger.burn(nonce).ok();

    let result = ledger.burn(nonce);
    assert!(matches!(result.unwrap_err(), BurnError::NonceAlreadyBurned { .. }));
}

#[test]
fn test_ledger_burn_unknown_nonce_returns_not_found() {
    let mut ledger = Ap2BurnLedger::new();
    let result = ledger.burn(Uuid::new_v4());
    assert!(matches!(result.unwrap_err(), BurnError::EntryNotFound { .. }));
}

#[test]
fn test_ledger_is_burned_false_for_unknown() {
    let ledger = Ap2BurnLedger::new();
    assert!(!ledger.is_burned(Uuid::new_v4()));
}

#[test]
fn test_ledger_is_burned_true_after_burn() {
    let mut ledger = Ap2BurnLedger::new();
    let nonce = Uuid::new_v4();
    let mandate_id = Uuid::new_v4();
    let mandate_hash = Ap2BurnLedger::compute_mandate_hash(mandate_id, Uuid::new_v4(), 100);

    ledger.register(mandate_id, nonce, mandate_hash, Utc::now()).ok();
    ledger.burn(nonce).ok();

    assert!(ledger.is_burned(nonce));
}

#[test]
fn test_ledger_mandate_hash_is_deterministic() {
    let mandate_id = Uuid::new_v4();
    let cart_id = Uuid::new_v4();
    let total = 100i64;

    let hash1 = Ap2BurnLedger::compute_mandate_hash(mandate_id, cart_id, total);
    let hash2 = Ap2BurnLedger::compute_mandate_hash(mandate_id, cart_id, total);
    assert_eq!(hash1, hash2);

    let hash3 = Ap2BurnLedger::compute_mandate_hash(mandate_id, cart_id, 200);
    assert_ne!(hash1, hash3);
}
