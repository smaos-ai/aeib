/// Phase 42: Swarm Orchestration & A2A Communication
/// 8 TDD tests covering:
/// - Collision Resistance: WorktreeClaimLedger atomic claim/release (Invariant 1)
/// - Cryptographic Inheritance: DelegatedMandate budget/tool bounds (Invariant 2)
/// - Channel Schema Validation: SwarmMessage validation (Invariant 3)
/// - Database-Backed State Sync: SwarmStateLedger idempotent upsert (Invariant 4)
use siss_agent_shell::swarm_channel::{
    ClaimError, InMemoryClaimLedger, InMemorySwarmState, SwarmChannel, SwarmMessage,
    SwarmStateLedger, WorktreeClaimLedger,
};
use siss_gatekeeper::delegation::{DelegatedMandate, DelegationError};
use siss_gatekeeper::tokens::IntentMandate;
use uuid::Uuid;

// ============================================================================
// TEST 1: Collision Resistance — first claim succeeds
// ============================================================================

#[test]
fn test_collision_first_claim_succeeds() {
    // GIVEN: InMemoryClaimLedger and a worktree/file pair
    let ledger = InMemoryClaimLedger::new();
    let worktree = "wt_001";
    let file = "src/main.rs";
    let agent_a = Uuid::new_v4();

    // WHEN: agent A claims the file
    let result = ledger.claim(worktree, file, agent_a);

    // THEN: returns Ok(())
    assert!(result.is_ok(), "first claim should succeed");
}

// ============================================================================
// TEST 2: Collision Resistance — second claim fails
// ============================================================================

#[test]
fn test_collision_second_claim_fails() {
    // GIVEN: InMemoryClaimLedger with a claimed file
    let ledger = InMemoryClaimLedger::new();
    let worktree = "wt_001";
    let file = "src/main.rs";
    let agent_a = Uuid::new_v4();
    let agent_b = Uuid::new_v4();

    // First claim succeeds
    let first_result = ledger.claim(worktree, file, agent_a);
    assert!(first_result.is_ok(), "first claim should succeed");

    // WHEN: agent B attempts to claim the same file
    let second_result = ledger.claim(worktree, file, agent_b);

    // THEN: returns Err(AlreadyClaimed) with agent_a as holder
    match second_result {
        Err(ClaimError { held_by }) => assert_eq!(held_by, agent_a),
        _ => panic!("expected ClaimError"),
    }
}

// ============================================================================
// TEST 3: Collision Resistance — different files in same worktree independent
// ============================================================================

#[test]
fn test_collision_different_files_independent() {
    // GIVEN: InMemoryClaimLedger and a worktree with two files
    let ledger = InMemoryClaimLedger::new();
    let worktree = "wt_001";
    let file_a = "src/main.rs";
    let file_b = "src/lib.rs";
    let agent_a = Uuid::new_v4();
    let agent_b = Uuid::new_v4();

    // WHEN: agent A claims file_a, agent B claims file_b
    let claim_a = ledger.claim(worktree, file_a, agent_a);
    let claim_b = ledger.claim(worktree, file_b, agent_b);

    // THEN: both succeed (no collision)
    assert!(claim_a.is_ok(), "claim on file_a should succeed");
    assert!(claim_b.is_ok(), "claim on file_b should succeed");
}

// ============================================================================
// TEST 4: Cryptographic Inheritance — delegation within budget succeeds
// ============================================================================

#[test]
fn test_mandate_delegation_within_budget() {
    // GIVEN: parent IntentMandate with budget_remaining=500
    let parent = IntentMandate {
        id: Uuid::new_v4(),
        budget_limit: 1000,
        budget_spent: 500,
        allowed_tools: vec![Uuid::new_v4(), Uuid::new_v4()],
        risk_class: "low".to_string(),
    };

    let allowed_tools = vec![parent.allowed_tools[0]]; // subset of parent
    let budget_limit = 400; // less than parent.budget_remaining() = 500

    // WHEN: create delegated mandate
    let result = DelegatedMandate::from_parent(&parent, allowed_tools, budget_limit, 1);

    // THEN: returns Ok
    assert!(result.is_ok(), "delegation within budget should succeed");
}

