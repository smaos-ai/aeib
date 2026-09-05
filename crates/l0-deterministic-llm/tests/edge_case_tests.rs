use l0_deterministic_llm::{DeterministicInferenceRequest, DeterministicLLMEngine};
use ed25519_dalek::SigningKey;

fn create_test_key() -> SigningKey {
    let mut seed = [0u8; 32];
    seed[0] = 99;
    SigningKey::from_bytes(&seed)
}

#[tokio::test]
async fn test_empty_prompt() {
    let engine = DeterministicLLMEngine::new(create_test_key());
    let request = DeterministicInferenceRequest::new(
        "".to_string(),
        100,
        "claude-3-opus".to_string(),
    );

    let response = engine.infer(request).await;
    assert!(response.is_ok()); // Empty prompts should still work
}

#[tokio::test]
async fn test_very_long_prompt() {
    let engine = DeterministicLLMEngine::new(create_test_key());
    let long_prompt = "x".repeat(10000);
    let request = DeterministicInferenceRequest::new(
        long_prompt,
        100,
        "claude-3-opus".to_string(),
    );

    let response = engine.infer(request).await;
    assert!(response.is_ok());
}

#[tokio::test]
async fn test_unicode_in_prompt() {
    let engine = DeterministicLLMEngine::new(create_test_key());
    let request = DeterministicInferenceRequest::new(
        "こんにちは世界 🌍 Привет".to_string(),
        100,
        "claude-3-opus".to_string(),
    );

    let response = engine.infer(request).await;
    assert!(response.is_ok());
    assert!(response.unwrap().output.len() > 0);
}

#[tokio::test]
async fn test_special_characters_in_prompt() {
    let engine = DeterministicLLMEngine::new(create_test_key());
    let request = DeterministicInferenceRequest::new(
        "!@#$%^&*()_+-=[]{}|;:',.<>?/~`".to_string(),
        100,
        "claude-3-opus".to_string(),
    );

    let response = engine.infer(request).await;
    assert!(response.is_ok());
}

#[tokio::test]
async fn test_max_tokens_zero() {
    let engine = DeterministicLLMEngine::new(create_test_key());
    let request = DeterministicInferenceRequest::new(
        "test prompt".to_string(),
        0,
        "claude-3-opus".to_string(),
    );

    let response = engine.infer(request).await;
    assert!(response.is_ok());
}

#[tokio::test]
async fn test_max_tokens_very_large() {
    let engine = DeterministicLLMEngine::new(create_test_key());
    let request = DeterministicInferenceRequest::new(
        "test prompt".to_string(),
        1000000,
        "claude-3-opus".to_string(),
    );

    let response = engine.infer(request).await;
    assert!(response.is_ok());
}

#[tokio::test]
async fn test_different_model_names() {
    let engine = DeterministicLLMEngine::new(create_test_key());

    let models = vec!["claude-3-opus", "gpt-4", "mistral-7b", "llama-70b"];

    for model in models {
        let request = DeterministicInferenceRequest::new(
            "test prompt".to_string(),
            100,
            model.to_string(),
        );

        let response = engine.infer(request).await;
        assert!(response.is_ok());
        assert_eq!(response.unwrap().cache_hit, false); // Different models = different fingerprints
    }
}

#[tokio::test]
async fn test_repeated_inferences_with_different_max_tokens() {
    let engine = DeterministicLLMEngine::new(create_test_key());

    // Same prompt, different max_tokens
    let req1 = DeterministicInferenceRequest::new(
        "same prompt".to_string(),
        50,
        "claude-3-opus".to_string(),
    );

    let req2 = DeterministicInferenceRequest::new(
        "same prompt".to_string(),
        100,
        "claude-3-opus".to_string(),
    );

    let _ = engine.infer(req1.clone()).await;
    let _ = engine.infer(req2).await;

    let metrics = engine.metrics();
    // Same prompt and model = same fingerprint, so second is cache hit
    assert_eq!(metrics.cache_hits, 1);
    assert_eq!(metrics.cache_misses, 1);
}

#[tokio::test]
async fn test_online_status_switch() {
    let engine = DeterministicLLMEngine::new(create_test_key());

    assert!(engine.is_online());
    engine.set_online(false);
    assert!(!engine.is_online());
    engine.set_online(true);
    assert!(engine.is_online());
    engine.set_online(false);
    assert!(!engine.is_online());
}

#[tokio::test]
async fn test_metrics_after_many_inferences() {
    let engine = DeterministicLLMEngine::new(create_test_key());

    for i in 0..100 {
        let request = DeterministicInferenceRequest::new(
            format!("Prompt {}", i % 10), // 10 unique, 10x repetition
            50,
            "claude-3-opus".to_string(),
        );
        let _ = engine.infer(request).await;
    }

    let metrics = engine.metrics();
    assert_eq!(metrics.total_inferences, 100);
    assert!(metrics.cache_hits >= 90); // Should have ~90 cache hits
    assert!(metrics.cost_reduction_percent >= 50.0); // Should show significant reduction
}

