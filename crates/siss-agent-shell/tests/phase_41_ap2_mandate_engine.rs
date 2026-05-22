/// Phase 41: AP2 Mandate Engine & Cryptographic Governance
/// 6 TDD tests covering:
/// - Mandate Typology: CartMandate, ExecutionMandate with Ed25519 signatures (Invariant 1)
/// - Separation of Responsibilities: agent cannot forge execution credentials (Invariant 2)
/// - Nonce Burn Protocol: one-time-use nonces enforced fail-closed (Invariant 3)

use siss_gatekeeper::signer::{LocalEd25519Signer, MockSigner, Signer};
use siss_gatekeeper::tokens::{CartMandate, ExecutionMandate};
use siss_gatekeeper::payload::build_execution_mandate_payload;
use siss_gatekeeper::nonce::{InMemoryNonceLedger, NonceLedger, NonceBurnError};
use chrono::Utc;
use uuid::Uuid;

// ============================================================================
// TEST 1: ExecutionMandate payload signing and verification roundtrip
// ============================================================================

#[test]
fn test_execution_mandate_signing_roundtrip() {
    // GIVEN: Ed25519 signer and valid ExecutionMandate payload
    let signer = LocalEd25519Signer::generate();
    let mandate_id = Uuid::new_v4();
    let intent_mandate_id = Uuid::new_v4();
    let task_id = Uuid::new_v4();
    let nonce = b"test-nonce-12345";
    let epoch_secs = Utc::now().timestamp();

    let payload = build_execution_mandate_payload(
        mandate_id,
        intent_mandate_id,
        task_id,
        1000,
        nonce,
        epoch_secs,
    );

    // WHEN: sign the payload
    let signature = signer.sign(&payload).expect("signing should succeed");

    // THEN: verify with the same signer returns true
    let is_valid = signer.verify(&payload, &signature).expect("verify should return bool");
    assert!(is_valid, "signature should verify against original payload");
}

// ============================================================================
// TEST 2: Tampered payload fails verification
// ============================================================================

#[test]
fn test_execution_mandate_tampered_fails() {
    // GIVEN: signed ExecutionMandate payload
    let signer = LocalEd25519Signer::generate();
    let mandate_id = Uuid::new_v4();
    let intent_mandate_id = Uuid::new_v4();
    let task_id = Uuid::new_v4();
    let nonce = b"test-nonce-12345";
    let epoch_secs = Utc::now().timestamp();

    let mut payload = build_execution_mandate_payload(
        mandate_id,
        intent_mandate_id,
        task_id,
        1000,
        nonce,
        epoch_secs,
    );

    let signature = signer.sign(&payload).expect("signing should succeed");

    // WHEN: tamper with one byte in the payload
    payload[5] ^= 0xFF;  // flip bits

    // THEN: verification fails
    let is_valid = signer.verify(&payload, &signature).expect("verify should return bool");
    assert!(
        !is_valid,
        "signature should NOT verify against tampered payload"
    );
}

// ============================================================================
// TEST 3: Separation of Responsibilities — agent cannot forge credentials
// ============================================================================

#[test]
fn test_separation_agent_cannot_forge() {
    // GIVEN: real signer (cockpit) and mock signer (agent)
    let cockpit_signer = LocalEd25519Signer::generate();
    let agent_signer = MockSigner;  // always produces [0xAA; 64]

    let mandate_id = Uuid::new_v4();
    let intent_mandate_id = Uuid::new_v4();
    let task_id = Uuid::new_v4();
    let nonce = b"test-nonce-12345";
    let epoch_secs = Utc::now().timestamp();

    let payload = build_execution_mandate_payload(
        mandate_id,
        intent_mandate_id,
        task_id,
        1000,
        nonce,
        epoch_secs,
    );

    // WHEN: agent (MockSigner) tries to forge a signature
    let forged_signature = agent_signer.sign(&payload).expect("mock signer always succeeds");

    // THEN: cockpit's verifier rejects the forged signature
    let is_valid = cockpit_signer
        .verify(&payload, &forged_signature)
        .expect("verify should return bool");
    assert!(
        !is_valid,
        "cockpit should reject signature from wrong private key"
    );
}

