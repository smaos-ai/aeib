use crate::{HardwareError, Result, Tensor};
use std::sync::{Arc, Mutex};
use tracing::debug;

/// Handle to Neural Engine for async operations
#[derive(Clone)]
pub struct NeuralEngineHandle {
    engine: Arc<NeuralEngine>,
}

impl NeuralEngineHandle {
    pub fn new(engine: Arc<NeuralEngine>) -> Self {
        Self { engine }
    }

    pub async fn accelerate_inference(&self, tensor: &Tensor) -> Result<Tensor> {
        self.engine.accelerate_inference(tensor).await
    }
}

/// Neural Engine on Apple Silicon (e.g., A16, M1-M3)
pub struct NeuralEngine {
    core_count: usize,
    max_inference_batch: usize,
    inference_latency_ms: Arc<Mutex<LatencyTracker>>,
}

struct LatencyTracker {
    operations: Vec<f64>,
    total_ops: u64,
}

impl LatencyTracker {
    fn new() -> Self {
        Self {
            operations: Vec::with_capacity(1024),
            total_ops: 0,
        }
    }

    fn record(&mut self, latency_ms: f64) {
        self.operations.push(latency_ms);
        self.total_ops += 1;
        if self.operations.len() > 1000 {
            self.operations.remove(0);
        }
    }

    fn average_latency(&self) -> f64 {
        if self.operations.is_empty() {
            return 0.0;
        }
        self.operations.iter().sum::<f64>() / self.operations.len() as f64
    }

    fn p99_latency(&self) -> f64 {
        if self.operations.is_empty() {
            return 0.0;
        }
        let mut sorted = self.operations.clone();
        sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        let idx = (sorted.len() as f64 * 0.99).ceil() as usize - 1;
        sorted[idx.min(sorted.len() - 1)]
    }
}

impl NeuralEngine {
    /// Initialize Neural Engine (Apple Neural Engine / ANE)
    pub fn new() -> Result<Self> {
        // Apple Silicon neural engine specs (typical M1/M2/M3)
        const ANE_CORE_COUNT: usize = 16; // Typical for Apple Silicon
        const MAX_BATCH: usize = 64;

        debug!("Initializing Neural Engine with {} cores", ANE_CORE_COUNT);

        Ok(Self {
            core_count: ANE_CORE_COUNT,
            max_inference_batch: MAX_BATCH,
            inference_latency_ms: Arc::new(Mutex::new(LatencyTracker::new())),
        })
    }

    /// Accelerate inference
    pub async fn accelerate_inference(&self, tensor: &Tensor) -> Result<Tensor> {
        let tensor_size = tensor.size();
        if tensor_size == 0 {
            return Err(HardwareError::TensorOperationFailed(
                "Empty tensor".to_string(),
            ));
        }

        let start = std::time::Instant::now();

        // Simulate inference latency: ~30-50ms depending on tensor size
        let simulated_latency_ms = ((tensor_size as f64).log2() * 5.0).min(50.0).max(10.0);
        tokio::time::sleep(tokio::time::Duration::from_millis(
            simulated_latency_ms.ceil() as u64,
        ))
        .await;

        let elapsed_ms = start.elapsed().as_secs_f64() * 1000.0;

        {
            let mut tracker = self.inference_latency_ms.lock().unwrap();
            tracker.record(elapsed_ms);
        }

        debug!(
            "Neural Engine inference completed in {:.2}ms (tensor size: {})",
            elapsed_ms, tensor_size
        );

        Ok(tensor.clone())
    }

    /// Get average inference latency
    pub fn get_average_latency(&self) -> f64 {
        self.inference_latency_ms.lock().unwrap().average_latency()
    }

    /// Get P99 latency
    pub fn get_p99_latency(&self) -> f64 {
        self.inference_latency_ms.lock().unwrap().p99_latency()
    }

    /// Get total operations performed
    pub fn get_total_operations(&self) -> u64 {
        self.inference_latency_ms.lock().unwrap().total_ops
    }

    /// Get core count
    pub fn core_count(&self) -> usize {
        self.core_count
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_neural_engine_creation() {
        let engine = NeuralEngine::new();
        assert!(engine.is_ok());
        let engine = engine.unwrap();
        assert_eq!(engine.core_count(), 16);
    }

    #[tokio::test]
    async fn test_neural_engine_inference() {
        let engine = NeuralEngine::new().unwrap();
        let tensor = Tensor::new(vec![1.0; 256], vec![16, 16]);
        let result = engine.accelerate_inference(&tensor).await;
        assert!(result.is_ok());
        assert_eq!(result.unwrap().size(), 256);
    }

    #[tokio::test]
    async fn test_neural_engine_inference_latency() {
        let engine = NeuralEngine::new().unwrap();
        let tensor = Tensor::new(vec![1.0; 1024], vec![32, 32]);
        let start = std::time::Instant::now();
        let result = engine.accelerate_inference(&tensor).await;
        let elapsed_ms = start.elapsed().as_secs_f64() * 1000.0;

        assert!(result.is_ok());
        assert!(elapsed_ms > 0.0);
        assert!(elapsed_ms < 100.0); // Should be < 100ms
    }

    #[tokio::test]
    async fn test_neural_engine_latency_tracking() {
        let engine = NeuralEngine::new().unwrap();
        let tensor = Tensor::new(vec![1.0; 100], vec![10, 10]);

        // Run multiple inferences
        for _ in 0..10 {
            let _ = engine.accelerate_inference(&tensor).await;
        }

        let avg_latency = engine.get_average_latency();
        assert!(avg_latency > 0.0);
        assert!(avg_latency < 100.0);

        let p99_latency = engine.get_p99_latency();
        assert!(p99_latency >= avg_latency);
    }

    #[tokio::test]
    async fn test_neural_engine_empty_tensor() {
        let engine = NeuralEngine::new().unwrap();
        let tensor = Tensor::new(vec![], vec![0]);
        let result = engine.accelerate_inference(&tensor).await;
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_neural_engine_large_tensor() {
        let engine = NeuralEngine::new().unwrap();
        let large_data = vec![1.0; 1_000_000];
        let tensor = Tensor::new(large_data, vec![1000, 1000]);
        let result = engine.accelerate_inference(&tensor).await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_neural_engine_concurrent_inferences() {
        let engine = Arc::new(NeuralEngine::new().unwrap());
        let mut handles = vec![];

        for i in 0..8 {
            let engine_clone = engine.clone();
            let handle = tokio::spawn(async move {
                let tensor = Tensor::new(vec![i as f32; 256], vec![16, 16]);
                engine_clone.accelerate_inference(&tensor).await
            });
            handles.push(handle);
        }

        for handle in handles {
            let result = handle.await;
            assert!(result.is_ok());
            assert!(result.unwrap().is_ok());
        }
    }

    #[tokio::test]
    async fn test_neural_engine_handle() {
        let engine = Arc::new(NeuralEngine::new().unwrap());
        let handle = NeuralEngineHandle::new(engine);
        let tensor = Tensor::new(vec![1.0; 100], vec![10, 10]);
        let result = handle.accelerate_inference(&tensor).await;
        assert!(result.is_ok());
    }

    #[test]
    fn test_neural_engine_operation_count() {
        let engine = NeuralEngine::new().unwrap();
        assert_eq!(engine.get_total_operations(), 0);
    }
}
