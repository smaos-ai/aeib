pub struct ProofOfSapience;

impl ProofOfSapience {
    /// Computes trust score as product of three factors: authority, accuracy, recency
    /// Result is clamped to [0, 1] range
    pub fn compute_trust_score(
        base_authority: f64,
        domain_accuracy: f64,
        recency_weight: f64,
    ) -> f64 {
        (base_authority * domain_accuracy * recency_weight).max(0.0).min(1.0)
    }

    /// Ebbinghaus decay: accuracy decays exponentially with half-life
    /// Formula: accuracy * 0.5^(days_elapsed / half_life_days)
    pub fn decay_accuracy(accuracy: f64, days_elapsed: f64, half_life_days: f64) -> f64 {
        if half_life_days <= 0.0 {
            return accuracy;
        }
        let decay_exponent = days_elapsed / half_life_days;
        accuracy * (0.5_f64).powf(decay_exponent)
    }

    /// Sybil resistance: caps score at 0.95 to prevent artificial inflation
    pub fn cap_score(raw_score: f64) -> f64 {
        raw_score.min(0.95)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_compute_trust_score() {
        let score = ProofOfSapience::compute_trust_score(0.8, 0.75, 0.9);
        assert!((score - 0.54).abs() < 0.01);
    }

    #[test]
    fn test_decay_accuracy_at_half_life() {
        let accuracy = 0.8;
        let half_life = 30.0;
        let decayed = ProofOfSapience::decay_accuracy(accuracy, half_life, half_life);
        assert!((decayed - 0.4).abs() < 0.01);
    }

    #[test]
    fn test_cap_score_below_cap() {
        let capped = ProofOfSapience::cap_score(0.5);
        assert_eq!(capped, 0.5);
    }

    #[test]
    fn test_cap_score_above_cap() {
        let capped = ProofOfSapience::cap_score(1.0);
        assert_eq!(capped, 0.95);
    }
}
