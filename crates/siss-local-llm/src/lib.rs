pub mod error;
pub mod inference;
pub mod model_loader;
pub mod types;

pub use error::{LocalLLMError, LocalLLMResult};
pub use inference::InferenceEngine;
pub use model_loader::ModelCache;
pub use types::{InferenceRequest, InferenceResult, LocalLLMConfig, ModelMetadata, ModelType};

use siss_layer00::{CapabilityToken, Layer0Gate};
use std::sync::Arc;

/// Main entry point for local LLM inference with Layer 0 gating
#[derive(Clone)]
pub struct LocalLLMGate {
    layer0_gate: Arc<Layer0Gate>,
    inference_engine: Arc<InferenceEngine>,
    model_cache: Arc<ModelCache>,
}

impl LocalLLMGate {
    pub fn new(layer0_gate: Arc<Layer0Gate>, config: LocalLLMConfig) -> Self {
        let model_cache = Arc::new(ModelCache::new(config));
        let inference_engine = Arc::new(InferenceEngine::new(
            layer0_gate.clone(),
            model_cache.clone(),
        ));

        Self {
            layer0_gate,
            inference_engine,
            model_cache,
        }
    }

    /// Execute inference with Layer 0 capability validation
    pub async fn infer(
        &self,
        request: InferenceRequest,
        token: &CapabilityToken,
        model_type: ModelType,
    ) -> LocalLLMResult<InferenceResult> {
        self.inference_engine
            .infer(request, token, model_type)
            .await
    }

    /// Access underlying Layer 0 gate for advanced operations
    pub fn layer0_gate(&self) -> &Arc<Layer0Gate> {
        &self.layer0_gate
    }

    /// Access model cache for cache management
    pub fn model_cache(&self) -> &Arc<ModelCache> {
        &self.model_cache
    }

    /// Verify Merkle chain integrity
    pub fn verify_merkle_chain(&self) -> LocalLLMResult<bool> {
        self.layer0_gate
            .verify_chain()
            .map_err(|e| LocalLLMError::AuditLogFailure(e.to_string()))
    }

    /// Get current Merkle root
    pub fn merkle_root(&self) -> LocalLLMResult<[u8; 32]> {
        self.layer0_gate
            .merkle_root()
            .map_err(|e| LocalLLMError::AuditLogFailure(e.to_string()))
    }
}