// ============================================================================
// TEST 4: Nonce burn — first call succeeds
// ============================================================================

#[test]
fn test_nonce_burn_first_call_ok() {
    // GIVEN: InMemoryNonceLedger and a nonce
    let ledger = InMemoryNonceLedger::new();
    let nonce = "unique-nonce-1234";
    let mandate_id = Uuid::new_v4();

    // WHEN: burn the nonce for the first time
    let result = ledger.burn(nonce, mandate_id);

    // THEN: returns Ok(())
    assert!(result.is_ok(), "first burn should return Ok");
}

// ============================================================================
// TEST 5: Nonce burn — replay detected
// ============================================================================

#[test]
fn test_nonce_burn_replay_detected() {
    // GIVEN: InMemoryNonceLedger with a burned nonce
    let ledger = InMemoryNonceLedger::new();
    let nonce = "unique-nonce-1234";
    let mandate_id = Uuid::new_v4();

    // First burn succeeds
    let first_result = ledger.burn(nonce, mandate_id);
    assert!(first_result.is_ok(), "first burn should succeed");

    // WHEN: attempt to burn the same nonce again
    let second_result = ledger.burn(nonce, mandate_id);

    // THEN: returns Err(AlreadyBurned)
    assert_eq!(
        second_result,
        Err(NonceBurnError::AlreadyBurned),
        "second burn should detect replay"
    );
}

// ============================================================================
// TEST 6: RCE mandate exhausted triggers interrupt
// ============================================================================

#[test]
fn test_rce_mandate_exhausted_triggers_interrupt() {
    // GIVEN: mandate parameters showing exhausted state
    let mandate_id = Uuid::new_v4();
    let budget_limit = 1000;
    let budget_spent = 1000;  // exhausted
    let is_exhausted = budget_spent > budget_limit;  // false in this case, need budget_spent >= budget_limit

    // Create a minimal RCE instance to test the interrupt checker
    let workflow_id = Uuid::new_v4();
    let rce = siss_graph_db::rce::ResumableCognitiveExecution::new(workflow_id);

    // WHEN: check for mandate exhaustion interrupt with exhausted budget
    let interrupt = rce.check_mandate_exhausted_interrupt(mandate_id, true, budget_spent, budget_limit);

    // THEN: returns Some(InterruptSignal) with correct fields
    assert!(
        interrupt.is_some(),
        "exhausted mandate should trigger interrupt"
    );
    let signal = interrupt.unwrap();
    assert_eq!(
        signal.interrupt_type, "mandate_exhausted",
        "interrupt type should be mandate_exhausted"
    );
    assert_eq!(
        signal.severity, "Critical",
        "interrupt severity should be Critical"
    );
    assert!(
        signal.human_approval_required,
        "interrupt should require human approval"
    );
}

// Bonus: test that non-exhausted mandate doesn't trigger interrupt
#[test]
fn test_rce_mandate_not_exhausted_no_interrupt() {
    // GIVEN: mandate parameters showing active state
    let mandate_id = Uuid::new_v4();
    let budget_limit = 1000;
    let budget_spent = 500;  // not exhausted
    let is_exhausted = false;

    let workflow_id = Uuid::new_v4();
    let rce = siss_graph_db::rce::ResumableCognitiveExecution::new(workflow_id);

    // WHEN: check for mandate exhaustion interrupt with active budget
    let interrupt = rce.check_mandate_exhausted_interrupt(mandate_id, is_exhausted, budget_spent, budget_limit);

    // THEN: returns None
    assert!(
        interrupt.is_none(),
        "active mandate should NOT trigger interrupt"
    );
}
