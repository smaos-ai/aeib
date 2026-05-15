use siss_enclave::model::rapid_mlx_adapter::RapidMLXAdapter;
use siss_enclave::routing::canary_router::{Payload, ShadowAdapter};
use std::sync::Arc;

#[test]
fn test_rapid_mlx_adapter_compute_divergence_identical_logprobs() {
    let adapter = RapidMLXAdapter::new("http://localhost:8000/v1/chat/completions");

    let shadow = vec![1.0, 0.5, 0.2];
    let baseline = vec![1.0, 0.5, 0.2];

    let divergence = adapter.compute_divergence_for_test(&shadow, &baseline);
    assert_eq!(divergence, 0.0, "identical logprobs should have 0 divergence");
}

#[test]
fn test_rapid_mlx_adapter_compute_divergence_different_logprobs() {
    let adapter = RapidMLXAdapter::new("http://localhost:8000/v1/chat/completions");

    let shadow = vec![1.0, 0.5, 0.2];
    let baseline = vec![2.0, 1.5, 1.2];

    let divergence = adapter.compute_divergence_for_test(&shadow, &baseline);
    assert!(divergence > 0.0, "different logprobs should have positive divergence");
    assert!(divergence <= 1.0, "divergence should be in [0, 1]");
}

#[test]
fn test_rapid_mlx_adapter_compute_f1_identical_tools() {
    let adapter = RapidMLXAdapter::new("http://localhost:8000/v1/chat/completions");

    let tools1 = serde_json::json!({
        "name": "calculator",
        "args": {"a": 2, "b": 3}
    });
    let tools2 = serde_json::json!({
        "name": "calculator",
        "args": {"a": 2, "b": 3}
    });

    let f1 = adapter.compute_tool_f1_for_test(&tools1, &tools2);
    assert_eq!(f1, 1.0, "identical tools should have F1=1.0");
}

#[test]
fn test_rapid_mlx_adapter_compute_f1_different_tools() {
    let adapter = RapidMLXAdapter::new("http://localhost:8000/v1/chat/completions");

    let tools1 = serde_json::json!({"name": "search", "args": "query1"});
    let tools2 = serde_json::json!({"name": "calculator", "args": "2+3"});

    let f1 = adapter.compute_tool_f1_for_test(&tools1, &tools2);
    assert!(f1 >= 0.0 && f1 <= 1.0, "F1 score should be in [0, 1]");
}

#[tokio::test]
async fn test_rapid_mlx_adapter_handles_network_errors_gracefully() {
    let adapter = RapidMLXAdapter::new("http://localhost:9999/v1/chat/completions");

    let payload = Arc::new(Payload {
        baseline_logprobs: vec![1.0, 0.5],
        baseline_tools: serde_json::json!({ "tools": [] }),
    });

    let result = adapter.evaluate(payload).await;
    // Should fail gracefully with error message, not panic
    assert!(result.is_err(), "Network error should return Err");
    let err = result.unwrap_err();
    assert!(err.contains("HTTP") || err.contains("error"), "Error message should indicate HTTP issue");
}
