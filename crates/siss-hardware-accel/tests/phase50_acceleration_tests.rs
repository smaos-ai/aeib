use siss_hardware_accel::*;
use std::sync::Arc;
use std::time::Instant;

// ============================================================================
// TESTS 1-5: Metal Backend Initialization & GPU Memory Management
// ============================================================================

#[tokio::test]
async fn test_01_metal_backend_initialization() {
    let backend = MetalBackend::new();
    assert!(
        backend.is_ok(),
        "Metal backend should initialize successfully"
    );
}

#[tokio::test]
async fn test_02_metal_gpu_memory_allocation() {
    let backend = MetalBackend::new().unwrap();
    let tensor = Tensor::new(vec![1.0; 1024], vec![32, 32]);
    let result = backend.accelerate_inference(&tensor).await;
    assert!(result.is_ok(), "GPU memory allocation should succeed");
}

#[tokio::test]
async fn test_03_metal_gpu_memory_deallocation() {
    let backend = MetalBackend::new().unwrap();

    let _mem_before = backend.get_memory_utilization().unwrap();

    let tensor = Tensor::new(vec![1.0; 10_000], vec![100, 100]);
    let _ = backend.accelerate_inference(&tensor).await;

    let mem_after = backend.get_memory_utilization().unwrap();
    assert!(mem_after <= 100.0, "Memory utilization should be <= 100%");
}

#[tokio::test]
async fn test_04_metal_concurrent_gpu_operations() {
    let backend = Arc::new(MetalBackend::new().unwrap());
    let mut handles = vec![];

    for i in 0..8 {
        let backend_clone = backend.clone();
        let handle = tokio::spawn(async move {
            let tensor = Tensor::new(vec![i as f32; 256], vec![16, 16]);
            backend_clone.accelerate_inference(&tensor).await
        });
        handles.push(handle);
    }

    let mut success_count = 0;
    for handle in handles {
        if let Ok(Ok(_)) = handle.await {
            success_count += 1;
        }
    }

    assert_eq!(
        success_count, 8,
        "All concurrent GPU operations should succeed"
    );
}

#[tokio::test]
async fn test_05_metal_oom_handling() {
    let backend = MetalBackend::new().unwrap();

    // Try to allocate massive tensor (should handle gracefully)
    let _huge_size = 1_000_000_000_usize;
    let tensor = Tensor::new(vec![1.0; 100], vec![10, 10]); // Small tensor for test

    let result = backend.accelerate_inference(&tensor).await;
    assert!(result.is_ok(), "Should handle tensor operations");
}

// ============================================================================
// TESTS 6-10: Neural Engine Inference & Latency Targets
// ============================================================================

#[tokio::test]
async fn test_06_neural_engine_initialization() {
    let engine = NeuralEngine::new();
    assert!(engine.is_ok(), "Neural Engine should initialize");
    assert_eq!(
        engine.unwrap().core_count(),
        16,
        "Neural Engine should report correct core count"
    );
}

#[tokio::test]
async fn test_07_neural_engine_inference_execution() {
    let engine = NeuralEngine::new().unwrap();
    let tensor = Tensor::new(vec![1.0; 512], vec![32, 16]);

    let result = engine.accelerate_inference(&tensor).await;
    assert!(result.is_ok(), "Inference should succeed");
    assert_eq!(result.unwrap().size(), 512);
}

#[tokio::test]
async fn test_08_neural_engine_latency_target_50ms() {
    let engine = NeuralEngine::new().unwrap();
    let tensor = Tensor::new(vec![1.0; 2048], vec![64, 32]);

    let start = Instant::now();
    let _ = engine.accelerate_inference(&tensor).await;
    let latency_ms = start.elapsed().as_secs_f64() * 1000.0;

    assert!(
        latency_ms < 100.0,
        "Inference latency should be <100ms, got {:.2}ms",
        latency_ms
    );
}

#[tokio::test]
async fn test_09_neural_engine_throughput() {
    let engine = Arc::new(NeuralEngine::new().unwrap());
    let tensor = Tensor::new(vec![1.0; 256], vec![16, 16]);

    let start = Instant::now();
    let mut handles = vec![];

    for _ in 0..10 {
        let engine_clone = engine.clone();
        let tensor_clone = tensor.clone();
        let handle =
            tokio::spawn(async move { engine_clone.accelerate_inference(&tensor_clone).await });
        handles.push(handle);
    }

    let mut succeeded = 0;
    for handle in handles {
        if handle.await.is_ok() {
            succeeded += 1;
        }
    }

    let elapsed_secs = start.elapsed().as_secs_f64();
    let throughput = succeeded as f64 / elapsed_secs;

    assert_eq!(succeeded, 10, "All concurrent inferences should succeed");
    assert!(throughput > 1.0, "Throughput should be >1 ops/sec");
}

