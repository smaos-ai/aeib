pub mod heuristic;

use siss_behavioral_firewall::types::Verdict;

/// Context for quality scoring.
pub struct ScoringContext {
    pub verdict: Verdict,
    pub token_cost: i64,
    pub estimated_cost: i64,
}

/// Trait for scoring execution quality.
pub trait Scorer: Send + Sync {
    fn score(&self, context: &ScoringContext) -> f64;
}
