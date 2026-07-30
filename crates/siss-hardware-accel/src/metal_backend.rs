use crate::{HardwareError, Result, Tensor};
use std::sync::{Arc, Mutex};
use tracing::{debug, warn};

/// Metal GPU device wrapper
pub struct MetalDevice {
    device_id: usize,
    memory_pool: Arc<Mutex<MemoryPool>>,
    thermal_threshold_celsius: f64,
}

struct MemoryPool {
    allocated_bytes: usize,
    max_bytes: usize,
    allocations: Vec<AllocationInfo>,
}

struct AllocationInfo {
    size: usize,
    timestamp: std::time::Instant,
}

impl MetalDevice {
    fn new(device_id: usize) -> Self {
        const DEFAULT_GPU_MEMORY_MB: usize = 8192; // 8GB for typical Apple Neural Engine
        Self {
            device_id,
            memory_pool: Arc::new(Mutex::new(MemoryPool {
                allocated_bytes: 0,
                max_bytes: DEFAULT_GPU_MEMORY_MB * 1024 * 1024,
                allocations: Vec::new(),
            })),
            thermal_threshold_celsius: 80.0,
        }
    }

    fn allocate(&self, size: usize) -> Result<()> {
        let mut pool = self.memory_pool.lock().unwrap();
        if pool.allocated_bytes + size > pool.max_bytes {
            return Err(HardwareError::MemoryAllocationFailed(format!(
                "Cannot allocate {} bytes, only {} available",
                size,
                pool.max_bytes - pool.allocated_bytes
            )));
        }
        pool.allocated_bytes += size;
        pool.allocations.push(AllocationInfo {
            size,
            timestamp: std::time::Instant::now(),
        });
        debug!("Allocated {} bytes on Metal device {}", size, self.device_id);
        Ok(())
    }

    fn deallocate(&self, size: usize) {
        let mut pool = self.memory_pool.lock().unwrap();
        if pool.allocated_bytes >= size {
            pool.allocated_bytes -= size;
            pool.allocations.retain(|a| a.timestamp.elapsed().as_secs() > 0);
        }
    }

    fn get_memory_usage(&self) -> f64 {
        let pool = self.memory_pool.lock().unwrap();
        pool.allocated_bytes as f64 / (1024.0 * 1024.0) // Convert to MB
    }
}

/// Metal backend for GPU acceleration
pub struct MetalBackend {
    device: Arc<MetalDevice>,
    is_initialized: bool,
    inference_cache: Arc<Mutex<InferenceCache>>,
}

struct InferenceCache {
    cache_size: usize,
    max_cache_size: usize,
}

impl MetalBackend {
    /// Initialize Metal backend
    pub fn new() -> Result<Self> {
        let device = Arc::new(MetalDevice::new(0));
        debug!("Initializing Metal backend on device 0");

        Ok(Self {
            device,
            is_initialized: true,
            inference_cache: Arc::new(Mutex::new(InferenceCache {
                cache_size: 0,
                max_cache_size: 512 * 1024 * 1024, // 512MB cache
            })),
        })
    }

    /// Accelerate inference on tensor
    pub async fn accelerate_inference(&self, tensor: &Tensor) -> Result<Tensor> {
        if !self.is_initialized {
            return Err(HardwareError::MetalInitFailed(
                "Metal backend not initialized".to_string(),
            ));
        }

        let tensor_size = tensor.size() * std::mem::size_of::<f32>();
        self.device.allocate(tensor_size)?;

        // Simulate GPU computation with time
        let start = std::time::Instant::now();

        // Simulate latency: ~50ms for inference
        tokio::time::sleep(tokio::time::Duration::from_millis(
            (tensor.size() as u64).min(50),
        ))
        .await;

        let elapsed = start.elapsed().as_secs_f64() * 1000.0; // Convert to ms
        debug!(
            "Metal inference completed in {:.2}ms for tensor size {}",
            elapsed, tensor.size()
        );

        self.device.deallocate(tensor_size);

        // Return processed tensor (simple copy for now)
        Ok(tensor.clone())
    }

