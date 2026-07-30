use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Ollama API error type
#[derive(Error, Debug)]
pub enum OllamaError {
    #[error("HTTP client error: {0}")]
    ClientError(String),
    #[error("Request timeout")]
    Timeout,
    #[error("Ollama service unavailable")]
    ServiceUnavailable,
    #[error("JSON parse error: {0}")]
    JsonError(#[from] serde_json::Error),
    #[error("Request error: {0}")]
    RequestError(#[from] reqwest::Error),
    #[error("Invalid response format")]
    InvalidResponse,
}

pub type Result<T> = std::result::Result<T, OllamaError>;

/// Request structure for Ollama API
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OllamaRequest {
    pub model: String,
    pub prompt: String,
    pub temperature: f32,
    pub top_p: f32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub top_k: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub num_predict: Option<i32>,
}

/// Response structure from Ollama API
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OllamaResponse {
    pub response: String,
    pub model: String,
    pub created_at: String,
    pub done: bool,
    pub done_reason: String,
    pub context: Vec<i32>,
    pub total_duration: u64,
    pub load_duration: u64,
    pub prompt_eval_count: u32,
    pub prompt_eval_duration: u64,
    pub eval_count: u32,
    pub eval_duration: u64,
}

/// Ollama models response
#[derive(Debug, Serialize, Deserialize)]
struct ModelsResponse {
    models: Vec<ModelInfo>,
}

#[derive(Debug, Serialize, Deserialize)]
struct ModelInfo {
    name: String,
}

/// Ollama client for local inference via REST API
///
/// The OllamaClient provides methods to interact with a running Ollama instance.
/// It supports model inference, health checking, and model listing.
///
/// # Timeout Behavior
///
/// The client has a default 5-second timeout for all requests. This can be customized
/// using the `with_timeout` method.
///
/// # Example
///
/// ```no_run
/// use siss_local_llm::OllamaClient;
/// use std::time::Duration;
///
/// let client = OllamaClient::new("http://localhost:11434", "qwen2.5-coder:14b")
///     .with_timeout(Duration::from_secs(10));
/// ```
pub struct OllamaClient {
    endpoint: String,
    default_model: String,
    client: reqwest::Client,
    timeout: std::time::Duration,
}

impl Clone for OllamaClient {
    fn clone(&self) -> Self {
        OllamaClient {
            endpoint: self.endpoint.clone(),
            default_model: self.default_model.clone(),
            client: reqwest::Client::new(),
            timeout: self.timeout,
        }
    }
}

impl OllamaClient {
    /// Create a new Ollama client
    pub fn new(endpoint: &str, default_model: &str) -> Self {
        OllamaClient {
            endpoint: endpoint.to_string(),
            default_model: default_model.to_string(),
            client: reqwest::Client::new(),
            timeout: std::time::Duration::from_secs(5),
        }
    }

    /// Get the endpoint URL
    pub fn endpoint(&self) -> &str {
        &self.endpoint
    }

    /// Get the default model name
    pub fn default_model(&self) -> &str {
        &self.default_model
    }

    /// Set request timeout
    pub fn with_timeout(mut self, timeout: std::time::Duration) -> Self {
        self.timeout = timeout;
        self
    }

    /// Check if Ollama service is healthy
    pub async fn health_check(&self) -> Result<bool> {
        let url = format!("{}/api/tags", self.endpoint);

        match tokio::time::timeout(
            self.timeout,
            self.client.get(&url).send(),
        )
        .await
        {
            Ok(Ok(response)) => {
                Ok(response.status().is_success())
            }
            Ok(Err(e)) => {
                Err(OllamaError::ClientError(e.to_string()))
            }
            Err(_) => {
                Err(OllamaError::Timeout)
            }
        }
    }

    /// List all available models
    pub async fn list_models(&self) -> Result<Vec<String>> {
        let url = format!("{}/api/tags", self.endpoint);

        match tokio::time::timeout(
            self.timeout,
            self.client.get(&url).send(),
        )
        .await
        {
            Ok(Ok(response)) => {
                let models_resp: ModelsResponse = response.json().await?;
                Ok(models_resp.models.iter().map(|m| m.name.clone()).collect())
            }
            Ok(Err(e)) => {
                Err(OllamaError::ClientError(e.to_string()))
            }
            Err(_) => {
                Err(OllamaError::Timeout)
            }
        }
    }

    /// Generate text using the default model
    pub async fn generate(&self, prompt: &str) -> Result<OllamaResponse> {
        self.generate_with_model(prompt, &self.default_model).await
    }

    /// Generate text using a specific model
    pub async fn generate_with_model(
        &self,
        prompt: &str,
        model: &str,
    ) -> Result<OllamaResponse> {
        let url = format!("{}/api/generate", self.endpoint);

        let request = OllamaRequest {
            model: model.to_string(),
            prompt: prompt.to_string(),
            temperature: 0.0,
            top_p: 0.9,
            top_k: Some(40),
            num_predict: Some(512),
        };

        match tokio::time::timeout(
            self.timeout,
            self.client.post(&url).json(&request).send(),
        )
        .await
        {
            Ok(Ok(response)) => {
                if response.status().is_success() {
                    let resp_text = response.text().await?;
                    // Ollama returns newline-delimited JSON
                    let lines: Vec<&str> = resp_text.lines().collect();
                    if let Some(last_line) = lines.last() {
                        let ollama_response: OllamaResponse =
                            serde_json::from_str(last_line)?;
                        Ok(ollama_response)
                    } else {
                        Err(OllamaError::InvalidResponse)
                    }
                } else {
                    Err(OllamaError::ServiceUnavailable)
                }
            }
            Ok(Err(e)) => {
                Err(OllamaError::ClientError(e.to_string()))
            }
            Err(_) => {
                Err(OllamaError::Timeout)
            }
        }
    }

    /// Generate text with custom parameters
    pub async fn generate_with_params(
        &self,
        prompt: &str,
        model: &str,
        temperature: f32,
        top_p: f32,
    ) -> Result<OllamaResponse> {
        let url = format!("{}/api/generate", self.endpoint);

        let request = OllamaRequest {
            model: model.to_string(),
            prompt: prompt.to_string(),
            temperature,
            top_p,
            top_k: Some(40),
            num_predict: Some(512),
        };

        match tokio::time::timeout(
            self.timeout,
            self.client.post(&url).json(&request).send(),
        )
        .await
        {
            Ok(Ok(response)) => {
                if response.status().is_success() {
                    let resp_text = response.text().await?;
                    let lines: Vec<&str> = resp_text.lines().collect();
                    if let Some(last_line) = lines.last() {
                        let ollama_response: OllamaResponse =
                            serde_json::from_str(last_line)?;
                        Ok(ollama_response)
                    } else {
                        Err(OllamaError::InvalidResponse)
                    }
                } else {
                    Err(OllamaError::ServiceUnavailable)
                }
            }
            Ok(Err(e)) => {
                Err(OllamaError::ClientError(e.to_string()))
            }
            Err(_) => {
                Err(OllamaError::Timeout)
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ollama_client_creation() {
        let client = OllamaClient::new("http://localhost:11434", "qwen2.5-coder:14b");
        assert_eq!(client.endpoint(), "http://localhost:11434");
        assert_eq!(client.default_model(), "qwen2.5-coder:14b");
    }

    #[test]
    fn test_ollama_request_serialization() {
        let request = OllamaRequest {
            model: "qwen2.5-coder:14b".to_string(),
            prompt: "test".to_string(),
            temperature: 0.0,
            top_p: 0.9,
            top_k: Some(40),
            num_predict: Some(512),
        };

        let json = serde_json::to_string(&request).unwrap();
        assert!(json.contains("qwen2.5-coder:14b"));
        assert!(json.contains("test"));
    }

    #[test]
    fn test_ollama_client_clone() {
        let client = OllamaClient::new("http://localhost:11434", "qwen2.5-coder:14b");
        let cloned = client.clone();
        assert_eq!(cloned.endpoint(), client.endpoint());
        assert_eq!(cloned.default_model(), client.default_model());
    }
}
