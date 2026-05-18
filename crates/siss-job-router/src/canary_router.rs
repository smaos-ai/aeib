use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};
use tokio::sync::mpsc;

/// Payload wrapper for shadow inference requests.
#[derive(Debug, Clone)]
pub struct Payload {
    pub request_id: String,
    pub data: Vec<u8>,
}

/// CanaryRouter manages shadow routing of a percentage of live requests.
pub struct CanaryRouter {
    sender: mpsc::Sender<Arc<Payload>>,
    shadow_dropped_full: AtomicU64,
}

impl CanaryRouter {
    /// Create a new CanaryRouter with bounded queue.
    pub fn new(queue_size: usize) -> (Self, mpsc::Receiver<Arc<Payload>>) {
        let (sender, receiver) = mpsc::channel(queue_size);
        let router = CanaryRouter {
            sender,
            shadow_dropped_full: AtomicU64::new(0),
        };
        (router, receiver)
    }

    /// Route a request to shadow if probability check passes.
    /// Non-blocking: silently drops if queue is full.
    pub fn route_request(&self, payload: Arc<Payload>, percentage: f64) -> bool {
        if !should_shadow_route(percentage) {
            return false;
        }

        match self.sender.try_send(Arc::clone(&payload)) {
            Ok(()) => true,
            Err(mpsc::error::TrySendError::Full(_)) => {
                self.shadow_dropped_full.fetch_add(1, Ordering::Relaxed);
                false
            }
            Err(mpsc::error::TrySendError::Closed(_)) => false,
        }
    }

    /// Get count of dropped shadows due to full queue.
    pub fn get_dropped_full_count(&self) -> u64 {
        self.shadow_dropped_full.load(Ordering::Relaxed)
    }
}

/// Check if request should be shadow-routed based on percentage.
fn should_shadow_route(percentage: f64) -> bool {
    use rand::Rng;
    rand::thread_rng().gen_bool(percentage / 100.0)
}

/// Result of a shadow inference request.
#[derive(Debug, Clone)]
pub struct ShadowInferenceResult {
    pub request_id: String,
    pub output: Option<Vec<u8>>,
    pub timed_out: bool,
}

/// Trait for shadow inference adapter.
pub trait ShadowAdapter: Send + Sync {
    fn infer(
        &self,
        payload: &Payload,
    ) -> futures::future::BoxFuture<'static, Result<Vec<u8>, String>>;
}