    /// Accelerate Merkle proof generation
    pub async fn accelerate_merkle_proof(&self, data: &[u8]) -> Result<[u8; 32]> {
        if !self.is_initialized {
            return Err(HardwareError::MetalInitFailed(
                "Metal backend not initialized".to_string(),
            ));
        }

        self.device.allocate(data.len())?;

        let start = std::time::Instant::now();

        // Simulate GPU Merkle tree computation
        tokio::time::sleep(tokio::time::Duration::from_micros(500)).await;

        let elapsed = start.elapsed().as_secs_f64() * 1000.0;
        debug!(
            "Metal Merkle proof generated in {:.4}ms for {} bytes",
            elapsed,
            data.len()
        );

        self.device.deallocate(data.len());

        // Compute hash using sha2 as fallback
        use sha2::{Digest, Sha256};
        let mut hasher = Sha256::new();
        hasher.update(data);
        let result = hasher.finalize();

        let mut proof = [0u8; 32];
        proof.copy_from_slice(&result[..32]);
        Ok(proof)
    }

    /// Get thermal status
    pub fn get_thermal_status(&self) -> Result<String> {
        // Simulate thermal sensor reading
        let memory_mb = self.device.get_memory_usage();
        let estimated_temp = 40.0 + (memory_mb / 100.0).min(40.0);

        if estimated_temp > self.device.thermal_threshold_celsius {
            warn!("GPU approaching thermal threshold: {:.1}C", estimated_temp);
            Ok(format!("WARNING: {:.1}C", estimated_temp))
        } else {
            Ok(format!("Normal: {:.1}C", estimated_temp))
        }
    }

    /// Get GPU memory utilization
    pub fn get_memory_utilization(&self) -> Result<f64> {
        let pool = self.device.memory_pool.lock().unwrap();
        let utilization = (pool.allocated_bytes as f64 / pool.max_bytes as f64) * 100.0;
        Ok(utilization)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_metal_device_creation() {
        let device = MetalDevice::new(0);
        assert_eq!(device.device_id, 0);
        assert_eq!(device.get_memory_usage(), 0.0);
    }

    #[test]
    fn test_metal_device_memory_allocation() {
        let device = MetalDevice::new(0);
        let alloc_size = 1024 * 1024; // 1MB
        assert!(device.allocate(alloc_size).is_ok());
        assert!(device.get_memory_usage() >= 1.0);
    }

    #[test]
    fn test_metal_device_memory_deallocation() {
        let device = MetalDevice::new(0);
        let alloc_size = 1024 * 1024;
        device.allocate(alloc_size).unwrap();
        let usage_before = device.get_memory_usage();
        device.deallocate(alloc_size);
        let usage_after = device.get_memory_usage();
        assert!(usage_after < usage_before);
    }

    #[tokio::test]
    async fn test_metal_backend_creation() {
        let backend = MetalBackend::new();
        assert!(backend.is_ok());
    }

    #[tokio::test]
    async fn test_metal_backend_inference() {
        let backend = MetalBackend::new().unwrap();
        let tensor = Tensor::new(vec![1.0, 2.0, 3.0, 4.0], vec![2, 2]);
        let result = backend.accelerate_inference(&tensor).await;
        assert!(result.is_ok());
        assert_eq!(result.unwrap().size(), 4);
    }

    #[tokio::test]
    async fn test_metal_backend_merkle_proof() {
        let backend = MetalBackend::new().unwrap();
        let data = b"test data for merkle proof";
        let result = backend.accelerate_merkle_proof(data).await;
        assert!(result.is_ok());
        assert_eq!(result.unwrap().len(), 32);
    }

    #[tokio::test]
    async fn test_metal_backend_concurrent_access() {
        let backend = Arc::new(MetalBackend::new().unwrap());
        let mut handles = vec![];

        for i in 0..4 {
            let backend_clone = backend.clone();
            let handle = tokio::spawn(async move {
                let tensor = Tensor::new(vec![i as f32; 100], vec![10, 10]);
                backend_clone.accelerate_inference(&tensor).await
            });
            handles.push(handle);
        }

        for handle in handles {
            let result = handle.await;
            assert!(result.is_ok());
            assert!(result.unwrap().is_ok());
        }
    }

    #[test]
    fn test_metal_thermal_status() {
        let backend = MetalBackend::new().unwrap();
        let status = backend.get_thermal_status();
        assert!(status.is_ok());
    }

    #[test]
    fn test_metal_memory_utilization() {
        let backend = MetalBackend::new().unwrap();
        let utilization = backend.get_memory_utilization().unwrap();
        assert!(utilization >= 0.0);
        assert!(utilization <= 100.0);
    }
}
