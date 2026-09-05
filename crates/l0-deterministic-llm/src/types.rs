use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// Deterministic LLM inference request with temperature=0.0
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeterministicInferenceRequest {
    pub prompt: String,
    pub max_tokens: u32,
    pub model: String,
    pub temperature: f32, // Always 0.0 for determinism
}

impl DeterministicInferenceRequest {
    pub fn new(prompt: String, max_tokens: u32, model: String) -> Self {
        Self {
            prompt,
            max_tokens,
            model,
            temperature: 0.0, // Enforced determinism
        }
    }

    /// SHA256 fingerprint for cache lookup
    pub fn fingerprint(&self) -> String {
        let combined = format!("{}:{}", self.prompt, self.model);
        format_sha256_hash(&combined)
    }
}

/// Cached inference response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CachedInferenceResponse {
    pub output: String,
    pub input_tokens: u32,
    pub output_tokens: u32,
    pub total_tokens: u32,
    pub fingerprint: String,
    pub created_at: DateTime<Utc>,
    pub cache_hit: bool,
}

impl CachedInferenceResponse {
    pub fn new(
        output: String,
        input_tokens: u32,
        output_tokens: u32,
        fingerprint: String,
        cache_hit: bool,
    ) -> Self {
        Self {
            output,
            input_tokens,
            output_tokens,
            total_tokens: input_tokens + output_tokens,
            fingerprint,
            created_at: Utc::now(),
            cache_hit,
        }
    }
}

/// Cost tracking for token reduction metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TokenCostMetrics {
    pub total_inferences: usize,
    pub cache_hits: usize,
    pub cache_misses: usize,
    pub total_tokens_baseline: u64,
    pub total_tokens_actual: u64,
    pub offline_fallbacks: usize,
    pub cost_reduction_percent: f64,
}

impl TokenCostMetrics {
    pub fn new() -> Self {
        Self {
            total_inferences: 0,
            cache_hits: 0,
            cache_misses: 0,
            total_tokens_baseline: 0,
            total_tokens_actual: 0,
            offline_fallbacks: 0,
            cost_reduction_percent: 0.0,
        }
    }

    /// Calculate cost reduction percentage (target: 70%)
    pub fn calculate_reduction(&mut self) {
        if self.total_tokens_baseline > 0 {
            let reduction = 1.0 - (self.total_tokens_actual as f64 / self.total_tokens_baseline as f64);
            self.cost_reduction_percent = reduction * 100.0;
        }
    }
}

impl Default for TokenCostMetrics {
    fn default() -> Self {
        Self::new()
    }
}

/// Offline fallback template (rule-based)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OfflineFallbackTemplate {
    pub domain: String,
    pub pattern: String,
    pub fallback_response: String,
}

impl OfflineFallbackTemplate {
    pub fn new(domain: String, pattern: String, fallback_response: String) -> Self {
        Self {
            domain,
            pattern,
            fallback_response,
        }
    }

    /// Check if prompt matches this template pattern
    pub fn matches(&self, prompt: &str) -> bool {
        prompt.to_lowercase().contains(&self.pattern.to_lowercase())
    }
}

/// Merkle chain entry for ledger integration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MerkleChainEntry {
    pub id: String,
    pub prompt_fingerprint: String,
    pub response_hash: String,
    pub prev_hash: Option<String>,
    pub timestamp: DateTime<Utc>,
    pub cost_tokens: u32,
    pub cache_hit: bool,
}

impl MerkleChainEntry {
    pub fn new(
        id: String,
        prompt_fingerprint: String,
        response_hash: String,
        prev_hash: Option<String>,
        cost_tokens: u32,
        cache_hit: bool,
    ) -> Self {
        Self {
            id,
            prompt_fingerprint,
            response_hash,
            prev_hash,
            timestamp: Utc::now(),
            cost_tokens,
            cache_hit,
        }
    }
}

/// Helper: SHA256 hash formatting
pub fn format_sha256_hash(input: &str) -> String {
    use sha2::{Digest, Sha256};
    let mut hasher = Sha256::new();
    hasher.update(input);
    format!("{:x}", hasher.finalize())
}
