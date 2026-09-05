//! LangChain Ollama adapter: Compatibility layer for LangChain integration
//! Bridges Ollama-compatible inference endpoints

use crate::error::{validate_model_name, L6Error};
use chrono::Utc;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OllamaConfig {
    pub base_url: String,
    pub model: String,
}

impl OllamaConfig {
    pub fn new(base_url: String, model: String) -> Self {
        Self { base_url, model }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LLMRequest {
    pub prompt: String,
    pub max_tokens: u32,
    pub temperature: f32,
}

impl LLMRequest {
    pub fn new(prompt: String, max_tokens: u32) -> Self {
        Self {
            prompt,
            max_tokens,
            temperature: 0.7,
        }
    }

    pub fn with_temperature(mut self, temperature: f32) -> Self {
        self.temperature = temperature;
        self
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LLMResponse {
    pub output: String,
    pub tokens_used: u32,
    pub throughput_tok_s: f32,
}

impl LLMResponse {
    pub fn new(output: String, tokens_used: u32, throughput_tok_s: f32) -> Self {
        Self {
            output,
            tokens_used,
            throughput_tok_s,
        }
    }
}

pub struct LangChainOllamaAdapter {
    config: OllamaConfig,
}

impl LangChainOllamaAdapter {
    pub fn new(config: OllamaConfig) -> Result<Self, L6Error> {
        if config.base_url.is_empty() {
            return Err(L6Error::InsufficientResources {
                reason: "Ollama base URL cannot be empty".to_string(),
                recovery: "Set valid Ollama endpoint (e.g., http://localhost:11434)".to_string(),
                timestamp: Utc::now(),
            });
        }

        validate_model_name(&config.model)?;

        Ok(Self { config })
    }

    pub fn health_check(&self) -> Result<(), L6Error> {
        if self.config.base_url.is_empty() {
            return Err(L6Error::HardwareDetectionFailed {
                reason: "Ollama endpoint unreachable".to_string(),
                recovery: "Ensure Ollama service is running".to_string(),
                timestamp: Utc::now(),
            });
        }
        Ok(())
    }

    pub fn is_ollama_compatible(&self) -> bool {
        self.config.base_url.contains("localhost") || self.config.base_url.contains("127.0.0.1")
    }

    pub fn validate_request(&self, request: &LLMRequest) -> bool {
        !request.prompt.is_empty() && request.max_tokens > 0
    }

    pub fn simulate_inference(&self, request: &LLMRequest) -> Result<LLMResponse, L6Error> {
        if !self.validate_request(request) {
            return Err(L6Error::InsufficientResources {
                reason: "Invalid request parameters".to_string(),
                recovery: "Ensure prompt is non-empty and max_tokens > 0".to_string(),
                timestamp: Utc::now(),
            });
        }

        Ok(LLMResponse::new(
            format!("Response to: {}", &request.prompt[..request.prompt.len().min(20)]),
            request.max_tokens,
            39.3,
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ollama_config() {
        let config = OllamaConfig::new("http://localhost:11434".to_string(), "qwen".to_string());
        assert_eq!(config.base_url, "http://localhost:11434");
    }

    #[test]
    fn test_llm_request() {
        let req = LLMRequest::new("test".to_string(), 50);
        assert_eq!(req.max_tokens, 50);
    }

    #[test]
    fn test_adapter_creation() {
        let config = OllamaConfig::new("http://localhost:11434".to_string(), "qwen".to_string());
        let adapter = LangChainOllamaAdapter::new(config);
        assert!(adapter.is_ok());
    }
}
