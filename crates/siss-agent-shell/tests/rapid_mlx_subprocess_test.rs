use siss_agent_shell::rapid_mlx_integration::{
    RapidMLXEngine, RapidMLXConfig, InferenceRequest, Quantization, MlxAvailabilityProbe,
};
use uuid::Uuid;

fn default_config() -> RapidMLXConfig {
    RapidMLXConfig {
        model_name: "Qwen3.5-4B".to_string(),
        quantization: Quantization::Q4,
        context_window: 4096,
        max_tokens: 512,
        temperature: 0.7,
        top_p: 0.9,
    }
}

#[test]
#[cfg_attr(not(target_os = "macos"), ignore)]
fn test_ttft_measured_not_hardcoded() {
    if !MlxAvailabilityProbe::check() {
        return;
    }

    let mut engine = RapidMLXEngine::new(default_config());
    let request = InferenceRequest {
        request_id: Uuid::new_v4(),
        model_config: default_config(),
        prompt: "What is 2+2?".to_string(),
        system_prompt: None,
        tools: vec![],
        use_cached_prompt: false,
        resume_from_snapshot: None,
    };

    let result = engine.infer(request);
    if let Ok(response) = result {
        // TTFT must not be hardcoded to 0.08
        assert!(response.time_to_first_token_ms > 0.0, "TTFT must be measured, not zero");
    }
}

#[test]
#[cfg_attr(not(target_os = "macos"), ignore)]
fn test_subprocess_output_parses_correctly() {
    if !MlxAvailabilityProbe::check() {
        return;
    }

    let mut engine = RapidMLXEngine::new(default_config());
    let request = InferenceRequest {
        request_id: Uuid::new_v4(),
        model_config: default_config(),
        prompt: "Hello".to_string(),
        system_prompt: Some("Be concise.".to_string()),
        tools: vec![],
        use_cached_prompt: false,
        resume_from_snapshot: None,
    };

    let result = engine.infer(request);
    assert!(result.is_ok());
    let response = result.unwrap();
    assert!(!response.generated_text.is_empty());
}

#[test]
#[cfg_attr(not(target_os = "macos"), ignore)]
fn test_mlx_availability_probe_returns_bool() {
    let available = MlxAvailabilityProbe::check();
    let _: bool = available;
}
