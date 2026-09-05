use crate::alignment::{CrossModalValidator, MintConfig, NoiseResilienceGate, RomaConfig};
use crate::learning::GhostBranchBuffer;

pub struct AlignmentValidator {
    roma_gate: NoiseResilienceGate,
    mint_validator: CrossModalValidator,
}

impl AlignmentValidator {
    pub fn new(roma_gate: NoiseResilienceGate, mint_validator: CrossModalValidator) -> Self {
        Self {
            roma_gate,
            mint_validator,
        }
    }

    pub fn new_with_defaults() -> Self {
        let roma_config = RomaConfig {
            noise_injection_enabled: true,
            corruption_scenarios: vec![
                "malformed_json".to_string(),
                "network_timeout".to_string(),
                "rate_limit_429".to_string(),
            ],
            stability_threshold: 0.85,
        };

        let mint_config = MintConfig {
            cross_modal_tests: vec![
                "spatial_reasoning".to_string(),
                "temporal_reasoning".to_string(),
                "audio_reasoning".to_string(),
            ],
            degradation_threshold: 0.10,
        };

        Self {
            roma_gate: NoiseResilienceGate::new(roma_config),
            mint_validator: CrossModalValidator::new(mint_config),
        }
    }

    /// Validate ROMA gate (noise resilience)
    pub async fn validate_roma(&self, ghost_branch: &GhostBranchBuffer) -> Result<bool, String> {
        self.roma_gate.validate(ghost_branch).await
    }

    /// Validate MINT gate (cross-modal preservation)
    pub async fn validate_mint(&self, baseline: f32, post_swap: f32) -> Result<bool, String> {
        // Simple spatial reasoning check for baseline test
        self.mint_validator
            .validate_spatial_reasoning(baseline, post_swap)
            .await
    }

    /// Authorize swap only if BOTH gates pass
    pub async fn authorize_swap(
        &self,
        ghost_branch: &GhostBranchBuffer,
        baseline_modal_score: f32,
        post_swap_modal_score: f32,
    ) -> Result<bool, String> {
        let roma_pass = self.validate_roma(ghost_branch).await?;
        let mint_pass = self
            .validate_mint(baseline_modal_score, post_swap_modal_score)
            .await?;

        // CRITICAL: Swap authorized only if BOTH gates pass
        Ok(roma_pass && mint_pass)
    }
}
