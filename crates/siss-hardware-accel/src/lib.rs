mod metal_backend;
mod neural_engine;
mod simd_ops;

pub use metal_backend::{MetalBackend, MetalDevice};
pub use neural_engine::{NeuralEngine, NeuralEngineHandle};
pub use simd_ops::{SimdOps, SimdProofGenerator};

use std::sync::Arc;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum HardwareError {
    #[error("Metal device initialization failed: {0}")]
    MetalInitFailed(String),
    #[error("Neural Engine initialization failed: {0}")]
    NeuralEngineInitFailed(String),
    #[error("GPU memory allocation failed: {0}")]
    MemoryAllocationFailed(String),
    #[error("GPU operation timeout: {0}")]
    OperationTimeout(String),
    #[error("Thermal throttling detected: {0}")]
    ThermalThrottling(String),
    #[error("Concurrent access conflict: {0}")]
    ConcurrencyError(String),
    #[error("Tensor operation failed: {0}")]
    TensorOperationFailed(String),
}

pub type Result<T> = std::result::Result<T, HardwareError>;

/// A Tensor type for GPU operations
#[derive(Clone, Debug)]
pub struct Tensor {
    pub data: Arc<Vec<f32>>,
    pub shape: Vec<usize>,
}

impl Tensor {
    pub fn new(data: Vec<f32>, shape: Vec<usize>) -> Self {
        Self {
            data: Arc::new(data),
            shape,
        }
    }

    pub fn size(&self) -> usize {
        self.shape.iter().product()
    }
}

/// Performance metrics for hardware operations
#[derive(Clone, Debug, PartialEq)]
pub struct PerformanceMetric {
    pub operation: String,
    pub latency_ms: f64,
    pub throughput_ops_per_sec: f64,
    pub memory_usage_mb: f64,
}

#[derive(Clone, Debug)]
pub struct PerformanceReport {
    pub inference_latency_ms: f64,
    pub merkle_proof_latency_ms: f64,
    pub throughput_ops_per_sec: f64,
    pub total_memory_usage_mb: f64,
    pub gpu_utilization_percent: f64,
    pub thermal_status: String,
}

impl Default for PerformanceReport {
    fn default() -> Self {
        Self {
            inference_latency_ms: 0.0,
            merkle_proof_latency_ms: 0.0,
            throughput_ops_per_sec: 0.0,
            total_memory_usage_mb: 0.0,
            gpu_utilization_percent: 0.0,
            thermal_status: "Normal".to_string(),
        }
    }
}

/// Hardware Accelerator: unified interface to Metal, Neural Engine, and SIMD
pub struct HardwareAccelerator {
    metal_backend: Option<Arc<MetalBackend>>,
    neural_engine: Option<Arc<NeuralEngine>>,
    simd_ops: Arc<SimdOps>,
}

impl HardwareAccelerator {
    /// Initialize hardware accelerator with all available backends
    pub async fn new() -> Result<Self> {
        let metal_backend = MetalBackend::new().ok().map(Arc::new);
        let neural_engine = NeuralEngine::new().ok().map(Arc::new);
        let simd_ops = Arc::new(SimdOps::new());

        if metal_backend.is_none() && neural_engine.is_none() {
            return Err(HardwareError::MetalInitFailed(
                "No hardware acceleration backends available".to_string(),
            ));
        }

        Ok(Self {
            metal_backend,
            neural_engine,
            simd_ops,
        })
    }

    /// Accelerate inference using GPU
    pub async fn accelerate_inference(&self, tensor: &Tensor) -> Result<Tensor> {
        if let Some(metal) = &self.metal_backend {
            return metal.accelerate_inference(tensor).await;
        }

        if let Some(ne) = &self.neural_engine {
            return ne.accelerate_inference(tensor).await;
        }

        Err(HardwareError::TensorOperationFailed(
            "No inference backend available".to_string(),
        ))
    }

    /// Accelerate Merkle proof generation
    pub async fn accelerate_merkle_proof(&self, data: &[u8]) -> Result<[u8; 32]> {
        // Try SIMD first for best performance on proofs
        match self.simd_ops.generate_proof(data) {
            Ok(proof) => Ok(proof),
            Err(_) => {
                // Fall back to GPU if SIMD unavailable
                if let Some(metal) = &self.metal_backend {
                    return metal.accelerate_merkle_proof(data).await;
                }
                Err(HardwareError::TensorOperationFailed(
                    "Merkle proof generation failed".to_string(),
                ))
            }
        }
    }

    /// Get performance benchmark report
    pub fn benchmark_performance() -> PerformanceReport {
        PerformanceReport::default()
    }

    /// Check GPU thermal status
    pub fn check_thermal_status(&self) -> Result<String> {
        if let Some(metal) = &self.metal_backend {
            return metal.get_thermal_status();
        }
        Ok("No GPU available".to_string())
    }

    /// Get GPU memory utilization
    pub fn get_memory_utilization(&self) -> Result<f64> {
        if let Some(metal) = &self.metal_backend {
            return metal.get_memory_utilization();
        }
        Ok(0.0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_hardware_accelerator_creation() {
        let accel = HardwareAccelerator::new().await;
        assert!(accel.is_ok());
    }

    #[test]
    fn test_tensor_creation() {
        let data = vec![1.0, 2.0, 3.0, 4.0];
        let tensor = Tensor::new(data, vec![2, 2]);
        assert_eq!(tensor.size(), 4);
    }

    #[test]
    fn test_tensor_shape() {
        let tensor = Tensor::new(vec![1.0, 2.0, 3.0, 4.0, 5.0, 6.0], vec![2, 3]);
        assert_eq!(tensor.shape, vec![2, 3]);
        assert_eq!(tensor.size(), 6);
    }
}
