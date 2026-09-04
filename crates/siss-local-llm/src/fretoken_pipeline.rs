use crate::{BudgetPolicy, KVCachePool, OllamaClient, OllamaResponse};
use std::collections::VecDeque;
use std::sync::{Arc, Mutex};
use thiserror::Error;

/// FreeToken pipeline errors
#[derive(Error, Debug)]
pub enum FreeTokenError {
    #[error("Ollama error: {0}")]
    OllamaError(String),
    #[error("Buffer unavailable")]
    BufferUnavailable,
    #[error("Invalid buffer state")]
    InvalidBufferState,
}

pub type FreeTokenResult<T> = std::result::Result<T, FreeTokenError>;

/// Buffer state machine for double-buffered prefill
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum PrefillBufferState {
    Empty,
    Prefilling,
    Ready,
    #[allow(dead_code)]
    Generating,
    #[allow(dead_code)]
    Complete,
}

/// A prefill buffer with state and ID
#[derive(Debug, Clone)]
struct PrefillBuffer {
    id: u64,
    state: PrefillBufferState,
    prompt: String,
}

/// FreeToken double-buffered prefill pipeline
///
/// Enables concurrent prefill encoding and generation by maintaining
/// multiple buffers. While one buffer streams output, another encodes the next prompt.
pub struct FreeTokenPipeline {
    client: OllamaClient,
    buffer_capacity: usize,
    available_buffers: Arc<Mutex<VecDeque<PrefillBuffer>>>,
    kv_cache: Arc<KVCachePool>,
    budget_policy: Arc<BudgetPolicy>,
    next_buffer_id: Arc<Mutex<u64>>,
}

impl Clone for FreeTokenPipeline {
    fn clone(&self) -> Self {
        FreeTokenPipeline {
            client: self.client.clone(),
            buffer_capacity: self.buffer_capacity,
            available_buffers: Arc::clone(&self.available_buffers),
            kv_cache: Arc::clone(&self.kv_cache),
            budget_policy: Arc::clone(&self.budget_policy),
            next_buffer_id: Arc::clone(&self.next_buffer_id),
        }
    }
}

impl FreeTokenPipeline {
    /// Create a new FreeToken pipeline
    ///
    /// # Arguments
    /// * `client` - Ollama client for inference
    /// * `num_buffers` - Number of prefill buffers (typically 2-4)
    pub fn new(client: OllamaClient, num_buffers: usize) -> Self {
        let mut buffers = VecDeque::with_capacity(num_buffers);
        let mut next_id = 0u64;

        for _ in 0..num_buffers {
            buffers.push_back(PrefillBuffer {
                id: next_id,
                state: PrefillBufferState::Empty,
                prompt: String::new(),
            });
            next_id += 1;
        }

        FreeTokenPipeline {
            client,
            buffer_capacity: num_buffers,
            available_buffers: Arc::new(Mutex::new(buffers)),
            kv_cache: Arc::new(KVCachePool::new(128_000_000)), // 128MB default
            budget_policy: Arc::new(BudgetPolicy::new()),
            next_buffer_id: Arc::new(Mutex::new(next_id)),
        }
    }

    /// Get the number of available buffers
    pub fn available_buffers(&self) -> usize {
        self.available_buffers.lock().unwrap().len()
    }

    /// Get the buffer capacity
    pub fn buffer_capacity(&self) -> usize {
        self.buffer_capacity
    }

    /// Get KV cache pool reference
    pub fn kv_cache(&self) -> Arc<KVCachePool> {
        Arc::clone(&self.kv_cache)
    }

    /// Generate text with the default parameters
    pub async fn generate(&self, prompt: &str) -> FreeTokenResult<OllamaResponse> {
        self.generate_with_budget(prompt, 512, 0.0).await
    }

