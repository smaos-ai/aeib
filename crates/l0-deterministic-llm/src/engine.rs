use crate::cache::PromptCache;
use crate::error::L0Error;
use crate::ledger::MerkleChainLedger;
use crate::offline::OfflineFallback;
use crate::types::{
    CachedInferenceResponse, DeterministicInferenceRequest, TokenCostMetrics,
    format_sha256_hash,
};
use ed25519_dalek::SigningKey;
use std::sync::Arc;
use parking_lot::Mutex;

/// Deterministic LLM Abstraction Engine (Layer 0)
/// - Temperature=0.0 deterministic inference
/// - Prompt caching with SHA256 fingerprinting
/// - 70% token cost reduction target
/// - Offline fallback support
/// - L8 proof layer integration (Merkle chain)
pub struct DeterministicLLMEngine {
    cache: PromptCache,
    ledger: MerkleChainLedger,
    offline: OfflineFallback,
    metrics: Arc<Mutex<TokenCostMetrics>>,
    is_online: Arc<Mutex<bool>>,
}

impl DeterministicLLMEngine {
    pub fn new(signing_key: SigningKey) -> Self {
        Self {
            cache: PromptCache::new(1000, 24),
            ledger: MerkleChainLedger::new(signing_key),
            offline: OfflineFallback::new(),
            metrics: Arc::new(Mutex::new(TokenCostMetrics::new())),
            is_online: Arc::new(Mutex::new(true)),
        }
    }

    /// Process inference request
    pub async fn infer(
        &self,
        request: DeterministicInferenceRequest,
    ) -> Result<CachedInferenceResponse, L0Error> {
        // Validate request (temperature must be 0.0)
        if (request.temperature - 0.0).abs() > 1e-6 {
            return Err(L0Error::InferenceError {
                reason: "Temperature must be 0.0 for determinism".to_string(),
            });
        }

        let fingerprint = request.fingerprint();

        // Check cache first
        if let Some(cached) = self.cache.get(&fingerprint) {
            self.record_cache_hit(&fingerprint);
            return Ok(cached);
        }

        // Try online inference
        if *self.is_online.lock() {
            match self.call_llm_api(&request, &fingerprint).await {
                Ok(response) => {
                    self.record_inference(&fingerprint, &response);
                    return Ok(response);
                }
                Err(_) => {
                    // Fall back to offline
                    *self.is_online.lock() = false;
                }
            }
        }

        // Offline fallback
        match self.offline.get_fallback(&request.prompt) {
            Some(fallback_response) => {
                let response = CachedInferenceResponse::new(
                    fallback_response,
                    0, // Offline doesn't use tokens
                    0,
                    fingerprint.clone(),
                    false,
                );
                self.record_offline_fallback(&response);
                Ok(response)
            }
            None => Err(L0Error::OfflineFallbackError {
                reason: "No fallback template available".to_string(),
            }),
        }
    }

    /// Simulate LLM API call (real implementation would call Anthropic API)
    async fn call_llm_api(
        &self,
        request: &DeterministicInferenceRequest,
        fingerprint: &str,
    ) -> Result<CachedInferenceResponse, L0Error> {
        // Simulate API call with deterministic token calculation
        let input_tokens = (request.prompt.len() / 4) as u32; // Rough estimate
        let output_tokens = request.max_tokens.min(100); // Simulated

        let response = CachedInferenceResponse::new(
            "Simulated inference result".to_string(),
            input_tokens,
            output_tokens,
            fingerprint.to_string(),
            false,
        );

        // Cache the response
        self.cache
            .set(fingerprint.to_string(), response.clone())
            .map_err(|e| L0Error::CacheError { reason: e })?;

        Ok(response)
    }

    fn record_cache_hit(&self, fingerprint: &str) {
        let mut metrics = self.metrics.lock();
        metrics.cache_hits += 1;
        metrics.total_inferences += 1;
        // Baseline increases as if we made an API call, but actual doesn't (cache hit is free)
        metrics.total_tokens_baseline += 50; // Average tokens per inference

        // Record in Merkle chain
        let response_hash = format_sha256_hash(fingerprint);
        let _ = self.ledger.add_entry(
            fingerprint.to_string(),
            response_hash,
            0, // No tokens for cache hit
            true,
        );

        metrics.calculate_reduction();
    }

    fn record_inference(
        &self,
        fingerprint: &str,
        response: &CachedInferenceResponse,
    ) {
        let mut metrics = self.metrics.lock();
        metrics.cache_misses += 1;
        metrics.total_inferences += 1;
        // Both baseline and actual increase for cache misses (we had to make the API call)
        metrics.total_tokens_baseline += response.total_tokens as u64;
        metrics.total_tokens_actual += response.total_tokens as u64;

        // Record in Merkle chain with cost
        let response_hash = format_sha256_hash(&response.output);
        let _ = self.ledger.add_entry(
            fingerprint.to_string(),
            response_hash,
            response.total_tokens,
            false,
        );

        metrics.calculate_reduction();
    }

