use crate::error::{LocalLLMError, LocalLLMResult};
use crate::model_loader::ModelCache;
use crate::types::{InferenceRequest, InferenceResult, ModelType};
use chrono::Utc;
use sha2::{Digest, Sha256};
use siss_layer00::{CapabilityToken, Layer0Gate};
use std::sync::Arc;
use std::time::Instant;

#[derive(Clone)]
pub struct InferenceEngine {
    layer0_gate: Arc<Layer0Gate>,
    model_cache: Arc<ModelCache>,
}

impl InferenceEngine {
    pub fn new(layer0_gate: Arc<Layer0Gate>, model_cache: Arc<ModelCache>) -> Self {
        Self {
            layer0_gate,
            model_cache,
        }
    }

    pub fn layer0_gate(&self) -> &Arc<Layer0Gate> {
        &self.layer0_gate
    }

    pub fn model_cache(&self) -> &Arc<ModelCache> {
        &self.model_cache
    }

    /// Execute inference with Layer 0 gating and Merkle logging
    pub async fn infer(
        &self,
        request: InferenceRequest,
        token: &CapabilityToken,
        model_type: ModelType,
    ) -> LocalLLMResult<InferenceResult> {
        // Validate token expiration
        if token.is_expired() {
            return Err(LocalLLMError::TokenExpired);
        }

        // Verify action scope matches requested action
        if token.action_scope != request.action {
            return Err(LocalLLMError::ActionScopeNotAllowed(format!(
                "Token scope '{}' does not match requested action '{}'",
                token.action_scope, request.action
            )));
        }

        let start_time = Instant::now();

        // Load or cache model
        let _model_metadata = self.model_cache.load_model(model_type)?;

        // Execute inference (simulated for now)
        let (output, tokens_used) = self.run_inference(&request.prompt, request.max_tokens)?;

        // Compute result hash for Merkle logging
        let result_hash = self.compute_result_hash(&output);

        // Log to Layer 0 Merkle ledger
        let audit_id = self
            .layer0_gate
            .invoke_tool(
                token,
                &format!("local_llm_inference_{}", model_type),
                result_hash,
            )
            .map_err(|e| LocalLLMError::AuditLogFailure(e.to_string()))?;

        let inference_time_ms = start_time.elapsed().as_millis() as u64;

        Ok(InferenceResult {
            output,
            tokens_used,
            merkle_logged: true,
            audit_id: Some(audit_id),
            model_type,
            inference_time_ms,
            timestamp: Utc::now(),
        })
    }

    /// Run actual inference (simulated for testing)
    fn run_inference(&self, prompt: &str, max_tokens: usize) -> LocalLLMResult<(String, usize)> {
        // Simulated inference - in production, this would call llama-cpp-rs
        let tokens_used = prompt.split_whitespace().count().min(max_tokens);

        let output = format!(
            "Generated response to prompt: '{}' using {} tokens",
            prompt, tokens_used
        );

        Ok((output, tokens_used))
    }

    /// Compute SHA256 hash of inference output for Merkle logging
    fn compute_result_hash(&self, output: &str) -> [u8; 32] {
        let mut hasher = Sha256::new();
        hasher.update(output.as_bytes());
        let result = hasher.finalize();
        let mut hash = [0u8; 32];
        hash.copy_from_slice(&result);
        hash
    }
}
