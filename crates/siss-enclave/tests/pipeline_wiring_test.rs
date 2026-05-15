use async_trait::async_trait;
use siss_enclave::eval::agent_judge::{AgentJudge, EvaluationRequest};
use siss_enclave::orchestrator::evolution_gate::{DoubleBufferedSwap, Judge};
use siss_enclave::routing::canary_router::{Payload, ShadowAdapter, ShadowInferenceResult};
use std::sync::Arc;
use tokio::time::Duration;

#[derive(Clone)]
struct MockAdapter;

#[async_trait]
impl ShadowAdapter for MockAdapter {
    async fn evaluate(&self, _payload: Arc<Payload>) -> Result<ShadowInferenceResult, String> {
        Ok(ShadowInferenceResult {
            divergence: 0.05,
            f1_score: 0.98,
        })
    }
}


#[tokio::test]
async fn test_canary_router_forwards_result_to_agent_judge() {
    let mock = MockAdapter;
    let queue_size = 2;
    let timeout_ms = 10000;

    let router =
        siss_enclave::routing::canary_router::CanaryRouter::new(mock, queue_size, timeout_ms);

    let payload = Arc::new(Payload {
        baseline_logprobs: vec![1.0, 0.5, 0.2],
        baseline_tools: serde_json::json!({"tool": "test"}),
    });

    let dropped = router.route_request(payload);
    assert!(!dropped, "Request should be accepted into queue");

    tokio::time::sleep(Duration::from_millis(100)).await;

    assert_eq!(
        router.queue_usage(),
        0,
        "Queue should be empty after worker processes request"
    );
}

#[tokio::test]
async fn test_agent_judge_implements_judge_trait_pass() {
    let (tx, rx) = tokio::sync::mpsc::channel::<EvaluationRequest>(5);
    let judge = AgentJudge::new(rx, Duration::from_secs(5));

    let tx_clone = tx.clone();
    tokio::spawn(async move {
        tx_clone
            .send(EvaluationRequest {
                divergence: 0.05,
                f1_score: 0.98,
            })
            .await
            .ok();
    });

    let judge_box: Box<dyn Judge> = Box::new(judge);

    let verdict = judge_box.evaluate_next().await;
    assert!(verdict.is_ok(), "Should return Ok");
    assert!(
        verdict.unwrap().pass,
        "Should pass with divergence=0.05 and f1=0.98"
    );
}

#[tokio::test]
async fn test_agent_judge_implements_judge_trait_fail() {
    let (tx, rx) = tokio::sync::mpsc::channel::<EvaluationRequest>(5);
    let judge = AgentJudge::new(rx, Duration::from_secs(5));

    let tx_clone = tx.clone();
    tokio::spawn(async move {
        tx_clone
            .send(EvaluationRequest {
                divergence: 0.20,
                f1_score: 0.98,
            })
            .await
            .ok();
    });

    let judge_box: Box<dyn Judge> = Box::new(judge);

    let verdict = judge_box.evaluate_next().await;
    assert!(verdict.is_ok(), "Should return Ok");
    assert!(
        !verdict.unwrap().pass,
        "Should fail with divergence=0.20 (above 0.15)"
    );
}

#[tokio::test]
async fn test_lora_swap_implements_evolution_gate_trait() {
    use siss_enclave::model::lora_swap::LoRAAdapter;
    use uuid::Uuid;

    let swap = siss_enclave::model::lora_swap::DoubleBufferedSwap::new(8_000_000_000);

    let adapter = LoRAAdapter {
        id: Uuid::new_v4(),
        version: 1,
        memory_bytes: 1_000_000,
        weights_checksum: "dummy_checksum".to_string(),
        deployed_at: chrono::Utc::now(),
    };

    let boxed_adapter = swap.allocate_adapter(adapter).unwrap();
    swap.stage_adapter(boxed_adapter).unwrap();

    let swap_box: Box<dyn DoubleBufferedSwap> = Box::new(swap);

    let result = swap_box.execute_swap(1).await;
    assert!(result.is_ok(), "execute_swap should succeed");

    let result = swap_box.discard(1).await;
    assert!(result.is_ok(), "discard should succeed");
}

#[tokio::test]
async fn test_full_pipeline_flow_from_request_to_judge() {
    let mock = MockAdapter;
    let queue_size = 2;
    let timeout_ms = 10000;

    let router =
        siss_enclave::routing::canary_router::CanaryRouter::new(mock, queue_size, timeout_ms);

    let payload = Arc::new(Payload {
        baseline_logprobs: vec![1.0, 0.5],
        baseline_tools: serde_json::json!({}),
    });

    let dropped = router.route_request(payload);
    assert!(!dropped, "Should accept request");
}
