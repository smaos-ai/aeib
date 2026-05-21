/// Phase 41 RED Phase: OpenClaw-RL Integration Tests
/// End-to-end tests for CIPO continuous learning pipeline fail-closed invariants

#[cfg(test)]
mod integration_tests {
    use crate::handlers::openclaw_rl::{
        OpenClawRL, FailureToCorrection, RewardSignal, LoRAWeights, UnifiedMemoryMetrics,
        OpenClawRLError,
    };

    #[tokio::test]
    async fn test_trajectory_verification_complete_causal_chain() {
        // GIVEN: Complete trajectory with failure-to-correction causal chain
        let trajectory = FailureToCorrection {
            trajectory_id: "traj-integration-001".to_string(),
            session_id: "sess-integration-001".to_string(),
            failure_event: "Query returned syntax error".to_string(),
            correction_event: "Reordered WHERE clause and re-executed".to_string(),
            failure_timestamp: "2026-05-21T12:00:00Z".to_string(),
            correction_timestamp: "2026-05-21T12:00:05Z".to_string(),
        };

        // WHEN: Verifying trajectory causality with complete chain
        let result = OpenClawRL::verify_trajectory_causality(trajectory).await;

        // THEN: Should accept complete causal chain (fails in RED phase, passes in GREEN)
        assert!(result.is_ok(), "Complete trajectory should be accepted");
        let trajectory_id = result.unwrap();
        assert_eq!(trajectory_id, "traj-integration-001", "Should return trajectory ID");
    }

    #[tokio::test]
    async fn test_trajectory_verification_rejects_empty_correction() {
        // GIVEN: Trajectory with empty correction event (broken chain)
        let trajectory = FailureToCorrection {
            trajectory_id: "traj-broken-001".to_string(),
            session_id: "sess-broken-001".to_string(),
            failure_event: "Agent action failed".to_string(),
            correction_event: "".to_string(), // No correction recorded
            failure_timestamp: "2026-05-21T12:00:00Z".to_string(),
            correction_timestamp: "2026-05-21T12:00:00Z".to_string(),
        };

        // WHEN: Verifying trajectory causality
        let result = OpenClawRL::verify_trajectory_causality(trajectory).await;

        // THEN: Rejects broken causal chain (fail-closed)
        assert!(result.is_err(), "Trajectory with empty correction should be rejected");
        assert!(
            matches!(result.unwrap_err(), OpenClawRLError::TrajectoryMissingCausalChain),
            "Should return TrajectoryMissingCausalChain error"
        );
    }

    #[tokio::test]
    async fn test_reward_signal_strict_validation_all_fields() {
        // GIVEN: Complete reward signal with all validation fields
        let signal = RewardSignal {
            trajectory_id: "traj-reward-001".to_string(),
            reward_score: 0.95,
            stdout_check: true,
            stderr_contains_error: false,
            exit_code: 0,
        };

        // WHEN: Validating reward signal with all required checks
        let result = OpenClawRL::validate_reward_signal(signal).await;

        // THEN: Should accept complete signal (fails in RED phase, passes in GREEN)
        assert!(result.is_ok(), "Valid reward signal should be accepted");
        let score = result.unwrap();
        assert_eq!(score, 0.95, "Should return correct reward score");
    }

    #[tokio::test]
    async fn test_reward_signal_rejects_negative_exit_code() {
        // GIVEN: Reward signal with error exit code but positive reward
        let signal = RewardSignal {
            trajectory_id: "traj-error-001".to_string(),
            reward_score: 0.8, // Positive reward
            stdout_check: true,
            stderr_contains_error: false,
            exit_code: 1, // Non-zero exit code (failure)
        };

        // WHEN: Validating reward signal
        let result = OpenClawRL::validate_reward_signal(signal).await;

        // THEN: Rejects ambiguous signal (fail-closed)
        assert!(result.is_err(), "Reward signal with error exit code should be rejected");
        assert!(
            matches!(result.unwrap_err(), OpenClawRLError::RewardSignalMalformed),
            "Should return RewardSignalMalformed error"
        );
    }

    #[tokio::test]
    async fn test_lora_safety_gate_requires_ap2_mandate() {
        // GIVEN: LoRA weights with empty AP2 mandate signature
        let weights = LoRAWeights {
            sovereign_capsule_id: "capsule-unsafe-001".to_string(),
            weights_hash: "sha256:def456".to_string(),
            ap2_mandate_signature: None,
            timestamp: "2026-05-21T12:00:00Z".to_string(),
        };

        // WHEN: Attempting hot-swap without mandate
        let result = OpenClawRL::hot_swap_lora_weights(weights).await;

        // THEN: Rejects hot-swap (fail-closed, 403 FORBIDDEN)
        assert!(result.is_err(), "LoRA hot-swap without AP2 mandate should fail");
        assert!(
            matches!(result.unwrap_err(), OpenClawRLError::LoRASafetyGateViolation),
            "Should return LoRASafetyGateViolation error"
        );
    }

    #[tokio::test]
    async fn test_lora_safety_gate_accepts_signed_mandate() {
        // GIVEN: LoRA weights with valid AP2 mandate signature
        let weights = LoRAWeights {
            sovereign_capsule_id: "capsule-safe-001".to_string(),
            weights_hash: "sha256:ghi789".to_string(),
            ap2_mandate_signature: Some("sig:ed25519:abc...xyz".to_string()),
            timestamp: "2026-05-21T12:00:00Z".to_string(),
        };

        // WHEN: Attempting hot-swap with valid AP2 mandate
        let result = OpenClawRL::hot_swap_lora_weights(weights).await;

        // THEN: Should accept hot-swap (fails in RED phase, passes in GREEN)
        assert!(result.is_ok(), "LoRA weights with AP2 mandate should be accepted");
        let capsule_id = result.unwrap();
        assert_eq!(capsule_id, "capsule-safe-001", "Should load correct capsule into Rapid-MLX");
    }

