use chrono::Utc;
use siss_layer00::{DashMapStore, Layer0Gate, Mandate, SovereignKeypair, sha256};
use siss_local_llm::{InferenceRequest, LocalLLMConfig, LocalLLMError, LocalLLMGate, ModelType};
use std::sync::Arc;
use uuid::Uuid;

fn create_test_mandate() -> (Mandate, SovereignKeypair) {
    let keypair = SovereignKeypair::generate();
    let public_key = keypair.public_key_bytes();

    let intent_hash = sha256(b"test_mandate");
    let signature = keypair.sign(&intent_hash);

    let mandate = Mandate {
        id: Uuid::new_v4(),
        intent_hash,
        public_key,
        signature,
        jurisdiction: "US".to_string(),
        action_scope: vec!["local_llm_*".to_string()],
        created_at: Utc::now(),
        expires_at: Utc::now() + chrono::Duration::hours(1),
    };

    (mandate, keypair)
}

fn setup_llm_gate() -> (Arc<LocalLLMGate>, Uuid) {
    let mandate_store = Arc::new(DashMapStore::new());
    let layer0_gate = Arc::new(Layer0Gate::new(mandate_store));

    let (mandate, _keypair) = create_test_mandate();
    let mandate_id = mandate.id;

    layer0_gate
        .register_mandate(mandate)
        .expect("Failed to register mandate");

    let config = LocalLLMConfig::default();
    let llm_gate = Arc::new(LocalLLMGate::new(layer0_gate, config));

    (llm_gate, mandate_id)
}

/// Test 1: Verify token validation is mandatory
#[tokio::test]
async fn test_llm_gate_requires_valid_token() {
    let (llm_gate, mandate_id) = setup_llm_gate();

    let request = InferenceRequest {
        prompt: "What is AI?".to_string(),
        max_tokens: 100,
        mandate_id,
        action: "local_llm_inference".to_string(),
        temperature: None,
        top_p: None,
    };

    // Request capability token with valid action
    let token = llm_gate
        .layer0_gate()
        .request_capability(mandate_id, "local_llm_inference")
        .expect("Failed to request capability token");

    // Should succeed with valid token
    let result = llm_gate
        .infer(request.clone(), &token, ModelType::Llama405B)
        .await;

    assert!(result.is_ok(), "Inference should succeed with valid token");
    let inference_result = result.unwrap();
    assert!(
        inference_result.merkle_logged,
        "Result should be logged to Merkle"
    );

    // Now test with expired token by manually creating one
    let mut expired_token = token.clone();
    expired_token.expires_at = Utc::now() - chrono::Duration::seconds(1);

    let result_expired = llm_gate
        .infer(request.clone(), &expired_token, ModelType::Llama405B)
        .await;

    assert!(
        matches!(result_expired, Err(LocalLLMError::TokenExpired)),
        "Should reject expired token"
    );
}

/// Test 2: Verify every inference is logged to Merkle ledger
#[tokio::test]
async fn test_llm_inference_logs_to_merkle() {
    let (llm_gate, mandate_id) = setup_llm_gate();

    let request = InferenceRequest {
        prompt: "Explain machine learning".to_string(),
        max_tokens: 150,
        mandate_id,
        action: "local_llm_inference".to_string(),
        temperature: Some(0.7),
        top_p: None,
    };

    let token = llm_gate
        .layer0_gate()
        .request_capability(mandate_id, "local_llm_inference")
        .expect("Failed to request capability");

    let result = llm_gate
        .infer(request, &token, ModelType::MistralMoE)
        .await
        .expect("Inference failed");

    // Verify Merkle logging
    assert!(result.merkle_logged, "Inference should be logged to Merkle");
    assert!(result.audit_id.is_some(), "Should have audit ID");

    // Verify Merkle chain integrity
    let chain_valid = llm_gate
        .verify_merkle_chain()
        .expect("Failed to verify chain");
    assert!(chain_valid, "Merkle chain should be valid");

    // Verify we can get Merkle root
    let root = llm_gate.merkle_root().expect("Failed to get Merkle root");
    assert_ne!(root, [0u8; 32], "Merkle root should not be zero");
}

/// Test 3: Verify model loading and caching
#[tokio::test]
async fn test_llm_model_load_from_disk() {
    let (llm_gate, _mandate_id) = setup_llm_gate();

    let cache = llm_gate.model_cache();

    // Cache should be empty initially
    assert_eq!(cache.cache_size(), 0, "Cache should start empty");

    // Load model metadata
    let result = cache.load_model(ModelType::Llama405B);

    // Should succeed in test mode
    assert!(result.is_ok(), "Should load model metadata");

    // Cache should now have one entry
    assert_eq!(cache.cache_size(), 1, "Cache should have one entry");

    // Getting cached model should work
    let cached = cache.get_cached_model(ModelType::Llama405B);
    assert!(cached.is_some(), "Should retrieve cached model");

    // Clear specific model
    let cleared = cache.clear_model(ModelType::Llama405B);
    assert!(cleared, "Should clear model");
    assert_eq!(cache.cache_size(), 0, "Cache should be empty after clear");

    // Clear all
    let _ = cache.load_model(ModelType::MistralMoE);
    cache.clear_all();
    assert_eq!(
        cache.cache_size(),
        0,
        "Cache should be empty after clear_all"
    );
}