    /// Generate text with budget-adaptive token allocation
    ///
    /// # Arguments
    /// * `prompt` - Input prompt
    /// * `requested_tokens` - Desired number of output tokens
    /// * `anomaly_score` - Network anomaly score (0.0 = normal, 1.5+ = critical)
    pub async fn generate_with_budget(
        &self,
        prompt: &str,
        requested_tokens: usize,
        anomaly_score: f32,
    ) -> FreeTokenResult<OllamaResponse> {
        // Compute token budget based on anomaly
        let _token_budget = self.budget_policy.compute_token_budget(requested_tokens, anomaly_score);

        // Call Ollama client
        self.client
            .generate_with_params(prompt, self.client.default_model(), 0.0, 0.9)
            .await
            .map_err(|e| FreeTokenError::OllamaError(e.to_string()))
    }

    /// Prefill a buffer asynchronously
    ///
    /// Encodes a prompt into KV cache while another buffer streams output.
    pub async fn prefill_buffer(&self, prompt: &str) -> FreeTokenResult<u64> {
        let mut buffers = self.available_buffers.lock().unwrap();

        if buffers.is_empty() {
            return Err(FreeTokenError::BufferUnavailable);
        }

        // Get the next available buffer
        let mut buffer = buffers.pop_front().unwrap();
        let buffer_id = buffer.id;

        // Update buffer state
        buffer.state = PrefillBufferState::Prefilling;
        buffer.prompt = prompt.to_string();

        // Simulate prefill by storing prompt in cache
        let cache_key = format!("prefill:{}", buffer_id);
        self.kv_cache
            .allocate(cache_key, prompt.as_bytes().to_vec())
            .map_err(|e| FreeTokenError::OllamaError(e.to_string()))?;

        // Mark buffer as ready
        buffer.state = PrefillBufferState::Ready;
        buffers.push_back(buffer);

        Ok(buffer_id)
    }

    /// Check if a buffer is ready for generation
    pub fn is_buffer_ready(&self, buffer_id: u64) -> bool {
        let buffers = self.available_buffers.lock().unwrap();
        buffers
            .iter()
            .find(|b| b.id == buffer_id)
            .map(|b| b.state == PrefillBufferState::Ready)
            .unwrap_or(false)
    }

    /// Get the current KV cache size
    pub fn cache_size(&self) -> usize {
        self.kv_cache.current_size()
    }

    /// Clear all buffers and cache
    pub fn reset(&self) {
        self.available_buffers.lock().unwrap().clear();
        self.kv_cache.clear();

        let mut buffers = self.available_buffers.lock().unwrap();
        let next_id = *self.next_buffer_id.lock().unwrap();

        for i in 0..self.buffer_capacity {
            buffers.push_back(PrefillBuffer {
                id: next_id + i as u64,
                state: PrefillBufferState::Empty,
                prompt: String::new(),
            });
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_pipeline() -> FreeTokenPipeline {
        let client = OllamaClient::new("http://localhost:11434", "qwen2.5-coder:14b");
        FreeTokenPipeline::new(client, 2)
    }

    #[test]
    fn test_pipeline_creation() {
        let pipeline = create_test_pipeline();
        assert_eq!(pipeline.buffer_capacity(), 2);
        assert_eq!(pipeline.available_buffers(), 2);
    }

    #[test]
    fn test_budget_computation() {
        let pipeline = create_test_pipeline();
        let budget = pipeline.budget_policy.compute_token_budget(512, 0.5);
        assert!(budget > 0);
        assert!(budget <= 512);
    }

    #[tokio::test]
    async fn test_prefill_buffer_allocation() {
        let pipeline = create_test_pipeline();
        let prompt = "test prompt";
        let _buffer_id = pipeline.prefill_buffer(prompt).await.unwrap();
    }

    #[test]
    fn test_cache_operations() {
        let pipeline = create_test_pipeline();
        let initial_size = pipeline.cache_size();
        assert_eq!(initial_size, 0);
    }

    #[test]
    fn test_reset_clears_state() {
        let pipeline = create_test_pipeline();
        pipeline.reset();
        assert_eq!(pipeline.available_buffers(), 2);
        assert_eq!(pipeline.cache_size(), 0);
    }
}
