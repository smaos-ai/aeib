use l6_infrastructure::{FreeTokenValidator, QwenInferenceConfig, InferenceResult};

#[test]
fn test_freetoken_validator_creation() {
    let config = QwenInferenceConfig::new("qwen-290b".to_string(), 8);
    let validator = FreeTokenValidator::new(config);
    assert!(validator.is_ok());
}

#[test]
fn test_qwen_inference_config_defaults() {
    let config = QwenInferenceConfig::new("qwen-290b".to_string(), 8);
    assert_eq!(config.model_name, "qwen-290b");
    assert_eq!(config.gpu_vram_gb, 8);
    assert!(config.quantization_bits > 0);
}

#[test]
fn test_freetoken_invalid_config_empty_model() {
    let config = QwenInferenceConfig::new("".to_string(), 8);
    let validator = FreeTokenValidator::new(config);
    assert!(validator.is_err());
}

#[test]
fn test_freetoken_invalid_config_insufficient_vram() {
    let config = QwenInferenceConfig::new("qwen-290b".to_string(), 2);
    let validator = FreeTokenValidator::new(config);
    assert!(validator.is_err());
}

#[test]
fn test_freetoken_validate_environment() {
    let config = QwenInferenceConfig::new("qwen-290b".to_string(), 8);
    let validator = FreeTokenValidator::new(config).unwrap();
    let result = validator.validate_environment();
    assert!(result.is_ok());
}

#[test]
fn test_freetoken_estimate_inference_time() {
    let config = QwenInferenceConfig::new("qwen-290b".to_string(), 8);
    let validator = FreeTokenValidator::new(config).unwrap();
    let time_ms = validator.estimate_inference_time_ms(100);
    assert!(time_ms > 0);
}

#[test]
fn test_freetoken_can_run_qwen() {
    let config = QwenInferenceConfig::new("qwen-290b".to_string(), 8);
    let validator = FreeTokenValidator::new(config).unwrap();
    let can_run = validator.can_run_qwen();
    assert!(can_run);
}

#[test]
fn test_freetoken_inference_result() {
    let result = InferenceResult::new(
        "test-prompt".to_string(),
        "test-output".to_string(),
        100,
        25.5,
    );
    assert_eq!(result.prompt, "test-prompt");
    assert_eq!(result.output, "test-output");
    assert_eq!(result.tokens_generated, 100);
    assert_eq!(result.throughput_tok_s, 25.5);
}

#[test]
fn test_freetoken_simulate_inference() {
    let config = QwenInferenceConfig::new("qwen-290b".to_string(), 8);
    let validator = FreeTokenValidator::new(config).unwrap();
    let result = validator.simulate_inference(100);
    assert!(result.is_ok());
    let inference = result.unwrap();
    assert_eq!(inference.tokens_generated, 100);
    assert!(inference.throughput_tok_s > 0.0);
}

#[test]
fn test_freetoken_audit_log() {
    let config = QwenInferenceConfig::new("qwen-290b".to_string(), 8);
    let validator = FreeTokenValidator::new(config).unwrap();
    validator.validate_environment().ok();
    let audit = validator.get_audit_log();
    assert!(!audit.is_empty());
}