    fn record_offline_fallback(&self, response: &CachedInferenceResponse) {
        let mut metrics = self.metrics.lock();
        metrics.offline_fallbacks += 1;
        metrics.total_inferences += 1;

        let response_hash = format_sha256_hash(&response.output);
        let _ = self.ledger.add_entry(
            response.fingerprint.clone(),
            response_hash,
            0,
            false,
        );
    }

    /// Get current metrics
    pub fn metrics(&self) -> TokenCostMetrics {
        self.metrics.lock().clone()
    }

    /// Register offline template
    pub fn register_fallback_template(
        &self,
        domain: String,
        pattern: String,
        response: String,
    ) -> Result<(), String> {
        use crate::types::OfflineFallbackTemplate;
        self.offline
            .register_template(OfflineFallbackTemplate::new(domain, pattern, response))
    }

    /// Set online status
    pub fn set_online(&self, online: bool) {
        *self.is_online.lock() = online;
    }

    /// Get online status
    pub fn is_online(&self) -> bool {
        *self.is_online.lock()
    }

    /// Get Merkle chain verification
    pub fn verify_ledger(&self) -> Result<bool, String> {
        self.ledger.verify_chain()
    }

    /// Get ledger entries
    pub fn ledger_entries(&self) -> Vec<crate::types::MerkleChainEntry> {
        self.ledger.get_all()
    }
}

impl Clone for DeterministicLLMEngine {
    fn clone(&self) -> Self {
        Self {
            cache: PromptCache::default(),
            ledger: self.ledger.clone(),
            offline: OfflineFallback::default(),
            metrics: Arc::clone(&self.metrics),
            is_online: Arc::clone(&self.is_online),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_key() -> SigningKey {
        let mut seed = [0u8; 32];
        seed[0] = 42;
        SigningKey::from_bytes(&seed)
    }

    #[tokio::test]
    async fn test_inference_with_valid_temperature() {
        let engine = DeterministicLLMEngine::new(create_test_key());
        let request = DeterministicInferenceRequest::new(
            "test prompt".to_string(),
            100,
            "claude-3".to_string(),
        );

        let result = engine.infer(request).await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_inference_rejects_non_zero_temperature() {
        let engine = DeterministicLLMEngine::new(create_test_key());
        let mut request = DeterministicInferenceRequest::new(
            "test prompt".to_string(),
            100,
            "claude-3".to_string(),
        );
        request.temperature = 0.7; // Non-deterministic

        let result = engine.infer(request).await;
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_cache_hit_on_second_request() {
        let engine = DeterministicLLMEngine::new(create_test_key());
        let request = DeterministicInferenceRequest::new(
            "test prompt".to_string(),
            100,
            "claude-3".to_string(),
        );

        // First call (cache miss)
        let _ = engine.infer(request.clone()).await;
        let metrics1 = engine.metrics();
        assert_eq!(metrics1.cache_misses, 1);

        // Second call (cache hit)
        let _ = engine.infer(request).await;
        let metrics2 = engine.metrics();
        assert_eq!(metrics2.cache_hits, 1);
    }

    #[tokio::test]
    async fn test_offline_fallback() {
        let engine = DeterministicLLMEngine::new(create_test_key());
        engine
            .register_fallback_template(
                "test".to_string(),
                "credit".to_string(),
                "Default credit response".to_string(),
            )
            .unwrap();

        engine.set_online(false);

        let request = DeterministicInferenceRequest::new(
            "What is the credit?".to_string(),
            100,
            "claude-3".to_string(),
        );

        let result = engine.infer(request).await;
        assert!(result.is_ok());
        assert_eq!(
            result.unwrap().output,
            "Default credit response"
        );
    }

    #[tokio::test]
    async fn test_metrics_tracking() {
        let engine = DeterministicLLMEngine::new(create_test_key());
        let request = DeterministicInferenceRequest::new(
            "test prompt".to_string(),
            100,
            "claude-3".to_string(),
        );

        let _ = engine.infer(request).await;

        let metrics = engine.metrics();
        assert!(metrics.total_inferences > 0);
    }

    #[test]
    fn test_ledger_verification() {
        let engine = DeterministicLLMEngine::new(create_test_key());
        let is_valid = engine.verify_ledger().unwrap();
        assert!(is_valid);
    }

    #[test]
    fn test_online_status() {
        let engine = DeterministicLLMEngine::new(create_test_key());
        assert!(engine.is_online());

        engine.set_online(false);
        assert!(!engine.is_online());

        engine.set_online(true);
        assert!(engine.is_online());
    }
}