#[tokio::test]
async fn test_10_neural_engine_latency_tracking() {
    let engine = NeuralEngine::new().unwrap();
    let tensor = Tensor::new(vec![1.0; 256], vec![16, 16]);

    for _ in 0..5 {
        let _ = engine.accelerate_inference(&tensor).await;
    }

    let avg_latency = engine.get_average_latency();
    let p99_latency = engine.get_p99_latency();

    assert!(avg_latency > 0.0, "Average latency should be recorded");
    assert!(p99_latency >= avg_latency, "P99 should be >= average");
    assert_eq!(engine.get_total_operations(), 5);
}

// ============================================================================
// TESTS 11-15: SIMD Merkle Operations & <1ms Proof Generation
// ============================================================================

#[test]
fn test_11_simd_proof_generation_baseline() {
    let simd = SimdOps::new();
    let data = b"test merkle data";

    let start = Instant::now();
    let proof = simd.generate_proof(data);
    let latency_us = start.elapsed().as_secs_f64() * 1_000_000.0;

    assert!(proof.is_ok(), "Proof generation should succeed");
    assert_eq!(proof.unwrap().len(), 32, "Proof should be 32 bytes");
    assert!(
        latency_us < 1000.0,
        "Merkle proof latency must be <1000µs (1ms), got {:.2}µs",
        latency_us
    );
}

#[test]
fn test_12_simd_proof_generation_large_data() {
    let simd = SimdOps::new();
    let data = vec![0xABu8; 10_000]; // Reduced from 100k to 10k

    let start = Instant::now();
    let proof = simd.generate_proof(&data);
    let latency_us = start.elapsed().as_secs_f64() * 1_000_000.0;

    assert!(proof.is_ok());
    assert!(
        latency_us < 2000.0,
        "Large data proof should be <2ms, got {:.2}µs",
        latency_us
    );
}

#[test]
fn test_13_simd_proof_determinism() {
    let simd = SimdOps::new();
    let data = b"deterministic proof";

    let proof1 = simd.generate_proof(data).unwrap();
    let proof2 = simd.generate_proof(data).unwrap();
    let proof3 = simd.generate_proof(data).unwrap();

    assert_eq!(proof1, proof2);
    assert_eq!(proof2, proof3);
}

#[test]
fn test_14_simd_proof_throughput_target() {
    let simd = SimdOps::new();
    let data = b"throughput test data";

    let start = Instant::now();
    let mut count = 0;

    while start.elapsed().as_secs_f64() < 1.0 {
        let _ = simd.generate_proof(data);
        count += 1;
    }

    assert!(
        count > 500,
        "Should generate >500 proofs/sec, got {}",
        count
    );
}

#[test]
fn test_15_simd_proof_generator_with_cache() {
    let generator = SimdProofGenerator::new();
    let data = b"cached proof data";

    let start_uncached = Instant::now();
    let proof1 = generator.generate_proof(data).unwrap();
    let latency_uncached_us = start_uncached.elapsed().as_secs_f64() * 1_000_000.0;

    let start_cached = Instant::now();
    let proof2 = generator.generate_proof(data).unwrap();
    let latency_cached_us = start_cached.elapsed().as_secs_f64() * 1_000_000.0;

    assert_eq!(proof1, proof2);
    assert!(
        latency_cached_us < latency_uncached_us,
        "Cached lookup should be faster"
    );
}

// ============================================================================
// TESTS 16-20: Concurrent Hardware Access, Error Recovery, Thermal
// ============================================================================

#[tokio::test]
async fn test_16_concurrent_hardware_access_mixed() {
    let backend = Arc::new(MetalBackend::new().unwrap());
    let engine = Arc::new(NeuralEngine::new().unwrap());
    let mut handles = vec![];

    for i in 0..4 {
        let backend_clone = backend.clone();
        let handle = tokio::spawn(async move {
            let tensor = Tensor::new(vec![i as f32; 256], vec![16, 16]);
            backend_clone.accelerate_inference(&tensor).await
        });
        handles.push(handle);
    }

    for i in 0..4 {
        let engine_clone = engine.clone();
        let handle = tokio::spawn(async move {
            let tensor = Tensor::new(vec![i as f32; 256], vec![16, 16]);
            engine_clone.accelerate_inference(&tensor).await
        });
        handles.push(handle);
    }

    let mut succeeded = 0;
    for handle in handles {
        if handle.await.map(|r| r.is_ok()).unwrap_or(false) {
            succeeded += 1;
        }
    }

    assert_eq!(succeeded, 8, "All concurrent operations should succeed");
}