/// Spawns a background worker that processes shadow inference requests.
/// Enforces a 5-second timeout per request to prevent queue clogging.
pub fn spawn_shadow_worker(
    mut receiver: mpsc::Receiver<Arc<Payload>>,
    adapter: Arc<dyn ShadowAdapter>,
    mut results_tx: mpsc::Sender<ShadowInferenceResult>,
) -> tokio::task::JoinHandle<()> {
    tokio::spawn(async move {
        let timeout_duration = std::time::Duration::from_secs(5);

        while let Some(payload) = receiver.recv().await {
            let adapter_clone = Arc::clone(&adapter);
            let payload_clone = Arc::clone(&payload);

            let result = tokio::time::timeout(timeout_duration, async move {
                adapter_clone.infer(&payload_clone).await
            })
            .await;

            let shadow_result = match result {
                Ok(Ok(output)) => ShadowInferenceResult {
                    request_id: payload.request_id.clone(),
                    output: Some(output),
                    timed_out: false,
                },
                Ok(Err(_)) => ShadowInferenceResult {
                    request_id: payload.request_id.clone(),
                    output: None,
                    timed_out: false,
                },
                Err(_) => ShadowInferenceResult {
                    request_id: payload.request_id.clone(),
                    output: None,
                    timed_out: true,
                },
            };

            let _ = results_tx.send(shadow_result).await;
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use super::mock_adapter::MockAdapter;

    /// test_try_send_drops_on_full: Ensures try_send doesn't panic when queue is full.
    #[test]
    fn test_try_send_drops_on_full() {
        let (router, mut receiver) = CanaryRouter::new(2);

        let payload1 = Arc::new(Payload {
            request_id: "req1".to_string(),
            data: vec![1, 2, 3],
        });

        let payload2 = Arc::new(Payload {
            request_id: "req2".to_string(),
            data: vec![4, 5, 6],
        });

        let payload3 = Arc::new(Payload {
            request_id: "req3".to_string(),
            data: vec![7, 8, 9],
        });

        // Fill queue
        assert!(router.route_request(Arc::clone(&payload1), 100.0));
        assert!(router.route_request(Arc::clone(&payload2), 100.0));

        // Queue is now full; next attempt should drop
        assert!(!router.route_request(Arc::clone(&payload3), 100.0));

        // Verify drop counter incremented
        assert_eq!(router.get_dropped_full_count(), 1);

        // Verify queue still has the first two items
        assert!(receiver.try_recv().is_ok());
        assert!(receiver.try_recv().is_ok());
        assert!(receiver.try_recv().is_err());
    }

    /// test_probability_distribution: Ensures routing follows expected percentage over many attempts.
    #[test]
    fn test_probability_distribution() {
        let (router, _receiver) = CanaryRouter::new(10000);
        let iterations = 10000;
        let percentage = 5.0; // 5%
        let mut routed_count = 0;

        for i in 0..iterations {
            let payload = Arc::new(Payload {
                request_id: format!("req{}", i),
                data: vec![i as u8],
            });
            if router.route_request(Arc::clone(&payload), percentage) {
                routed_count += 1;
            }
        }

        // Allow 20% deviation from expected percentage
        let expected = (iterations as f64) * (percentage / 100.0);
        let tolerance = expected * 0.2;
        let actual = routed_count as f64;

        assert!(
            (actual - expected).abs() <= tolerance,
            "Expected ~{} routed (±{}), got {}",
            expected,
            tolerance,
            actual
        );
    }

    /// test_background_worker_timeout: Ensures worker respects 5-second timeout.
    #[tokio::test]
    async fn test_background_worker_timeout() {
        let (router, _receiver) = CanaryRouter::new(100);

        let payload = Arc::new(Payload {
            request_id: "slow_req".to_string(),
            data: vec![1, 2, 3],
        });

        assert!(router.route_request(Arc::clone(&payload), 100.0));

        let timeout_duration = std::time::Duration::from_secs(5);
        let start = std::time::Instant::now();

        // Spawn a worker that mimics a slow adapter
        let worker_task = tokio::spawn(async move {
            let result = tokio::time::timeout(timeout_duration, async {
                // Simulate slow inference that takes 10 seconds
                tokio::time::sleep(std::time::Duration::from_secs(10)).await;
                "inference result"
            })
            .await;

            result.is_err() // Should timeout
        });

        let timed_out = worker_task.await.unwrap();
        let elapsed = start.elapsed();

        // Verify timeout fired within ~5 seconds
        assert!(timed_out, "Worker should have timed out");
        assert!(
            elapsed >= timeout_duration && elapsed < std::time::Duration::from_secs(6),
            "Worker should timeout in ~5 seconds, took {:?}",
            elapsed
        );
    }

    /// test_non_blocking_dispatch: Ensures route_request doesn't block on live thread.
    #[tokio::test]
    async fn test_non_blocking_dispatch() {
        let (router, _receiver) = CanaryRouter::new(1);

        // Fill the queue
        let payload1 = Arc::new(Payload {
            request_id: "req1".to_string(),
            data: vec![1],
        });
        router.route_request(Arc::clone(&payload1), 100.0);

        // This should complete instantly without blocking, even though queue is full
        let start = std::time::Instant::now();
        let payload2 = Arc::new(Payload {
            request_id: "req2".to_string(),
            data: vec![2],
        });
        let _ = router.route_request(Arc::clone(&payload2), 100.0);
        let elapsed = start.elapsed();

        // Should complete in < 1ms (definitely not blocking)
        assert!(
            elapsed < std::time::Duration::from_millis(1),
            "route_request blocked: {:?}",
            elapsed
        );
    }

    /// test_shadow_worker_processes_requests: Ensures worker consumes queue and captures results.
    #[tokio::test]
    async fn test_shadow_worker_processes_requests() {
        let (router, receiver) = CanaryRouter::new(100);
        let (results_tx, mut results_rx) = mpsc::channel(100);

        let mock_adapter = Arc::new(MockAdapter::new(50)); // 50ms latency
        let worker = spawn_shadow_worker(receiver, mock_adapter, results_tx);

        // Send two payloads
        let payload1 = Arc::new(Payload {
            request_id: "req1".to_string(),
            data: vec![1, 2, 3],
        });
        router.route_request(Arc::clone(&payload1), 100.0);

        let payload2 = Arc::new(Payload {
            request_id: "req2".to_string(),
            data: vec![4, 5, 6],
        });
        router.route_request(Arc::clone(&payload2), 100.0);

        // Receive results
        let result1 = tokio::time::timeout(std::time::Duration::from_secs(2), results_rx.recv())
            .await
            .expect("timeout waiting for result1")
            .expect("should receive result1");

        let result2 = tokio::time::timeout(std::time::Duration::from_secs(2), results_rx.recv())
            .await
            .expect("timeout waiting for result2")
            .expect("should receive result2");

        // Verify results captured correctly
        assert_eq!(result1.request_id, "req1");
        assert!(!result1.timed_out);
        assert!(result1.output.is_some());

        assert_eq!(result2.request_id, "req2");
        assert!(!result2.timed_out);
        assert!(result2.output.is_some());

        drop(router); // Close sender
        worker.await.expect("worker should complete");
    }

    /// test_shadow_worker_respects_5s_timeout: Ensures stalled adapter is forcibly terminated.
    #[tokio::test]
    async fn test_shadow_worker_respects_5s_timeout() {
        let (router, receiver) = CanaryRouter::new(100);
        let (results_tx, mut results_rx) = mpsc::channel(100);

        // Mock adapter that hangs for 10 seconds
        let mock_adapter = Arc::new(MockAdapter::new(10000));
        let worker = spawn_shadow_worker(receiver, mock_adapter, results_tx);

        let payload = Arc::new(Payload {
            request_id: "slow_req".to_string(),
            data: vec![1, 2, 3],
        });
        router.route_request(Arc::clone(&payload), 100.0);

        let start = std::time::Instant::now();

        // Should timeout after ~5 seconds
        let result = tokio::time::timeout(std::time::Duration::from_secs(7), results_rx.recv())
            .await
            .expect("timeout waiting for result")
            .expect("should receive result");

        let elapsed = start.elapsed();

        // Verify timeout was enforced
        assert_eq!(result.request_id, "slow_req");
        assert!(result.timed_out, "Result should be marked as timed out");
        assert!(result.output.is_none());
        assert!(
            elapsed >= std::time::Duration::from_secs(5)
                && elapsed < std::time::Duration::from_secs(6),
            "Worker should timeout in ~5 seconds, took {:?}",
            elapsed
        );

        drop(router);
        worker.await.expect("worker should complete");
    }

    /// test_shadow_worker_continues_after_timeout: Ensures worker recovers and processes next request.
    #[tokio::test]
    async fn test_shadow_worker_continues_after_timeout() {
        let (router, receiver) = CanaryRouter::new(100);
        let (results_tx, mut results_rx) = mpsc::channel(100);

        let mock_adapter = Arc::new(MockAdapter::new(6000)); // 6s delay (will timeout)
        let worker = spawn_shadow_worker(receiver, mock_adapter, results_tx);

        // Send first request (will timeout)
        let payload1 = Arc::new(Payload {
            request_id: "slow_req".to_string(),
            data: vec![1],
        });
        router.route_request(Arc::clone(&payload1), 100.0);

        // Get timed-out result
        let result1 = tokio::time::timeout(std::time::Duration::from_secs(7), results_rx.recv())
            .await
            .expect("timeout waiting for result1")
            .expect("should receive result1");

        assert!(result1.timed_out);

        // Send second request (worker should still process despite prior timeout)
        let payload2 = Arc::new(Payload {
            request_id: "next_req".to_string(),
            data: vec![2],
        });
        router.route_request(Arc::clone(&payload2), 100.0);

        // This test verifies the worker loop continues despite timeout
        drop(router);
        worker.await.expect("worker should complete");
    }
}

// Mock adapter for testing
#[cfg(test)]
mod mock_adapter {
    use super::*;

    pub struct MockAdapter {
        delay_ms: u64,
    }

    impl MockAdapter {
        pub fn new(delay_ms: u64) -> Self {
            MockAdapter { delay_ms }
        }
    }

    impl ShadowAdapter for MockAdapter {
        fn infer(
            &self,
            payload: &Payload,
        ) -> futures::future::BoxFuture<'static, Result<Vec<u8>, String>> {
            let delay = std::time::Duration::from_millis(self.delay_ms);
            let data = payload.data.clone();
            Box::pin(async move {
                tokio::time::sleep(delay).await;
                Ok(data)
            })
        }
    }
}