    #[tokio::test]
    async fn test_circuit_breaker_allows_safe_memory_levels() {
        // GIVEN: Memory pressure at 70% (below 85% threshold)
        let metrics = UnifiedMemoryMetrics {
            memory_pressure_percent: 70.0,
            available_memory_mb: 2048,
            neural_engine_utilization: 0.5,
        };

        // WHEN: Checking memory circuit breaker at safe levels
        let result = OpenClawRL::check_memory_circuit_breaker(metrics).await;

        // THEN: Should allow training to continue (fails in RED phase, passes in GREEN)
        assert!(result.is_ok(), "Memory pressure at 70% should allow training to continue");
    }

    #[tokio::test]
    async fn test_circuit_breaker_pauses_at_exactly_85_percent() {
        // GIVEN: Memory pressure at exactly 85% (at threshold)
        let metrics = UnifiedMemoryMetrics {
            memory_pressure_percent: 85.0,
            available_memory_mb: 1024,
            neural_engine_utilization: 0.8,
        };

        // WHEN: Checking memory circuit breaker at threshold (threshold specifies > 85%)
        let result = OpenClawRL::check_memory_circuit_breaker(metrics).await;

        // THEN: Should allow at threshold - circuit breaks only if > 85% (fails in RED, passes in GREEN)
        assert!(result.is_ok(), "Memory pressure at exactly 85% should allow training to continue");
    }

    #[tokio::test]
    async fn test_circuit_breaker_triggers_graceful_pause_at_92_percent() {
        // GIVEN: Memory pressure at 92% (exceeds 85% threshold)
        let metrics = UnifiedMemoryMetrics {
            memory_pressure_percent: 92.0,
            available_memory_mb: 256,
            neural_engine_utilization: 0.95,
        };

        // WHEN: Checking memory circuit breaker
        let result = OpenClawRL::check_memory_circuit_breaker(metrics).await;

        // THEN: Triggers graceful pause (fail-closed, 429 backpressure)
        assert!(result.is_err(), "Memory pressure at 92% should trigger circuit breaker");
        assert!(
            matches!(result.unwrap_err(), OpenClawRLError::ResourceCircuitBreakerTriggered),
            "Should return ResourceCircuitBreakerTriggered error"
        );
    }

    #[tokio::test]
    async fn test_openclaw_complete_training_workflow() {
        // GIVEN: Complete CIPO workflow: trajectory → reward → weights → memory check

        // Stage 1: Extract trajectory with failure-to-correction chain
        let trajectory = FailureToCorrection {
            trajectory_id: "workflow-001".to_string(),
            session_id: "sess-workflow-001".to_string(),
            failure_event: "Agent failed to parse API response".to_string(),
            correction_event: "Added JSON error handling and retried".to_string(),
            failure_timestamp: "2026-05-21T12:00:00Z".to_string(),
            correction_timestamp: "2026-05-21T12:00:02Z".to_string(),
        };

        // Verify trajectory causality
        let traj_result = OpenClawRL::verify_trajectory_causality(trajectory).await;
        assert!(traj_result.is_ok(), "Stage 1: Trajectory with complete causal chain should be verified");

        // Stage 2: Compute reward signal from corrected trajectory
        let reward = RewardSignal {
            trajectory_id: "workflow-001".to_string(),
            reward_score: 0.92,
            stdout_check: true,
            stderr_contains_error: false,
            exit_code: 0,
        };

        // Validate reward strictness
        let reward_result = OpenClawRL::validate_reward_signal(reward).await;
        assert!(reward_result.is_ok(), "Stage 2: Valid reward signal should be accepted");
        assert_eq!(reward_result.unwrap(), 0.92, "Should return correct reward score");

        // Stage 3: Generate LoRA weights with AP2 mandate
        let weights = LoRAWeights {
            sovereign_capsule_id: "capsule-workflow-001".to_string(),
            weights_hash: "sha256:workflow...hash".to_string(),
            ap2_mandate_signature: Some("sig:ed25519:workflow...mandate".to_string()),
            timestamp: "2026-05-21T12:00:03Z".to_string(),
        };

        // Hot-swap into Rapid-MLX with mandate
        let swap_result = OpenClawRL::hot_swap_lora_weights(weights).await;
        assert!(swap_result.is_ok(), "Stage 3: LoRA weights with AP2 mandate should be hot-swapped");
        assert_eq!(swap_result.unwrap(), "capsule-workflow-001", "Should load correct capsule ID");

        // Stage 4: Check memory pressure before next iteration
        let metrics = UnifiedMemoryMetrics {
            memory_pressure_percent: 78.0,
            available_memory_mb: 1536,
            neural_engine_utilization: 0.6,
        };

        // Verify circuit breaker allows continued training
        let circuit_result = OpenClawRL::check_memory_circuit_breaker(metrics).await;
        assert!(circuit_result.is_ok(), "Stage 4: Safe memory pressure should allow training to continue");

        // THEN: Complete workflow executes without blocking the active agent (fails in RED, passes in GREEN)
    }
}
