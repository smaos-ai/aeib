use async_trait::async_trait;
use siss_enclave::routing::canary_router::{
    CanaryRouter, Payload, ShadowAdapter, ShadowInferenceResult,
};
use std::sync::Arc;
use std::time::Duration;
use tokio::time::Instant;

#[derive(Clone)]
struct ChaosMockAdapter {
    hang: bool,
    delay_ms: u64,
    inject_error: bool,
}

#[async_trait]
impl ShadowAdapter for ChaosMockAdapter {
    async fn evaluate(&self, _payload: Arc<Payload>) -> Result<ShadowInferenceResult, String> {
        if self.hang {
            tokio::time::sleep(Duration::from_secs(30)).await;
        } else if self.delay_ms > 0 {
            tokio::time::sleep(Duration::from_millis(self.delay_ms)).await;
        }

        if self.inject_error {
            return Err("Chaos mock injected error".to_string());
        }

        Ok(ShadowInferenceResult {
            divergence: 0.0,
            f1_score: 1.0,
        })
    }
}

#[tokio::test]
async fn test_live_thread_drops_shadows_under_queue_pressure_without_blocking() {
    // 1. Setup adapter with 100ms delay to force queue buildup
    let mock = ChaosMockAdapter {
        hang: false,
        delay_ms: 100,
        inject_error: false,
    };

    // Queue capacity = 2 to ensure we can send multiple requests before queue fills
    let router = CanaryRouter::new(mock, 2, 10000);

    let start = Instant::now();

    // Rapid-fire send 5 requests while worker processes first one (100ms)
    let dropped_1 = router.route_request(Arc::new(Payload {
        baseline_logprobs: vec![],
        baseline_tools: serde_json::json!({}),
    }));
    let dropped_2 = router.route_request(Arc::new(Payload {
        baseline_logprobs: vec![],
        baseline_tools: serde_json::json!({}),
    }));
    let dropped_3 = router.route_request(Arc::new(Payload {
        baseline_logprobs: vec![],
        baseline_tools: serde_json::json!({}),
    }));
    let dropped_4 = router.route_request(Arc::new(Payload {
        baseline_logprobs: vec![],
        baseline_tools: serde_json::json!({}),
    }));
    let dropped_5 = router.route_request(Arc::new(Payload {
        baseline_logprobs: vec![],
        baseline_tools: serde_json::json!({}),
    }));

    let elapsed = start.elapsed();

    // ASSERTIONS
    eprintln!(
        "Dropped: [{}, {}, {}, {}, {}]",
        dropped_1, dropped_2, dropped_3, dropped_4, dropped_5
    );
    assert!(
        elapsed < Duration::from_millis(5),
        "Live thread was blocked! Elapsed: {:?}",
        elapsed
    );
    // First two requests should fit in the queue (capacity 2)
    assert_eq!(dropped_1, false, "Request 1 should be accepted");
    assert_eq!(
        dropped_2, false,
        "Request 2 should be accepted (queue capacity 2)"
    );
    // Requests 3+ should be dropped (queue is full)
    assert_eq!(dropped_3, true, "Request 3 MUST be dropped (queue full)");
    assert_eq!(dropped_4, true, "Request 4 MUST be dropped (queue full)");
    assert_eq!(dropped_5, true, "Request 5 MUST be dropped (queue full)");
}

#[tokio::test]
async fn test_worker_respects_timeout_and_recovers() {
    // 1. Setup adapter to hang indefinitely
    let mock = ChaosMockAdapter {
        hang: true,
        delay_ms: 0,
        inject_error: false,
    };

    // 2. Set an aggressive 50ms timeout for the test to keep the suite fast
    let router = CanaryRouter::new(mock, 5, 50);

    router.route_request(Arc::new(Payload {
        baseline_logprobs: vec![],
        baseline_tools: serde_json::json!({}),
    }));

    // Wait enough time for the 50ms timeout to trip inside the worker
    tokio::time::sleep(Duration::from_millis(75)).await;

    // ASSERTION: The queue should be empty because the worker dropped the hung request
    // and is ready for the next one, proving instantaneous recovery.
    assert_eq!(
        router.queue_usage(),
        0,
        "Queue should be empty after timeout"
    );
}
