use siss_agent_shell::types::IntentParams;
/// Phase 31 Skills 2.0 & CIPO-cycle Test Suite
///
/// TDD Red Phase: All 6 tests verify Skills 2.0 integration and CIPO constraint enforcement.
/// Tests cover: skill payload parsing, CIPO context creation, depth/budget verification,
/// multi-step CIPO cycles, and serde round-trip for IntentParams carrying skill context.
use siss_context_cartography::skill::{CipoContext, CipoError, SkillPayload};
use siss_graph_core::node::NodeId;

// ============================================================================
// TEST UTILITIES
// ============================================================================

fn make_skill(name: &str, max_depth: u32, max_budget: u32) -> SkillPayload {
    SkillPayload {
        name: name.to_string(),
        version: "1.0.0".to_string(),
        goal: format!("Test skill: {}", name),
        max_execution_depth: max_depth,
        max_token_budget: max_budget,
    }
}

// ============================================================================
// ACCEPTANCE TESTS (RED PHASE)
// ============================================================================

#[test]
fn test_skill_payload_parses_from_context_cartography() {
    let payload_json = r#"{
        "name": "data-extraction",
        "version": "2.1.0",
        "goal": "Extract structured data",
        "max_execution_depth": 10,
        "max_token_budget": 5000
    }"#;

    let skill = CipoContext::parse_skill_payload(payload_json)
        .expect("should parse valid SKILL.md payload");

    assert_eq!(skill.name, "data-extraction");
    assert_eq!(skill.version, "2.1.0");
    assert_eq!(skill.goal, "Extract structured data");
    assert_eq!(skill.max_execution_depth, 10);
    assert_eq!(skill.max_token_budget, 5000);
}

#[test]
fn test_cipo_context_initial_state_always_passes() {
    let skill = make_skill("test-skill", 5, 100);
    let ctx = CipoContext::new(skill);

    assert_eq!(ctx.depth, 0, "initial depth must be 0");
    assert_eq!(ctx.tokens_consumed, 0, "initial tokens must be 0");
    assert!(
        ctx.verify().is_ok(),
        "initial state must always pass verify()"
    );
}

#[test]
fn test_cipo_context_depth_exceeded_blocks() {
    let skill = make_skill("depth-test", 3, 1000);
    let mut ctx = CipoContext::new(skill);

    ctx.depth = 4;
    let result = ctx.verify();

    assert!(result.is_err(), "depth 4 > max 3 should fail");
    assert_eq!(result.unwrap_err(), CipoError::DepthExceeded);
}

#[test]
fn test_cipo_context_budget_exceeded_blocks() {
    let skill = make_skill("budget-test", 10, 100);
    let mut ctx = CipoContext::new(skill);

    ctx.tokens_consumed = 101;
    let result = ctx.verify();

    assert!(result.is_err(), "tokens 101 > max 100 should fail");
    assert_eq!(result.unwrap_err(), CipoError::BudgetExceeded);
}

#[test]
fn test_cipo_cycle_multi_step_progression() {
    let skill = make_skill("multi-step", 3, 1000);
    let mut ctx = CipoContext::new(skill);

    // Step 1: depth=1, tokens=100 (within bounds)
    ctx.depth = 1;
    ctx.tokens_consumed = 100;
    assert!(
        ctx.verify().is_ok(),
        "step 1: depth 1 <= max 3, tokens 100 <= max 1000"
    );

    // Step 2: depth=2, tokens=200 (within bounds)
    ctx.depth = 2;
    ctx.tokens_consumed = 200;
    assert!(
        ctx.verify().is_ok(),
        "step 2: depth 2 <= max 3, tokens 200 <= max 1000"
    );

    // Step 3: depth=3, tokens=500 (at boundary, within bounds)
    ctx.depth = 3;
    ctx.tokens_consumed = 500;
    assert!(
        ctx.verify().is_ok(),
        "step 3: depth 3 == max 3, tokens 500 <= max 1000"
    );

    // Step 4: depth=4 (exceeds depth bound)
    ctx.depth = 4;
    let result = ctx.verify();
    assert!(
        result.is_err(),
        "step 4: depth 4 > max 3 should fail with DepthExceeded"
    );
    assert_eq!(result.unwrap_err(), CipoError::DepthExceeded);
}

#[test]
fn test_intent_params_carries_skill_context_round_trip() {
    let skill = make_skill("round-trip-test", 7, 2000);
    let params = IntentParams {
        intent: "Test intent with skill context".to_string(),
        requested_tools: vec![NodeId::new()],
        estimated_cost: 100,
        skill_context: Some(skill.clone()),
    };

    // Serialize to JSON
    let json_str = serde_json::to_string(&params).expect("should serialize IntentParams");

    // Deserialize back
    let restored: IntentParams =
        serde_json::from_str(&json_str).expect("should deserialize IntentParams");

    assert_eq!(restored.intent, params.intent);
    assert_eq!(restored.estimated_cost, params.estimated_cost);
    assert!(
        restored.skill_context.is_some(),
        "skill_context must survive round-trip"
    );

    let restored_skill = restored.skill_context.unwrap();
    assert_eq!(restored_skill.name, "round-trip-test");
    assert_eq!(restored_skill.version, "1.0.0");
    assert_eq!(restored_skill.max_execution_depth, 7);
    assert_eq!(restored_skill.max_token_budget, 2000);
}
