use l6_infrastructure::{LangChainOllamaAdapter, OllamaConfig, LLMRequest, LLMResponse};

#[test]
fn test_ollama_config_creation() {
    let config = OllamaConfig::new("http://localhost:11434".to_string(), "qwen".to_string());
    assert_eq!(config.base_url, "http://localhost:11434");
    assert_eq!(config.model, "qwen");
}

#[test]
fn test_langchain_adapter_creation() {
    let config = OllamaConfig::new("http://localhost:11434".to_string(), "qwen".to_string());
    let adapter = LangChainOllamaAdapter::new(config);
    assert!(adapter.is_ok());
}

#[test]
fn test_langchain_adapter_invalid_url() {
    let config = OllamaConfig::new("".to_string(), "qwen".to_string());
    let adapter = LangChainOllamaAdapter::new(config);
    assert!(adapter.is_err());
}

#[test]
fn test_langchain_adapter_invalid_model() {
    let config = OllamaConfig::new("http://localhost:11434".to_string(), "".to_string());
    let adapter = LangChainOllamaAdapter::new(config);
    assert!(adapter.is_err());
}

#[test]
fn test_llm_request_creation() {
    let request = LLMRequest::new("What is 2+2?".to_string(), 100);
    assert_eq!(request.prompt, "What is 2+2?");
    assert_eq!(request.max_tokens, 100);
}

#[test]
fn test_llm_request_with_options() {
    let request = LLMRequest::new("What is 2+2?".to_string(), 100)
        .with_temperature(0.7);
    assert_eq!(request.temperature, 0.7);
}

#[test]
fn test_langchain_adapter_health_check() {
    let config = OllamaConfig::new("http://localhost:11434".to_string(), "qwen".to_string());
    if let Ok(adapter) = LangChainOllamaAdapter::new(config) {
        let is_healthy = adapter.health_check();
        assert!(is_healthy.is_ok());
    }
}

#[test]
fn test_langchain_adapter_is_compatible() {
    let config = OllamaConfig::new("http://localhost:11434".to_string(), "qwen".to_string());
    if let Ok(adapter) = LangChainOllamaAdapter::new(config) {
        assert!(adapter.is_ollama_compatible());
    }
}

#[test]
fn test_llm_response_creation() {
    let response = LLMResponse::new(
        "The answer is 4".to_string(),
        50,
        25.5,
    );
    assert_eq!(response.output, "The answer is 4");
    assert_eq!(response.tokens_used, 50);
    assert_eq!(response.throughput_tok_s, 25.5);
}

#[test]
fn test_langchain_adapter_request_validation() {
    let config = OllamaConfig::new("http://localhost:11434".to_string(), "qwen".to_string());
    if let Ok(adapter) = LangChainOllamaAdapter::new(config) {
        let request = LLMRequest::new("Test prompt".to_string(), 100);
        let is_valid = adapter.validate_request(&request);
        assert!(is_valid);
    }
}

#[test]
fn test_langchain_adapter_simulate_inference() {
    let config = OllamaConfig::new("http://localhost:11434".to_string(), "qwen".to_string());
    if let Ok(adapter) = LangChainOllamaAdapter::new(config) {
        let request = LLMRequest::new("What is AI?".to_string(), 50);
        let result = adapter.simulate_inference(&request);
        assert!(result.is_ok());
        let response = result.unwrap();
        assert!(!response.output.is_empty());
    }
}
