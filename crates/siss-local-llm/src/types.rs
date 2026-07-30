use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum ModelType {
    Llama405B,
    MistralMoE,
    OpenSourceCustom,
}

impl std::fmt::Display for ModelType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ModelType::Llama405B => write!(f, "llama-405b"),
            ModelType::MistralMoE => write!(f, "mistral-moe"),
            ModelType::OpenSourceCustom => write!(f, "custom"),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InferenceRequest {
    pub prompt: String,
    pub max_tokens: usize,
    pub mandate_id: Uuid,
    pub action: String,
    pub temperature: Option<f32>,
    pub top_p: Option<f32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InferenceResult {
    pub output: String,
    pub tokens_used: usize,
    pub merkle_logged: bool,
    pub audit_id: Option<i64>,
    pub model_type: ModelType,
    pub inference_time_ms: u64,
    pub timestamp: DateTime<Utc>,
}

#[derive(Debug, Clone)]
pub struct ModelMetadata {
    pub model_type: ModelType,
    pub model_path: String,
    pub max_context_length: usize,
    pub loaded_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LocalLLMConfig {
    pub model_cache_dir: String,
    pub max_cache_size: usize,
    pub enable_gpu: bool,
    pub thread_count: usize,
}

impl Default for LocalLLMConfig {
    fn default() -> Self {
        Self {
            model_cache_dir: "/tmp/siss-llm-models".to_string(),
            max_cache_size: 2048,
            enable_gpu: false,
            thread_count: 4,
        }
    }
}
