//! Integration tests for Ollama backend integration in siss-ml-inference

use siss_ml_inference::{HardwareBackend, InferenceEngine, InferenceModel, ModelMetadata, Tensor};

fn create_test_model(id: &str) -> InferenceModel {
    let weights = Tensor::new(vec![1.0, 2.0, 3.0, 4.0], vec![2, 2]).unwrap();
    let metadata =
        ModelMetadata::new(id.to_string(), "1.0".to_string(), vec![1, 2], vec![1, 2]);
    InferenceModel::new(id.to_string(), weights, metadata, 42)
}

#[tokio::test]
async fn test_inference_with_ollama_primary() {
    // Test that InferenceEngine can be configured with Ollama backend
    let engine = InferenceEngine::new(HardwareBackend::Ollama);
    let model = create_test_model("ollama_test");

    assert!(engine.register_model(model).is_ok());
    assert_eq!(engine.hardware_backend(), HardwareBackend::Ollama);
    assert_eq!(engine.model_count(), 1);
}

#[tokio::test]
async fn test_inference_fallback_to_cpu() {
    // Test that InferenceEngine can fall back from Ollama to CPU
    let engine = InferenceEngine::new(HardwareBackend::Ollama);
    let model = create_test_model("fallback_test");

    engine.register_model(model).unwrap();

    // This tests the fallback routing logic
    // When Ollama is unavailable, inference should route to CPU
    let input = Tensor::new(vec![1.0, 2.0], vec![1, 2]).unwrap();
    let result = engine.infer("fallback_test", &input).await;

    // Inference should either succeed with Ollama or fall back to CPU
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_ollama_deterministic_responses() {
    // Test that Ollama backend produces deterministic results
    let engine = InferenceEngine::new(HardwareBackend::Ollama);
    let model = create_test_model("determinism_test");

    engine.register_model(model).unwrap();

    let input = Tensor::new(vec![1.0, 2.0], vec![1, 2]).unwrap();

    // Run inference twice and verify determinism
    let output1 = engine.infer("determinism_test", &input).await.unwrap();
    let output2 = engine.infer("determinism_test", &input).await.unwrap();

    // Outputs should be identical (deterministic)
    assert_eq!(output1.flatten(), output2.flatten());
}

#[tokio::test]
async fn test_mixed_ollama_cpu_inference() {
    // Test that InferenceEngine can route requests to appropriate backend
    let engine_ollama = InferenceEngine::new(HardwareBackend::Ollama);
    let engine_cpu = InferenceEngine::new(HardwareBackend::CPU);

    let model = create_test_model("mixed_test");

    engine_ollama.register_model(model.clone()).unwrap();
    engine_cpu.register_model(model).unwrap();

    let input = Tensor::new(vec![1.0, 2.0], vec![1, 2]).unwrap();

    // Both backends should produce valid inference results
    let ollama_result = engine_ollama.infer("mixed_test", &input).await;
    let cpu_result = engine_cpu.infer("mixed_test", &input).await;

    assert!(ollama_result.is_ok());
    assert!(cpu_result.is_ok());
}

#[tokio::test]
async fn test_ollama_concurrent_with_ml_models() {
    // Test concurrent inference with Ollama backend alongside ML models
    let engine = InferenceEngine::new(HardwareBackend::Ollama);

    for i in 0..3 {
        let model = create_test_model(&format!("concurrent_model_{}", i));
        engine.register_model(model).unwrap();
    }

    // Spawn concurrent inference tasks
    let mut handles = vec![];

    for i in 0..3 {
        let engine_clone = engine.clone();
        let model_id = format!("concurrent_model_{}", i);

        let handle = tokio::spawn(async move {
            let input = Tensor::new(vec![1.0, 2.0], vec![1, 2]).unwrap();
            engine_clone.infer(&model_id, &input).await
        });

        handles.push(handle);
    }

    // All concurrent inferences should complete successfully
    for handle in handles {
        let result = handle.await;
        assert!(result.is_ok());
        assert!(result.unwrap().is_ok());
    }
}

#[tokio::test]
async fn test_backend_selection_logic() {
    // Test explicit backend selection
    let backends = vec![
        HardwareBackend::CPU,
        HardwareBackend::MetalGPU,
        HardwareBackend::AppleNeuralEngine,
        HardwareBackend::Ollama,
    ];

    for backend in backends {
        let engine = InferenceEngine::new(backend);
        assert_eq!(engine.hardware_backend(), backend);
    }
}

#[tokio::test]
async fn test_ollama_latency_tracking() {
    // Test latency tracking with Ollama backend
    let engine = InferenceEngine::new(HardwareBackend::Ollama);
    let model = create_test_model("latency_test");

    engine.register_model(model).unwrap();

    let input = Tensor::new(vec![1.0, 2.0], vec![1, 2]).unwrap();

    // Measure latency with Ollama backend
    let (output, latency_ms) = engine.infer_with_latency("latency_test", &input).await.unwrap();

    assert_eq!(output.shape(), &[1, 2]);
    assert!(latency_ms < 1000); // Should complete within 1 second even with Ollama
}

#[tokio::test]
async fn test_model_registry_with_ollama() {
    // Test model registry operations with Ollama backend
    let engine = InferenceEngine::new(HardwareBackend::Ollama);

    // Register multiple models
    for i in 0..5 {
        let model = create_test_model(&format!("registry_model_{}", i));
        assert!(engine.register_model(model).is_ok());
    }

    assert_eq!(engine.model_count(), 5);

    let models = engine.list_models();
    assert_eq!(models.len(), 5);

    // Unload a model
    assert!(engine.unload_model("registry_model_0").is_ok());
    assert_eq!(engine.model_count(), 4);

    // Verify removal
    let retrieved = engine.get_model("registry_model_0");
    assert!(retrieved.is_err());
}