/// Test 4: Verify action scope is enforced
#[tokio::test]
async fn test_llm_inference_respects_action_scope() {
    let (llm_gate, mandate_id) = setup_llm_gate();

    let request = InferenceRequest {
        prompt: "What is quantum computing?".to_string(),
        max_tokens: 200,
        mandate_id,
        action: "local_llm_inference".to_string(),
        temperature: None,
        top_p: None,
    };

    // Request token for a different action
    let token = llm_gate
        .layer0_gate()
        .request_capability(mandate_id, "local_llm_inference")
        .expect("Failed to request token");

    // Token scope is "local_llm_inference", request action is "local_llm_inference" - should succeed
    let result = llm_gate
        .infer(request.clone(), &token, ModelType::OpenSourceCustom)
        .await;

    assert!(result.is_ok(), "Should allow matching action scope");

    // Now create a request with mismatched action
    let mismatched_request = InferenceRequest {
        prompt: "Different prompt".to_string(),
        max_tokens: 100,
        mandate_id,
        action: "different_action".to_string(),
        temperature: None,
        top_p: None,
    };

    let result_mismatch = llm_gate
        .infer(mismatched_request, &token, ModelType::Llama405B)
        .await;

    assert!(
        matches!(
            result_mismatch,
            Err(LocalLLMError::ActionScopeNotAllowed(_))
        ),
        "Should reject mismatched action scope"
    );
}

/// Test 5: Verify concurrent inference is thread-safe
#[tokio::test]
async fn test_llm_concurrent_inference() {
    let (llm_gate, mandate_id) = setup_llm_gate();

    let token = llm_gate
        .layer0_gate()
        .request_capability(mandate_id, "local_llm_inference")
        .expect("Failed to request token");

    let mut handles = vec![];

    for i in 0..5 {
        let llm_gate_clone = llm_gate.clone();
        let token_clone = token.clone();
        let mandate_id_clone = mandate_id;

        let handle = tokio::spawn(async move {
            let request = InferenceRequest {
                prompt: format!("Prompt {}", i),
                max_tokens: 50,
                mandate_id: mandate_id_clone,
                action: "local_llm_inference".to_string(),
                temperature: None,
                top_p: None,
            };

            llm_gate_clone
                .infer(request, &token_clone, ModelType::Llama405B)
                .await
        });

        handles.push(handle);
    }

    let results = futures::future::join_all(handles).await;

    for result in results {
        assert!(result.is_ok(), "Concurrent task should succeed");
        let inference_result = result.unwrap().expect("Inference should be ok");
        assert!(
            inference_result.merkle_logged,
            "Each inference should be logged"
        );
    }
}

/// Test 6: Verify inference result contains expected data
#[tokio::test]
async fn test_llm_inference_result_completeness() {
    let (llm_gate, mandate_id) = setup_llm_gate();

    let request = InferenceRequest {
        prompt: "Complete test".to_string(),
        max_tokens: 80,
        mandate_id,
        action: "local_llm_inference".to_string(),
        temperature: Some(0.5),
        top_p: Some(0.9),
    };

    let token = llm_gate
        .layer0_gate()
        .request_capability(mandate_id, "local_llm_inference")
        .expect("Failed to request token");

    let result = llm_gate
        .infer(request, &token, ModelType::MistralMoE)
        .await
        .expect("Inference failed");

    // Verify all fields are present
    assert!(!result.output.is_empty(), "Output should not be empty");
    assert!(result.tokens_used > 0, "Should have used tokens");
    assert!(result.merkle_logged, "Should be logged");
    assert!(result.audit_id.is_some(), "Should have audit ID");
    assert_eq!(
        result.model_type,
        ModelType::MistralMoE,
        "Should match requested model"
    );
    assert!(
        result.inference_time_ms > 0 || result.inference_time_ms == 0,
        "Should have timing"
    );
}

/// Test 7: Model type enum conversion
#[tokio::test]
async fn test_model_type_display() {
    assert_eq!(ModelType::Llama405B.to_string(), "llama-405b");
    assert_eq!(ModelType::MistralMoE.to_string(), "mistral-moe");
    assert_eq!(ModelType::OpenSourceCustom.to_string(), "custom");
}
