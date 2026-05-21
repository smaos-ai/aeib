/// Phase 41: OpenClaw-RL & CIPO Continuous Learning Loop
/// RED phase: Fail-closed invariants for asynchronous CIPO training pipeline

use serde::{Deserialize, Serialize};

/// Trajectory from claude-mem SQLite: failure-to-correction causal chain
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FailureToCorrection {
    pub trajectory_id: String,
    pub session_id: String,
    pub failure_event: String,
    pub correction_event: String,
    pub failure_timestamp: String,
    pub correction_timestamp: String,
}

/// Binary RL (GRPO) reward signal
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RewardSignal {
    pub trajectory_id: String,
    pub reward_score: f32,
    pub stdout_check: bool,
    pub stderr_contains_error: bool,
    pub exit_code: i32,
}

/// Generated LoRA weights for Rapid-MLX hot-swap
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LoRAWeights {
    pub sovereign_capsule_id: String,
    pub weights_hash: String,
    pub ap2_mandate_signature: Option<String>,
    pub timestamp: String,
}

/// Apple Silicon resource metrics during distillation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UnifiedMemoryMetrics {
    pub memory_pressure_percent: f32,
    pub available_memory_mb: u64,
    pub neural_engine_utilization: f32,
}

/// OpenClaw-RL error types (fail-closed)
#[derive(Debug, Clone)]
pub enum OpenClawRLError {
    TrajectoryMissingCausalChain,      // 400: No failure-to-correction link
    LoRASafetyGateViolation,            // 403: Missing AP2 mandate signature
    RewardSignalMalformed,              // 400: Missing/ambiguous reward fields
    ResourceCircuitBreakerTriggered,    // 429: Memory pressure > 85%
    MemoryPressureExceeded,             // 503: Cannot proceed with training
}

/// OpenClaw-RL handler (fail-closed invariants enforced)
pub struct OpenClawRL;

impl OpenClawRL {
    /// Extract and verify trajectory has failure-to-correction causal chain
    /// Fail-closed: Reject payload if no clear failure event or correction event
    pub async fn verify_trajectory_causality(trajectory: FailureToCorrection) -> Result<String, OpenClawRLError> {
        // TODO: Implement in GREEN phase
        Err(OpenClawRLError::TrajectoryMissingCausalChain)
    }

    /// Validate reward signal strictness
    /// Fail-closed: Reject malformed or ambiguous reward signals
    pub async fn validate_reward_signal(signal: RewardSignal) -> Result<f32, OpenClawRLError> {
        // TODO: Implement in GREEN phase
        Err(OpenClawRLError::RewardSignalMalformed)
    }

    /// Hot-swap LoRA weights into Rapid-MLX
    /// Fail-closed: Require cryptographically signed AP2 mandate
    pub async fn hot_swap_lora_weights(weights: LoRAWeights) -> Result<String, OpenClawRLError> {
        // TODO: Implement in GREEN phase
        Err(OpenClawRLError::LoRASafetyGateViolation)
    }

    /// Check Apple Silicon unified memory pressure
    /// Fail-closed: Graceful pause if pressure > 85%
    pub async fn check_memory_circuit_breaker(metrics: UnifiedMemoryMetrics) -> Result<(), OpenClawRLError> {
        // TODO: Implement in GREEN phase
        Err(OpenClawRLError::ResourceCircuitBreakerTriggered)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_trajectory_verification_missing_failure_event() {
        // GIVEN: Trajectory with missing failure event
        let trajectory = FailureToCorrection {
            trajectory_id: "traj-001".to_string(),
            session_id: "sess-001".to_string(),
            failure_event: "".to_string(), // Empty failure event
            correction_event: "Corrected query syntax".to_string(),
            failure_timestamp: "2026-05-21T12:00:00Z".to_string(),
            correction_timestamp: "2026-05-21T12:00:01Z".to_string(),
        };

        // WHEN: Verifying trajectory causality
        let result = OpenClawRL::verify_trajectory_causality(trajectory).await;

        // THEN: Rejects missing failure event (fail-closed)
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), OpenClawRLError::TrajectoryMissingCausalChain));
    }

    #[tokio::test]
    async fn test_reward_signal_missing_stdout_check() {
        // GIVEN: Reward signal with missing stdout_check
        let signal = RewardSignal {
            trajectory_id: "traj-002".to_string(),
            reward_score: 0.85,
            stdout_check: false, // Missing required validation
            stderr_contains_error: false,
            exit_code: 0,
        };

        // WHEN: Validating reward signal
        let result = OpenClawRL::validate_reward_signal(signal).await;

        // THEN: Rejects malformed signal (fail-closed)
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), OpenClawRLError::RewardSignalMalformed));
    }

    #[tokio::test]
    async fn test_lora_safety_gate_missing_ap2_mandate() {
        // GIVEN: LoRA weights without AP2 mandate signature
        let weights = LoRAWeights {
            sovereign_capsule_id: "capsule-001".to_string(),
            weights_hash: "sha256:abc123".to_string(),
            ap2_mandate_signature: None, // Missing AP2 mandate
            timestamp: "2026-05-21T12:00:00Z".to_string(),
        };

        // WHEN: Hot-swapping LoRA weights
        let result = OpenClawRL::hot_swap_lora_weights(weights).await;

        // THEN: Rejects without AP2 mandate (fail-closed, 403)
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), OpenClawRLError::LoRASafetyGateViolation));
    }

    #[tokio::test]
    async fn test_circuit_breaker_memory_pressure_exceeds_85() {
        // GIVEN: Memory pressure at 86% (exceeds 85% threshold)
        let metrics = UnifiedMemoryMetrics {
            memory_pressure_percent: 86.0,
            available_memory_mb: 512,
            neural_engine_utilization: 0.8,
        };

        // WHEN: Checking memory circuit breaker
        let result = OpenClawRL::check_memory_circuit_breaker(metrics).await;

        // THEN: Triggers graceful pause (fail-closed, 429)
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), OpenClawRLError::ResourceCircuitBreakerTriggered));
    }
}
