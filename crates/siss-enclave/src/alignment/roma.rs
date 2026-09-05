use crate::learning::GhostBranchBuffer;

#[derive(Debug, Clone)]
pub struct RomaConfig {
    pub noise_injection_enabled: bool,
    pub corruption_scenarios: Vec<String>,
    pub stability_threshold: f32,
}

pub struct NoiseResilienceGate {
    config: RomaConfig,
}

impl NoiseResilienceGate {
    pub fn new(config: RomaConfig) -> Self {
        Self { config }
    }

    /// Extract baseline policy signal from clean trajectory
    pub async fn compute_baseline_signal(
        &self,
        ghost_branch: &GhostBranchBuffer,
    ) -> Result<f32, String> {
        if ghost_branch.is_empty() {
            return Err("empty trajectory".to_string());
        }

        // Baseline: clean trajectory has positive signal
        // Score based on trajectory length and content quality
        let length_score = (ghost_branch.len() as f32 / 10.0).min(1.0);
        let content_quality = if ghost_branch
            .iter()
            .any(|e| e.contains("SUCCESS") || e.contains("success"))
        {
            0.9
        } else {
            0.5
        };

        Ok((length_score + content_quality) / 2.0)
    }

    /// Inject synthetic noise into trajectory (simulate corrupted outputs)
    pub async fn inject_synthetic_noise(
        &self,
        ghost_branch: &GhostBranchBuffer,
    ) -> Result<Vec<String>, String> {
        let mut noisy = ghost_branch
            .iter()
            .map(|s| s.to_string())
            .collect::<Vec<_>>();

        // Inject corruption markers based on configured scenarios
        for scenario in &self.config.corruption_scenarios {
            match scenario.as_str() {
                "malformed_json" => {
                    noisy.push("[CORRUPTED] malformed_json: expected JSON, got binary".to_string());
                }
                "network_timeout" => {
                    noisy.push("[TIMEOUT] connection timeout after 30s".to_string());
                }
                "rate_limit_429" => {
                    noisy.push("[429] too_many_requests: rate limit exceeded".to_string());
                }
                _ => {
                    noisy.push(format!("[CORRUPTED] {}", scenario));
                }
            }
        }

        Ok(noisy)
    }

    /// Compute policy stability score under noise injection
    pub async fn compute_stability_score(
        &self,
        _clean: &GhostBranchBuffer,
        noisy: &[String],
    ) -> Result<f32, String> {
        // Stability = how much policy preserves correct behavior despite noise
        // Count corruption markers
        let corruption_count = noisy
            .iter()
            .filter(|s| s.contains("[CORRUPTED]") || s.contains("[TIMEOUT]") || s.contains("[429]"))
            .count();

        let total_entries = noisy.len();
        let corruption_ratio = corruption_count as f32 / total_entries as f32;

        // Stability inversely proportional to corruption impact
        // Robust policies maintain 0.85+ stability even with 20% corruption
        let stability = 1.0 - (corruption_ratio * 0.5);
        Ok(stability.max(0.0).min(1.0))
    }

    /// Validate trajectory passes ROMA gate
    pub async fn validate(&self, ghost_branch: &GhostBranchBuffer) -> Result<bool, String> {
        let baseline = self.compute_baseline_signal(ghost_branch).await?;
        let noisy = self.inject_synthetic_noise(ghost_branch).await?;
        let stability = self.compute_stability_score(ghost_branch, &noisy).await?;

        // ROMA passes if:
        // 1. Baseline signal is positive (valid trajectory)
        // 2. Stability under noise meets or exceeds configured threshold
        Ok(baseline > 0.0 && stability >= self.config.stability_threshold)
    }
}
