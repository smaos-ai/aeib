use crate::{InferenceError, ModelMetadata, Result, Tensor};
use dashmap::DashMap;
use std::sync::Arc;
use std::time::SystemTime;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HardwareBackend {
    AppleNeuralEngine,
    MetalGPU,
    CPU,
}

#[derive(Debug, Clone)]
pub struct InferenceModel {
    pub id: String,
    pub weights: Arc<Tensor>,
    pub metadata: ModelMetadata,
    pub deterministic_seed: u64,
    pub created_at: SystemTime,
}

impl InferenceModel {
    pub fn new(
        id: String,
        weights: Tensor,
        metadata: ModelMetadata,
        deterministic_seed: u64,
    ) -> Self {
        InferenceModel {
            id,
            weights: Arc::new(weights),
            metadata,
            deterministic_seed,
            created_at: SystemTime::now(),
        }
    }
}

#[derive(Debug, Clone)]
pub struct InferenceEngine {
    models: Arc<DashMap<String, InferenceModel>>,
    hardware_backend: HardwareBackend,
    determinism_cache: Arc<DashMap<String, bool>>,
}

impl InferenceEngine {
    pub fn new(hardware_backend: HardwareBackend) -> Self {
        InferenceEngine {
            models: Arc::new(DashMap::new()),
            hardware_backend,
            determinism_cache: Arc::new(DashMap::new()),
        }
    }

    pub fn with_backend(backend: HardwareBackend) -> Self {
        Self::new(backend)
    }

    pub fn register_model(&self, model: InferenceModel) -> Result<()> {
        if self.models.contains_key(&model.id) {
            return Err(InferenceError::InferenceFailed(
                "Model already registered".to_string(),
            ));
        }
        self.models.insert(model.id.clone(), model);
        Ok(())
    }

    pub fn get_model(&self, id: &str) -> Result<InferenceModel> {
        self.models
            .get(id)
            .map(|entry| entry.clone())
            .ok_or_else(|| InferenceError::ModelNotFound(id.to_string()))
    }

    pub fn list_models(&self) -> Vec<String> {
        self.models
            .iter()
            .map(|entry| entry.key().clone())
            .collect()
    }

    pub fn hardware_backend(&self) -> HardwareBackend {
        self.hardware_backend
    }

    pub async fn infer(&self, model_id: &str, input: &Tensor) -> Result<Tensor> {
        let model = self.get_model(model_id)?;

        // Validate input shape
        if input.shape() != model.metadata.input_shape.as_slice() {
            return Err(InferenceError::ShapeMismatch {
                expected: format!("{:?}", model.metadata.input_shape),
                actual: format!("{:?}", input.shape()),
            });
        }

        // Simple inference: matrix multiplication (input @ weights)
        // For input [1, 2] and weights [2, 2], we get [1, 2] output
        if model.weights.shape().len() == 2 && input.shape().len() == 2 {
            input.matmul(&model.weights)
        } else if model.weights.shape().len() == 2 && input.shape().len() == 1 {
            // Handle 1D input by reshaping to 2D
            let reshaped_input = Tensor::new(input.flatten(), vec![1, input.shape()[0]])?;
            reshaped_input.matmul(&model.weights)
        } else {
            Err(InferenceError::InferenceFailed(
                "Unsupported tensor shapes for inference".to_string(),
            ))
        }
    }

    pub async fn verify_determinism(&self, model_id: &str, input: &Tensor) -> Result<bool> {
        let cache_key = format!("{}:{:?}", model_id, input.shape());

        if let Some(cached) = self.determinism_cache.get(&cache_key) {
            return Ok(*cached);
        }

        let _ = self.get_model(model_id)?;

        // Run inference twice and compare outputs
        let output1 = self.infer(model_id, input).await?;
        let output2 = self.infer(model_id, input).await?;

        let is_deterministic = output1.flatten() == output2.flatten();
        self.determinism_cache.insert(cache_key, is_deterministic);

        Ok(is_deterministic)
    }

    pub async fn batch_infer(&self, model_id: &str, inputs: &[Tensor]) -> Result<Vec<Tensor>> {
        let mut outputs = Vec::new();
        for input in inputs {
            outputs.push(self.infer(model_id, input).await?);
        }
        Ok(outputs)
    }

