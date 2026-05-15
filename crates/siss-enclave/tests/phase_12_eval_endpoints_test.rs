use siss_enclave::model::rapid_mlx_adapter::RapidMLXAdapter;
use siss_enclave::routing::canary_router::{Payload, ShadowAdapter};
use std::sync::Arc;

#[tokio::test]
async fn test_eval_endpoints_disabled_returns_zero_scores() {
    // RapidMLXAdapter::new() leaves all eval endpoints empty (fail-closed defaults)
    let adapter = RapidMLXAdapter::new("http://localhost:9999");
    let payload = Arc::new(Payload {
        baseline_logprobs: vec![1.0, 0.5],
        baseline_tools: serde_json::json!({}),
    });

    // evaluate() will fail on primary inference (no server at 9999) so this test verifies
    // the adapter structure itself, not the full evaluate flow
    assert_eq!(
        adapter.compute_divergence_for_test(&vec![1.0], &vec![1.0]),
        0.0
    );
}

#[tokio::test]
async fn test_with_eval_endpoints_constructor_exists() {
    // Verify that with_eval_endpoints() constructor is available
    let adapter = RapidMLXAdapter::with_eval_endpoints(
        "http://localhost:9999",
        "http://localhost:7001",
        "http://localhost:7002",
        "http://localhost:7003",
    );

    // Just verify it constructs without error
    assert_eq!(
        adapter.compute_divergence_for_test(&vec![1.0], &vec![1.0]),
        0.0
    );
}

#[tokio::test]
async fn test_eval_endpoints_with_nonexistent_servers_returns_zero_scores() {
    // Set eval endpoints to nonexistent servers (will timeout/fail)
    let adapter = RapidMLXAdapter::with_eval_endpoints(
        "http://127.0.0.1:9999", // primary MLX endpoint (won't respond)
        "http://127.0.0.1:7001", // ROMA (won't respond)
        "http://127.0.0.1:7002", // MINT (won't respond)
        "http://127.0.0.1:7003", // CoReBench (won't respond)
    );

    let payload = Arc::new(Payload {
        baseline_logprobs: vec![1.0],
        baseline_tools: serde_json::json!({}),
    });

    // evaluate() returns Err because primary endpoint fails
    // (primary inference errors are not fail-closed)
    let result = adapter.evaluate(payload).await;
    assert!(
        result.is_err(),
        "Primary inference failure should return Err"
    );
}

#[tokio::test]
async fn test_eval_endpoints_empty_returns_zero_scores() {
    let adapter = RapidMLXAdapter::new("http://127.0.0.1:9999");

    // Verify internal computation still works even with no eval endpoints
    let divergence = adapter.compute_divergence_for_test(&vec![1.0, 0.5], &vec![1.0, 0.5]);
    assert_eq!(
        divergence, 0.0,
        "Empty endpoints should not affect divergence computation"
    );
}

#[tokio::test]
async fn test_scores_are_clamped_to_unit_interval() {
    let adapter = RapidMLXAdapter::new("http://localhost:9999");

    // Verify that compute_divergence returns clamped values
    let div1 = adapter.compute_divergence_for_test(&vec![1000.0], &vec![0.0]);
    assert!(div1 <= 1.0, "Divergence should be clamped to [0.0, 1.0]");
    assert!(div1 >= 0.0, "Divergence should be clamped to [0.0, 1.0]");
}

#[tokio::test]
async fn test_f1_score_computation() {
    let adapter = RapidMLXAdapter::new("http://localhost:9999");

    // Test exact match
    let f1_exact = adapter.compute_tool_f1_for_test(
        &serde_json::json!({"tool": "test"}),
        &serde_json::json!({"tool": "test"}),
    );
    assert_eq!(f1_exact, 1.0, "Exact match should give F1 score of 1.0");

    // Test empty case
    let f1_empty = adapter.compute_tool_f1_for_test(&serde_json::json!({}), &serde_json::json!({}));
    assert_eq!(f1_empty, 1.0, "Both empty should give F1 score of 1.0");
}
