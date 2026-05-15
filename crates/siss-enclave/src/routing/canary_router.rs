use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use tokio::sync::mpsc;

#[derive(Default, Clone)]
pub struct Payload {}

#[derive(Debug, Clone)]
pub struct ShadowInferenceResult {
    pub divergence: f64,
    pub f1_score: f64,
}

#[async_trait::async_trait]
pub trait ShadowAdapter: Send + Sync + 'static {
    async fn evaluate(&self, payload: Arc<Payload>) -> Result<ShadowInferenceResult, String>;
}

pub struct CanaryRouter {
    sender: mpsc::Sender<Arc<Payload>>,
    queue_usage: Arc<AtomicUsize>,
}

impl CanaryRouter {
    pub fn new<A: ShadowAdapter + 'static>(adapter: A, queue_size: usize, timeout_ms: u64) -> Self {
        let (tx, rx) = mpsc::channel(queue_size);
        let queue_usage = Arc::new(AtomicUsize::new(0));
        let queue_usage_clone = Arc::clone(&queue_usage);
        let adapter: Arc<dyn ShadowAdapter> = Arc::new(adapter);

        tokio::spawn(async move {
            Self::background_worker(rx, adapter, timeout_ms, queue_usage_clone).await;
        });

        Self {
            sender: tx,
            queue_usage,
        }
    }

    async fn background_worker(
        mut receiver: mpsc::Receiver<Arc<Payload>>,
        adapter: Arc<dyn ShadowAdapter>,
        timeout_ms: u64,
        queue_usage: Arc<AtomicUsize>,
    ) {
        let timeout_duration = std::time::Duration::from_millis(timeout_ms);

        while let Some(payload) = receiver.recv().await {
            queue_usage.fetch_sub(1, Ordering::Relaxed);

            let adapter_clone = Arc::clone(&adapter);
            let payload_clone = Arc::clone(&payload);

            let _result = tokio::time::timeout(timeout_duration, async move {
                adapter_clone.evaluate(payload_clone).await
            })
            .await;

            // Drop the result, as we're just testing the queue behavior
            // In production, this would send to agent_judge
        }
    }

    /// Returns true if the request was dropped (Fail-Open)
    pub fn route_request(&self, payload: Arc<Payload>) -> bool {
        match self.sender.try_send(payload) {
            Ok(()) => {
                self.queue_usage.fetch_add(1, Ordering::Relaxed);
                false
            }
            Err(mpsc::error::TrySendError::Full(_)) => true,
            Err(mpsc::error::TrySendError::Closed(_)) => true,
        }
    }

    pub fn queue_usage(&self) -> usize {
        self.queue_usage.load(Ordering::Relaxed)
    }
}