#[tokio::test]
async fn test_ledger_after_many_entries() {
    let engine = DeterministicLLMEngine::new(create_test_key());

    for i in 0..50 {
        let request = DeterministicInferenceRequest::new(
            format!("Prompt {}", i),
            50,
            "claude-3-opus".to_string(),
        );
        let _ = engine.infer(request).await;
    }

    let entries = engine.ledger_entries();
    assert_eq!(entries.len(), 50);

    let is_valid = engine.verify_ledger().unwrap();
    assert!(is_valid);
}

#[tokio::test]
async fn test_fallback_with_pattern_substring() {
    let engine = DeterministicLLMEngine::new(create_test_key());

    engine
        .register_fallback_template(
            "test".to_string(),
            "credit".to_string(),
            "Default credit".to_string(),
        )
        .unwrap();

    engine.set_online(false);

    // Pattern should match substring
    let request = DeterministicInferenceRequest::new(
        "Please give me a CREDIT SCORE".to_string(),
        100,
        "claude-3-opus".to_string(),
    );

    let response = engine.infer(request).await;
    assert!(response.is_ok());
    assert_eq!(response.unwrap().output, "Default credit");
}

#[tokio::test]
async fn test_fingerprint_consistency() {
    let req1 = DeterministicInferenceRequest::new(
        "Hello World".to_string(),
        100,
        "claude-3".to_string(),
    );

    let req2 = DeterministicInferenceRequest::new(
        "Hello World".to_string(),
        100,
        "claude-3".to_string(),
    );

    let req3 = DeterministicInferenceRequest::new(
        "Hello World".to_string(),
        200, // Different max_tokens
        "claude-3".to_string(),
    );

    // Same prompt and model should have same fingerprint regardless of max_tokens
    assert_eq!(req1.fingerprint(), req2.fingerprint());
    assert_eq!(req1.fingerprint(), req3.fingerprint());
}

#[tokio::test]
async fn test_multiple_offline_templates_priority() {
    let engine = DeterministicLLMEngine::new(create_test_key());

    // Register multiple templates
    engine
        .register_fallback_template(
            "general".to_string(),
            "test".to_string(),
            "General fallback".to_string(),
        )
        .unwrap();

    engine
        .register_fallback_template(
            "specific".to_string(),
            "test123".to_string(),
            "Specific fallback".to_string(),
        )
        .unwrap();

    engine.set_online(false);

    // Should match the most specific pattern first
    let request = DeterministicInferenceRequest::new(
        "This is test123 specific".to_string(),
        100,
        "claude-3-opus".to_string(),
    );

    let response = engine.infer(request).await;
    // Should return one of the matching responses
    assert!(response.is_ok());
}

#[test]
fn test_deterministic_inference_request_creation() {
    let req = DeterministicInferenceRequest::new(
        "test".to_string(),
        100,
        "model".to_string(),
    );

    assert_eq!(req.temperature, 0.0); // Must be deterministic
    assert_eq!(req.max_tokens, 100);
    assert_eq!(req.model, "model");
}

#[test]
fn test_fingerprint_is_sha256() {
    let req = DeterministicInferenceRequest::new(
        "test".to_string(),
        100,
        "model".to_string(),
    );

    let fingerprint = req.fingerprint();
    // SHA256 produces 64-character hex strings
    assert_eq!(fingerprint.len(), 64);
    // Should be valid hex
    assert!(fingerprint.chars().all(|c| c.is_ascii_hexdigit()));
}

#[tokio::test]
async fn test_offline_with_cache_hit() {
    let engine = DeterministicLLMEngine::new(create_test_key());

    // Make first request to cache it
    let request = DeterministicInferenceRequest::new(
        "Cached prompt".to_string(),
        100,
        "claude-3".to_string(),
    );

    let _ = engine.infer(request.clone()).await;
    let metrics_before = engine.metrics();
    assert_eq!(metrics_before.cache_hits, 0); // First call is a miss

    // Go offline
    engine.set_online(false);

    // Same prompt should hit cache (no fallback needed)
    let response = engine.infer(request).await;
    assert!(response.is_ok());

    let metrics_after = engine.metrics();
    assert_eq!(metrics_after.cache_hits, 1); // Cache hit should work offline
}

#[tokio::test]
async fn test_metrics_with_offline_fallbacks() {
    let engine = DeterministicLLMEngine::new(create_test_key());

    engine
        .register_fallback_template(
            "test".to_string(),
            "test".to_string(),
            "Offline response".to_string(),
        )
        .unwrap();

    engine.set_online(false);

    for _ in 0..5 {
        let request = DeterministicInferenceRequest::new(
            "test prompt".to_string(),
            100,
            "claude-3".to_string(),
        );
        let _ = engine.infer(request).await;
    }

    let metrics = engine.metrics();
    assert!(metrics.offline_fallbacks >= 1);
}