// ============================================================================
// TEST 5: Cryptographic Inheritance — delegation exceeding budget fails
// ============================================================================

#[test]
fn test_mandate_delegation_exceeds_budget() {
    // GIVEN: parent IntentMandate with budget_remaining=500
    let parent = IntentMandate {
        id: Uuid::new_v4(),
        budget_limit: 1000,
        budget_spent: 500,
        allowed_tools: vec![Uuid::new_v4()],
        risk_class: "low".to_string(),
    };

    let allowed_tools = vec![parent.allowed_tools[0]];
    let budget_limit = 501; // exceeds parent.budget_remaining()

    // WHEN: attempt to create delegated mandate
    let result = DelegatedMandate::from_parent(&parent, allowed_tools, budget_limit, 1);

    // THEN: returns Err(BudgetExceeded)
    assert!(
        matches!(result, Err(DelegationError::BudgetExceeded { .. })),
        "delegation exceeding budget should fail"
    );
}

// ============================================================================
// TEST 6: Cryptographic Inheritance — unauthorized tool rejected
// ============================================================================

#[test]
fn test_mandate_delegation_unauthorized_tool() {
    // GIVEN: parent IntentMandate with specific allowed_tools
    let parent = IntentMandate {
        id: Uuid::new_v4(),
        budget_limit: 1000,
        budget_spent: 500,
        allowed_tools: vec![Uuid::new_v4()], // only one tool allowed
        risk_class: "low".to_string(),
    };

    let unauthorized_tool = Uuid::new_v4(); // not in parent.allowed_tools
    let allowed_tools = vec![unauthorized_tool];
    let budget_limit = 100;

    // WHEN: attempt to delegate with unauthorized tool
    let result = DelegatedMandate::from_parent(&parent, allowed_tools, budget_limit, 1);

    // THEN: returns Err(UnauthorizedTool)
    assert!(
        matches!(result, Err(DelegationError::UnauthorizedTool(_))),
        "delegation with unauthorized tool should fail"
    );
}

// ============================================================================
// TEST 7: Channel Schema Validation — invalid progress rejected
// ============================================================================

#[test]
fn test_channel_invalid_progress_rejected() {
    // GIVEN: SwarmChannel
    let channel = SwarmChannel::with_capacity(10);

    // WHEN: attempt to broadcast StatusUpdate with invalid progress_pct (101)
    let msg = SwarmMessage::StatusUpdate {
        agent_id: Uuid::new_v4(),
        state: "executing".to_string(),
        progress_pct: 101, // invalid: must be 0-100
    };

    let result = channel.broadcast(msg);

    // THEN: returns Err(SchemaMismatch)
    assert!(
        result.is_err(),
        "broadcast with invalid progress should fail"
    );
}

// ============================================================================
// TEST 8: Database-Backed State Sync — idempotent upsert
// ============================================================================

#[test]
fn test_swarm_state_idempotent_upsert() {
    // GIVEN: InMemorySwarmState
    let ledger = InMemorySwarmState::new();
    let agent_id = Uuid::new_v4();

    // WHEN: update state twice with same agent_id
    let first_update = ledger.update_state(agent_id, "initializing", 10);
    let second_update = ledger.update_state(agent_id, "executing", 50);

    // THEN: both succeed, second overwrites first
    assert!(first_update.is_ok(), "first update should succeed");
    assert!(second_update.is_ok(), "second update should succeed");

    let final_state = ledger.get_state(agent_id);
    assert!(final_state.is_some(), "state should exist");
    let snapshot = final_state.unwrap();
    assert_eq!(
        snapshot.state, "executing",
        "second update should overwrite first"
    );
    assert_eq!(
        snapshot.progress, 50,
        "progress should be from second update"
    );
}
