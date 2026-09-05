use siss_behavioral_firewall::types::Verdict;

use super::{Scorer, ScoringContext};

/// Default scorer: average of verdict score and token efficiency.
pub struct HeuristicScorer;

impl Scorer for HeuristicScorer {
    fn score(&self, context: &ScoringContext) -> f64 {
        let verdict_score = match context.verdict {
            Verdict::Clear => 1.0,
            Verdict::Blocked => 0.5,
            Verdict::CriticalBlocked => 0.0,
        };

        let efficiency_score = if context.estimated_cost == 0 {
            1.0
        } else {
            let ratio = context.token_cost as f64 / context.estimated_cost as f64;
            (1.0 - ratio).clamp(0.0, 1.0)
        };

        (verdict_score + efficiency_score) / 2.0
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_clear_half_cost() {
        let scorer = HeuristicScorer;
        let ctx = ScoringContext {
            verdict: Verdict::Clear,
            token_cost: 50,
            estimated_cost: 100,
        };
        // verdict=1.0, efficiency=1.0-0.5=0.5, avg=0.75
        let score = scorer.score(&ctx);
        assert!((score - 0.75).abs() < f64::EPSILON);
    }

    #[test]
    fn test_clear_exact_cost() {
        let scorer = HeuristicScorer;
        let ctx = ScoringContext {
            verdict: Verdict::Clear,
            token_cost: 100,
            estimated_cost: 100,
        };
        // verdict=1.0, efficiency=0.0, avg=0.5
        let score = scorer.score(&ctx);
        assert!((score - 0.5).abs() < f64::EPSILON);
    }

    #[test]
    fn test_clear_zero_cost() {
        let scorer = HeuristicScorer;
        let ctx = ScoringContext {
            verdict: Verdict::Clear,
            token_cost: 0,
            estimated_cost: 100,
        };
        // verdict=1.0, efficiency=1.0, avg=1.0
        let score = scorer.score(&ctx);
        assert!((score - 1.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_blocked_verdict() {
        let scorer = HeuristicScorer;
        let ctx = ScoringContext {
            verdict: Verdict::Blocked,
            token_cost: 50,
            estimated_cost: 100,
        };
        // verdict=0.5, efficiency=0.5, avg=0.5
        let score = scorer.score(&ctx);
        assert!((score - 0.5).abs() < f64::EPSILON);
    }

    #[test]
    fn test_critical_blocked() {
        let scorer = HeuristicScorer;
        let ctx = ScoringContext {
            verdict: Verdict::CriticalBlocked,
            token_cost: 100,
            estimated_cost: 100,
        };
        // verdict=0.0, efficiency=0.0, avg=0.0
        let score = scorer.score(&ctx);
        assert!((score - 0.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_zero_estimated_cost() {
        let scorer = HeuristicScorer;
        let ctx = ScoringContext {
            verdict: Verdict::Clear,
            token_cost: 50,
            estimated_cost: 0,
        };
        // verdict=1.0, efficiency=1.0 (default), avg=1.0
        let score = scorer.score(&ctx);
        assert!((score - 1.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_over_budget_clamps_efficiency() {
        let scorer = HeuristicScorer;
        let ctx = ScoringContext {
            verdict: Verdict::Clear,
            token_cost: 200,
            estimated_cost: 100,
        };
        // verdict=1.0, efficiency=clamp(1.0-2.0, 0, 1)=0.0, avg=0.5
        let score = scorer.score(&ctx);
        assert!((score - 0.5).abs() < f64::EPSILON);
    }
}