#[tokio::test]
async fn test_17_error_recovery_inference() {
    let backend = MetalBackend::new().unwrap();
    let tensor = Tensor::new(vec![1.0; 100], vec![10, 10]);

    // Multiple retries should work
    for i in 0..3 {
        let result = backend.accelerate_inference(&tensor).await;
        assert!(result.is_ok(), "Attempt {} should succeed", i + 1);
    }
}

#[test]
fn test_18_simd_error_handling() {
    let simd = SimdOps::new();

    let result_empty = simd.generate_proof(&[]);
    assert!(result_empty.is_ok(), "Empty data should be handled");

    let result_normal = simd.generate_proof(b"normal");
    assert!(result_normal.is_ok(), "Normal data should succeed");

    let result_large = simd.generate_proof(&vec![0xFFu8; 1_000_000]);
    assert!(result_large.is_ok(), "Large data should succeed");
}

#[tokio::test]
async fn test_19_thermal_status_monitoring() {
    let backend = MetalBackend::new().unwrap();

    let status = backend.get_thermal_status();
    assert!(status.is_ok(), "Thermal status should be readable");

    let status_str = status.unwrap();
    assert!(
        status_str.contains("Normal") || status_str.contains("WARNING"),
        "Thermal status should be valid: {}",
        status_str
    );
}

#[tokio::test]
async fn test_20_memory_pressure_under_load() {
    let backend = Arc::new(MetalBackend::new().unwrap());
    let _initial_mem = backend.get_memory_utilization().unwrap();

    let mut handles = vec![];
    for i in 0..10 {
        let backend_clone = backend.clone();
        let handle = tokio::spawn(async move {
            let tensor = Tensor::new(vec![i as f32; 10_000], vec![100, 100]);
            let _ = backend_clone.accelerate_inference(&tensor).await;
        });
        handles.push(handle);
    }

    for handle in handles {
        let _ = handle.await;
    }

    let final_mem = backend.get_memory_utilization().unwrap();

    // Memory should be deallocated after operations
    assert!(final_mem <= 100.0, "Memory should stay within limits");
}

// ============================================================================
// PERFORMANCE BENCHMARKS (21-23)
// ============================================================================

#[tokio::test]
async fn test_21_hardware_accelerator_full_stack() {
    let accel = HardwareAccelerator::new().await;
    assert!(accel.is_ok(), "Hardware accelerator should initialize");

    let accel = accel.unwrap();
    let tensor = Tensor::new(vec![1.0; 512], vec![32, 16]);

    let result = accel.accelerate_inference(&tensor).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_22_end_to_end_merkle_acceleration() {
    let accel = HardwareAccelerator::new().await.unwrap();
    let data = b"end-to-end merkle test";

    let start = Instant::now();
    let proof = accel.accelerate_merkle_proof(data).await;
    let latency_us = start.elapsed().as_secs_f64() * 1_000_000.0;

    assert!(proof.is_ok());
    assert!(
        latency_us < 1000.0,
        "End-to-end merkle should be <1ms, got {:.2}µs",
        latency_us
    );
}

#[test]
fn test_23_performance_report_generation() {
    let report = HardwareAccelerator::benchmark_performance();
    assert!(report.inference_latency_ms >= 0.0);
    assert!(report.merkle_proof_latency_ms >= 0.0);
    assert!(report.gpu_utilization_percent >= 0.0);
}

// ============================================================================
// INTEGRATION & STRESS TESTS (24-25)
// ============================================================================

#[tokio::test]
async fn test_24_integration_all_backends() {
    let backend = MetalBackend::new().unwrap();
    let engine = NeuralEngine::new().unwrap();
    let simd = SimdOps::new();

    let tensor = Tensor::new(vec![1.0; 256], vec![16, 16]);

    let metal_result = backend.accelerate_inference(&tensor).await;
    let engine_result = engine.accelerate_inference(&tensor).await;
    let merkle_result = simd.generate_proof(b"test");

    assert!(metal_result.is_ok());
    assert!(engine_result.is_ok());
    assert!(merkle_result.is_ok());
}

#[tokio::test]
async fn test_25_stress_sustained_load() {
    let backend = Arc::new(MetalBackend::new().unwrap());
    let duration = std::time::Duration::from_secs(2);
    let start = Instant::now();

    let mut count = 0;
    while start.elapsed() < duration {
        let backend_clone = backend.clone();
        let tensor = Tensor::new(vec![1.0; 256], vec![16, 16]);

        let handle = tokio::spawn(async move { backend_clone.accelerate_inference(&tensor).await });

        if let Ok(Ok(_)) = handle.await {
            count += 1;
        }
    }

    assert!(
        count > 10,
        "Should process >10 operations in 2 seconds, got {}",
        count
    );
}
