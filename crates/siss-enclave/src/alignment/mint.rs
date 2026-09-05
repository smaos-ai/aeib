#[derive(Debug, Clone)]
pub struct MintConfig {
    pub cross_modal_tests: Vec<String>,
    pub degradation_threshold: f32,
}

pub struct CrossModalValidator {
    config: MintConfig,
}

impl CrossModalValidator {
    pub fn new(config: MintConfig) -> Self {
        Self { config }
    }

    /// Validate spatial reasoning capability preservation
    pub async fn validate_spatial_reasoning(
        &self,
        baseline: f32,
        post_swap: f32,
    ) -> Result<bool, String> {
        let degradation = (baseline - post_swap).abs();
        let degradation_ratio = degradation / baseline;

        // MINT passes if degradation ≤ threshold (default 10%)
        Ok(degradation_ratio <= self.config.degradation_threshold)
    }

    /// Validate temporal reasoning capability preservation
    pub async fn validate_temporal_reasoning(
        &self,
        baseline: f32,
        post_swap: f32,
    ) -> Result<bool, String> {
        let degradation = (baseline - post_swap).abs();
        let degradation_ratio = degradation / baseline;

        Ok(degradation_ratio <= self.config.degradation_threshold)
    }

    /// Validate audio reasoning capability preservation
    pub async fn validate_audio_reasoning(
        &self,
        baseline: f32,
        post_swap: f32,
    ) -> Result<bool, String> {
        let degradation = (baseline - post_swap).abs();
        let degradation_ratio = degradation / baseline;

        Ok(degradation_ratio <= self.config.degradation_threshold)
    }

    /// Run all configured cross-modal tests
    pub async fn validate_all(
        &self,
        baseline_scores: &std::collections::HashMap<String, f32>,
        post_swap_scores: &std::collections::HashMap<String, f32>,
    ) -> Result<bool, String> {
        for modal in &self.config.cross_modal_tests {
            let baseline = baseline_scores.get(modal).copied().unwrap_or(0.0);
            let post = post_swap_scores.get(modal).copied().unwrap_or(0.0);

            let pass = match modal.as_str() {
                "spatial_reasoning" => self.validate_spatial_reasoning(baseline, post).await?,
                "temporal_reasoning" => self.validate_temporal_reasoning(baseline, post).await?,
                "audio_reasoning" => self.validate_audio_reasoning(baseline, post).await?,
                _ => true,
            };

            if !pass {
                return Ok(false);
            }
        }

        Ok(true)
    }
}