    pub fn concurrent_infer_capacity(&self) -> usize {
        num_cpus::get() * 2
    }

    pub fn unload_model(&self, id: &str) -> Result<()> {
        self.models
            .remove(id)
            .ok_or_else(|| InferenceError::ModelNotFound(id.to_string()))?;
        Ok(())
    }

    pub fn model_count(&self) -> usize {
        self.models.len()
    }

    pub async fn infer_with_latency(
        &self,
        model_id: &str,
        input: &Tensor,
    ) -> Result<(Tensor, u64)> {
        let start = std::time::Instant::now();
        let output = self.infer(model_id, input).await?;
        let latency_ms = start.elapsed().as_millis() as u64;
        Ok((output, latency_ms))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_model(id: &str, _backend: HardwareBackend) -> InferenceModel {
        // Create a 2x1 weights matrix for inference: input [1,2] x weights [2,1] = output [1,1]
        // But we want output [1,2], so we need [2,2] weights
        // For [1,2] input x [2,2] weights = [1,2] output
        let weights = Tensor::new(vec![1.0, 2.0, 3.0, 4.0], vec![2, 2]).unwrap();
        let metadata =
            ModelMetadata::new(id.to_string(), "1.0".to_string(), vec![1, 2], vec![1, 2]);
        InferenceModel::new(id.to_string(), weights, metadata, 42)
    }

    #[test]
    fn test_engine_creation() {
        let engine = InferenceEngine::new(HardwareBackend::CPU);
        assert_eq!(engine.hardware_backend(), HardwareBackend::CPU);
        assert_eq!(engine.model_count(), 0);
    }

    #[test]
    fn test_engine_with_backend_variants() {
        let engine_cpu = InferenceEngine::with_backend(HardwareBackend::CPU);
        assert_eq!(engine_cpu.hardware_backend(), HardwareBackend::CPU);

        let engine_neural = InferenceEngine::with_backend(HardwareBackend::AppleNeuralEngine);
        assert_eq!(
            engine_neural.hardware_backend(),
            HardwareBackend::AppleNeuralEngine
        );

        let _engine_metal = InferenceEngine::with_backend(HardwareBackend::MetalGPU);
        assert_eq!(_engine_metal.hardware_backend(), HardwareBackend::MetalGPU);
    }

    #[test]
    fn test_register_model() {
        let engine = InferenceEngine::new(HardwareBackend::CPU);
        let model = create_test_model("model1", HardwareBackend::CPU);

        assert!(engine.register_model(model).is_ok());
        assert_eq!(engine.model_count(), 1);
    }

    #[test]
    fn test_duplicate_model_registration() {
        let engine = InferenceEngine::new(HardwareBackend::CPU);
        let model = create_test_model("model1", HardwareBackend::CPU);

        engine.register_model(model.clone()).unwrap();
        assert!(engine.register_model(model).is_err());
    }

    #[test]
    fn test_get_model() {
        let engine = InferenceEngine::new(HardwareBackend::CPU);
        let model = create_test_model("model1", HardwareBackend::CPU);

        engine.register_model(model.clone()).unwrap();
        let retrieved = engine.get_model("model1").unwrap();
        assert_eq!(retrieved.id, "model1");
    }

    #[test]
    fn test_get_nonexistent_model() {
        let engine = InferenceEngine::new(HardwareBackend::CPU);
        assert!(engine.get_model("nonexistent").is_err());
    }

    #[test]
    fn test_list_models() {
        let engine = InferenceEngine::new(HardwareBackend::CPU);
        for i in 0..3 {
            let model = create_test_model(&format!("model{}", i), HardwareBackend::CPU);
            engine.register_model(model).unwrap();
        }

        let list = engine.list_models();
        assert_eq!(list.len(), 3);
    }

    #[tokio::test]
    async fn test_inference_basic() {
        let engine = InferenceEngine::new(HardwareBackend::CPU);
        let model = create_test_model("model1", HardwareBackend::CPU);
        engine.register_model(model).unwrap();

        let _input = Tensor::new(vec![1.0, 2.0], vec![2]).unwrap();
        let reshaped_input = Tensor::new(vec![1.0, 2.0], vec![1, 2]).unwrap();

        let output = engine.infer("model1", &reshaped_input).await.unwrap();
        assert_eq!(output.shape(), &[1, 2]);
    }

    #[tokio::test]
    async fn test_inference_shape_mismatch() {
        let engine = InferenceEngine::new(HardwareBackend::CPU);
        let model = create_test_model("model1", HardwareBackend::CPU);
        engine.register_model(model).unwrap();

        let wrong_input = Tensor::new(vec![1.0, 2.0, 3.0], vec![3]).unwrap();
        assert!(engine.infer("model1", &wrong_input).await.is_err());
    }

    #[tokio::test]
    async fn test_verify_determinism() {
        let engine = InferenceEngine::new(HardwareBackend::CPU);
        let model = create_test_model("model1", HardwareBackend::CPU);
        engine.register_model(model).unwrap();

        let input = Tensor::new(vec![1.0, 2.0], vec![1, 2]).unwrap();
        let is_deterministic = engine.verify_determinism("model1", &input).await.unwrap();
        assert!(is_deterministic);
    }

    #[tokio::test]
    async fn test_determinism_caching() {
        let engine = InferenceEngine::new(HardwareBackend::CPU);
        let model = create_test_model("model1", HardwareBackend::CPU);
        engine.register_model(model).unwrap();

        let input = Tensor::new(vec![1.0, 2.0], vec![1, 2]).unwrap();

        engine.verify_determinism("model1", &input).await.unwrap();
        assert_eq!(engine.determinism_cache.len(), 1);
    }

    #[tokio::test]
    async fn test_batch_infer() {
        let engine = InferenceEngine::new(HardwareBackend::CPU);
        let model = create_test_model("model1", HardwareBackend::CPU);
        engine.register_model(model).unwrap();

        let inputs = vec![
            Tensor::new(vec![1.0, 2.0], vec![1, 2]).unwrap(),
            Tensor::new(vec![3.0, 4.0], vec![1, 2]).unwrap(),
        ];

        let outputs = engine.batch_infer("model1", &inputs).await.unwrap();
        assert_eq!(outputs.len(), 2);
    }

    #[test]
    fn test_concurrent_infer_capacity() {
        let engine = InferenceEngine::new(HardwareBackend::CPU);
        let capacity = engine.concurrent_infer_capacity();
        assert!(capacity > 0);
    }

    #[test]
    fn test_unload_model() {
        let engine = InferenceEngine::new(HardwareBackend::CPU);
        let model = create_test_model("model1", HardwareBackend::CPU);
        engine.register_model(model).unwrap();

        assert!(engine.unload_model("model1").is_ok());
        assert_eq!(engine.model_count(), 0);
    }

    #[test]
    fn test_unload_nonexistent_model() {
        let engine = InferenceEngine::new(HardwareBackend::CPU);
        assert!(engine.unload_model("nonexistent").is_err());
    }

    #[tokio::test]
    async fn test_infer_with_latency() {
        let engine = InferenceEngine::new(HardwareBackend::CPU);
        let model = create_test_model("model1", HardwareBackend::CPU);
        engine.register_model(model).unwrap();

        let input = Tensor::new(vec![1.0, 2.0], vec![1, 2]).unwrap();
        let (output, latency_ms) = engine.infer_with_latency("model1", &input).await.unwrap();

        assert_eq!(output.shape(), &[1, 2]);
        assert!(latency_ms < 50); // Target <50ms
    }

    #[test]
    fn test_inference_model_creation() {
        let weights = Tensor::new(vec![1.0, 2.0], vec![1, 2]).unwrap();
        let metadata = ModelMetadata::new("test".to_string(), "1.0".to_string(), vec![2], vec![2]);

        let model = InferenceModel::new("model1".to_string(), weights, metadata, 42);
        assert_eq!(model.id, "model1");
        assert_eq!(model.deterministic_seed, 42);
    }

    #[test]
    fn test_hardware_backend_equality() {
        assert_eq!(HardwareBackend::CPU, HardwareBackend::CPU);
        assert_ne!(HardwareBackend::CPU, HardwareBackend::MetalGPU);
        assert_ne!(
            HardwareBackend::AppleNeuralEngine,
            HardwareBackend::MetalGPU
        );
    }
}
