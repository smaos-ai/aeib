use chrono::Utc;
/// Phase 45: AutoResearch & CIPO Evolution Engine
/// 8 TDD tests covering:
/// - Bounds Enforcement (Invariant 2): path whitelist, destructive pattern ban, anti-deletion
/// - Judge Determinism (Invariant 4): function pointer, no side effects, deterministic score
/// - CIPO Trace Capture (Invariant 3): Tier1 → Tier3 escalation emits trace
/// - CIPO Distillation: failure traces → refinement signals
use siss_job_router::auto_research::{
    AutoResearchEngine, BoundsViolation, JudgeInput, JudgeScript, ProgramBounds,
    SandboxedExperiment, TestOutcome, TestTarget,
};
use siss_job_router::cipo::{CipoDistiller, CipoTrace};
use siss_job_router::confidence_scorer::RoutingTier;
use siss_job_router::omni_route::OmniRoute;
use siss_job_router::routing_engine::RoutingDecision;

// ============================================================================
// TEST 1: Bounds allow valid mutation
// ============================================================================

#[test]
fn test_bounds_allow_valid_mutation() {
    let bounds = ProgramBounds {
        allowed_paths: &["crates/siss-job-router/src/"],
        negative_constraints: &["rm -rf"],
        max_iterations: 10,
        self_modification_banned: true,
    };

    let result = SandboxedExperiment::validate_mutation(
        "crates/siss-job-router/src/foo.rs",
        "fn bar() {}",
        &bounds,
    );

    assert!(result.is_ok(), "valid path + safe content should pass");
}

// ============================================================================
// TEST 2: Bounds reject invalid path
// ============================================================================

#[test]
fn test_bounds_reject_invalid_path() {
    let bounds = ProgramBounds {
        allowed_paths: &["crates/siss-job-router/src/"],
        negative_constraints: &[],
        max_iterations: 10,
        self_modification_banned: true,
    };

    let result = SandboxedExperiment::validate_mutation(
        "crates/siss-behavioral-firewall/src/lib.rs",
        "fn bar() {}",
        &bounds,
    );

    assert!(
        matches!(result, Err(BoundsViolation::PathNotAllowed { .. })),
        "path outside allowed_paths should be rejected"
    );
}

// ============================================================================
// TEST 3: Negative constraint blocks rm -rf
// ============================================================================

#[test]
fn test_negative_constraint_blocks_rm_rf() {
    let bounds = ProgramBounds {
        allowed_paths: &["crates/siss-job-router/src/"],
        negative_constraints: &["rm -rf"],
        max_iterations: 10,
        self_modification_banned: true,
    };

    let result = SandboxedExperiment::validate_mutation(
        "crates/siss-job-router/src/foo.rs",
        "let x = \"rm -rf /data\";",
        &bounds,
    );

    assert!(
        matches!(result, Err(BoundsViolation::DestructivePattern { .. })),
        "content with rm -rf should be blocked"
    );
}

// ============================================================================
// TEST 4: Negative constraint blocks DROP TABLE
// ============================================================================

#[test]
fn test_negative_constraint_blocks_drop_table() {
    let bounds = ProgramBounds {
        allowed_paths: &["crates/siss-job-router/src/"],
        negative_constraints: &["DROP TABLE"],
        max_iterations: 10,
        self_modification_banned: true,
    };

    let result = SandboxedExperiment::validate_mutation(
        "crates/siss-job-router/src/foo.rs",
        "DROP TABLE users",
        &bounds,
    );

    assert!(
        matches!(result, Err(BoundsViolation::DestructivePattern { .. })),
        "content with DROP TABLE should be blocked"
    );
}

// ============================================================================
// TEST 5: Empty content blocked
// ============================================================================

#[test]
fn test_empty_content_blocked() {
    let bounds = ProgramBounds {
        allowed_paths: &["crates/siss-job-router/src/"],
        negative_constraints: &[],
        max_iterations: 10,
        self_modification_banned: true,
    };

    let result =
        SandboxedExperiment::validate_mutation("crates/siss-job-router/src/foo.rs", "", &bounds);

    assert!(
        matches!(result, Err(BoundsViolation::EmptyContent)),
        "empty content should be rejected (anti-deletion)"
    );
}

// ============================================================================
// TEST 6: Judge score deterministic
// ============================================================================

#[test]
fn test_judge_score_deterministic() {
    fn my_scorer(input: &JudgeInput) -> f64 {
        input.test_outcomes.iter().filter(|t| t.passed).count() as f64 / 5.0
    }

    let script = JudgeScript {
        score_fn: my_scorer,
    };

    let input = JudgeInput {
        code: "fn foo() {}".to_string(),
        test_outcomes: vec![TestOutcome {
            name: "t1".to_string(),
            passed: true,
        }],
    };

    let s1 = (script.score_fn)(&input);
    let s2 = (script.score_fn)(&input);

    assert_eq!(s1, s2, "same input should produce same score");
}

// ============================================================================
// TEST 7: CIPO trace emitted on SLM failure
// ============================================================================

#[test]
fn test_cipo_trace_emitted_on_slm_failure() {
    let decision = RoutingDecision {
        primary_tier: RoutingTier::Tier1RapidMLX,
        fallback_chain: vec![],
        reason: "test".to_string(),
    };

    let mut sink: Vec<CipoTrace> = vec![];

    // execute_with_fallback_simulation returns non-JSON, gate fails, escalates
    let _result = OmniRoute::execute_with_verification("my_payload", &decision, Some(&mut sink));

    assert_eq!(sink.len(), 1, "should capture one trace on Tier1 failure");
    assert_eq!(
        sink[0].tier_escalated_from,
        RoutingTier::Tier1RapidMLX,
        "escalation should be from Tier1"
    );
    assert_eq!(
        sink[0].tier_escalated_to,
        RoutingTier::Tier3Opus,
        "escalation should be to Tier3"
    );
    assert_eq!(sink[0].payload, "my_payload", "payload should be captured");
}

// ============================================================================
// TEST 8: CIPO distiller produces refinement signal
// ============================================================================

#[test]
fn test_cipo_distiller_produces_refinement_signal() {
    let traces = vec![CipoTrace {
        payload: "test_payload".to_string(),
        slm_output: "bad output".to_string(),
        gate_error_raw: "not valid json".to_string(),
        tier_escalated_from: RoutingTier::Tier1RapidMLX,
        tier_escalated_to: RoutingTier::Tier3Opus,
        timestamp: Utc::now(),
    }];

    let signals = CipoDistiller::distill(&traces);

    assert!(!signals.is_empty(), "should produce at least one signal");
    assert!(signals[0].confidence > 0.0, "confidence should be positive");
    assert!(
        signals[0].lesson.contains("SLM failed"),
        "lesson should mention SLM failure"
    );
    assert_eq!(
        signals[0].source_trace_count, 1,
        "signal should reference 1 source trace"
    );
}
