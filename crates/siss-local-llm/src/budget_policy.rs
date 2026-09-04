/// Budget-adaptive token allocation policy (Q* optimization)
///
/// Reduces token generation under bandwidth constraints using anomaly scoring.
/// Implements three tiers of reduction based on network conditions.

/// Token budget policy for bandwidth-constrained environments
#[derive(Debug, Clone)]
pub struct BudgetPolicy {
    /// Minimum viable token budget (always allocated)
    min_tokens: usize,
}

impl BudgetPolicy {
    /// Create a new budget policy with defaults
    pub fn new() -> Self {
        BudgetPolicy { min_tokens: 300 }
    }

    /// Compute token budget based on anomaly score
    ///
    /// # Arguments
    /// * `requested` - Requested number of tokens
    /// * `anomaly_score` - Network anomaly score (0.0 = normal, 1.5+ = critical)
    ///
    /// # Reduction Tiers
    /// - Normal (anomaly <= 0.3): 1.0x (no reduction)
    /// - Warning (0.3-0.8): linear interpolation 1.0 -> 0.8
    /// - Critical (0.8-1.5): linear interpolation 0.8 -> 0.3
    /// - Beyond critical (>1.5): 0.3x (minimum)
    pub fn compute_token_budget(&self, requested: usize, anomaly_score: f32) -> usize {
        let reduction_factor = if anomaly_score <= 0.3 {
            1.0
        } else if anomaly_score <= 0.8 {
            // Warning: linear from 1.0 to 0.8
            let progress = (anomaly_score - 0.3) / (0.8 - 0.3);
            1.0 - (progress * 0.2)
        } else if anomaly_score <= 1.5 {
            // Critical: linear from 0.8 to 0.3
            let progress = (anomaly_score - 0.8) / (1.5 - 0.8);
            0.8 - (progress * 0.5)
        } else {
            // Beyond critical: minimum 0.3x
            0.3
        };

        let reduced = (requested as f32 * reduction_factor).ceil() as usize;
        reduced.max(self.min_tokens)
    }
}

impl Default for BudgetPolicy {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_normal_bandwidth() {
        let policy = BudgetPolicy::new();
        assert_eq!(policy.compute_token_budget(1000, 0.0), 1000);
        assert_eq!(policy.compute_token_budget(1000, 0.3), 1000);
    }

    #[test]
    fn test_warning_bandwidth() {
        let policy = BudgetPolicy::new();
        let budget = policy.compute_token_budget(1000, 0.55);
        assert!(budget < 1000);
        assert!(budget >= 800);
    }

    #[test]
    fn test_critical_bandwidth() {
        let policy = BudgetPolicy::new();
        let budget = policy.compute_token_budget(1000, 1.15);
        assert!(budget < 800);
        assert!(budget >= 300);
    }

    #[test]
    fn test_beyond_critical() {
        let policy = BudgetPolicy::new();
        assert_eq!(policy.compute_token_budget(1000, 1.5), 300);
        assert_eq!(policy.compute_token_budget(1000, 2.0), 300);
    }

    #[test]
    fn test_monotonic_reduction() {
        let policy = BudgetPolicy::new();
        let mut prev = policy.compute_token_budget(1000, 0.0);

        for i in 1..=15 {
            let anomaly = i as f32 * 0.1;
            let curr = policy.compute_token_budget(1000, anomaly);
            assert!(
                curr <= prev,
                "Budget should decrease monotonically (anomaly {}: {} > {})",
                anomaly,
                curr,
                prev
            );
            prev = curr;
        }
    }
}
