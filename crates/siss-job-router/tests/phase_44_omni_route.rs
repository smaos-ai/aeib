use siss_job_router::attention_budget::{AttentionBudgetEnforcer, ContextEntry};
use siss_job_router::confidence_scorer::RoutingTier;
/// Phase 44: OmniRoute — Saliency-First Routing & Dual-Path Reasoning
/// 8 TDD tests covering:
/// - Dual-Path Orchestration: AP2/RAG always → SLM; token count → LLM (Invariant 1)
/// - Attention Budget (σ⁺): hard caps 2k/4k with ϕ⁺ simplification (Invariant 2)
/// - Smart Cloud Fallback: SLM output validation + gate-failure re-route (Invariant 3)
use siss_job_router::saliency::{SaliencyFeatures, SaliencyScorer};
use siss_job_router::verification_gate::{GateError, VerificationGate};

// ============================================================================
// TEST 1: AP2 task routes to SLM
// ============================================================================

#[test]
fn test_ap2_task_routes_to_slm() {
    let features = SaliencyFeatures {
        estimated_tokens: 150,
        reasoning_depth: 1,
        is_ap2_microtx: true,
        is_rag_fetch: false,
        description: "Process AP2 micro-transaction".to_string(),
    };

    let decision = SaliencyScorer::score(&features);
    assert_eq!(
        decision.primary_tier,
        RoutingTier::Tier1RapidMLX,
        "AP2 microtransaction must route to Tier1RapidMLX"
    );
}

// ============================================================================
// TEST 2: RAG fetch routes to SLM
// ============================================================================

#[test]
fn test_rag_fetch_routes_to_slm() {
    let features = SaliencyFeatures {
        estimated_tokens: 250,
        reasoning_depth: 1,
        is_ap2_microtx: false,
        is_rag_fetch: true,
        description: "Fetch document by ID".to_string(),
    };

    let decision = SaliencyScorer::score(&features);
    assert_eq!(
        decision.primary_tier,
        RoutingTier::Tier1RapidMLX,
        "RAG fetch must route to Tier1RapidMLX"
    );
}

// ============================================================================
// TEST 3: High token count routes to LLM
// ============================================================================

#[test]
fn test_high_token_count_routes_to_llm() {
    let features = SaliencyFeatures {
        estimated_tokens: 500, // exceeds SALIENCY_COMPLEX_THRESHOLD (200)
        reasoning_depth: 1,
        is_ap2_microtx: false,
        is_rag_fetch: false,
        description: "Analyze large dataset".to_string(),
    };

    let decision = SaliencyScorer::score(&features);
    assert_eq!(
        decision.primary_tier,
        RoutingTier::Tier3Opus,
        "High token count must route to Tier3Opus"
    );
}

// ============================================================================
// TEST 4: AP2 overrides high token count
// ============================================================================

#[test]
fn test_ap2_overrides_high_token_count() {
    let features = SaliencyFeatures {
        estimated_tokens: 500, // high, but AP2 pattern wins
        reasoning_depth: 1,
        is_ap2_microtx: true,
        is_rag_fetch: false,
        description: "AP2 transaction with large context".to_string(),
    };

    let decision = SaliencyScorer::score(&features);
    assert_eq!(
        decision.primary_tier,
        RoutingTier::Tier1RapidMLX,
        "AP2 pattern must override high token count and route to Tier1"
    );
}

// ============================================================================
// TEST 5: Budget passes within SLM cap
// ============================================================================

#[test]
fn test_budget_passes_within_slm_cap() {
    let entries = vec![ContextEntry {
        content: "x".repeat(1000), // ~250 tokens
        priority: 100,
    }];

    let result = AttentionBudgetEnforcer::enforce(entries, &RoutingTier::Tier1RapidMLX);
    assert!(result.is_ok(), "1000 chars (~250 tokens) within 2048 cap");
    let context = result.unwrap();
    assert!(!context.simplification_applied, "no simplification needed");
}

// ============================================================================
// TEST 6: Budget triggers simplification at SLM cap
// ============================================================================

#[test]
fn test_budget_triggers_simplification_at_slm_cap() {
    // Create entries that will exceed 2048 token cap when summed
    // 1 token ≈ 4 chars, so 2048 tokens ≈ 8192 chars
    let entries = vec![
        ContextEntry {
            content: "a".repeat(5000), // ~1250 tokens
            priority: 255,             // keep this one
        },
        ContextEntry {
            content: "b".repeat(5000), // ~1250 tokens
            priority: 0,               // drop this one first
        },
    ];

    let result = AttentionBudgetEnforcer::enforce(entries, &RoutingTier::Tier1RapidMLX);
    assert!(
        result.is_ok(),
        "budget enforcement should succeed with simplification"
    );
    let context = result.unwrap();
    assert!(
        context.simplification_applied,
        "should have triggered ϕ⁺ simplification"
    );
    assert!(
        context.tokens_used <= 2048,
        "post-simplification must fit within 2048 cap"
    );
}

// ============================================================================
// TEST 7: Verification gate passes valid JSON
// ============================================================================

#[test]
fn test_verification_gate_passes_valid_json() {
    let valid_json_obj = r#"{"tool":"bash","args":["ls","-la"]}"#;
    let result = VerificationGate::check(valid_json_obj);
    assert!(result.is_ok(), "valid JSON object must pass");

    let valid_json_arr = r#"[1,2,3]"#;
    let result = VerificationGate::check(valid_json_arr);
    assert!(result.is_ok(), "valid JSON array must pass");
}

// ============================================================================
// TEST 8: SLM fallback to frontier on gate failure
// ============================================================================

#[test]
fn test_slm_fallback_to_frontier_on_gate_failure() {
    let invalid_json = "this is not json at all";
    let result = VerificationGate::check(invalid_json);
    assert!(result.is_err(), "malformed output must fail gate");

    if let Err(error) = result {
        assert_eq!(error.raw, invalid_json);
    } else {
        panic!("expected GateError");
    }

    // In integration, this would trigger re-route to Tier3
    // The test here verifies the gate correctly identifies the failure
}
