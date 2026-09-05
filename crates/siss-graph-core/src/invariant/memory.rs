use crate::node::memory::{ConsolidationTier, compute_decay, is_gc_eligible};

/// Compute current confidence and determine if a memory node should be garbage collected.
pub fn should_gc(
    initial_confidence: f64,
    last_reinforced_at: chrono::DateTime<chrono::Utc>,
    tier: ConsolidationTier,
    threshold: f64,
) -> bool {
    let current = compute_decay(initial_confidence, last_reinforced_at, tier);
    is_gc_eligible(current, threshold)
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{Duration, Utc};

    #[test]
    fn test_recent_memory_not_gc() {
        let result = should_gc(0.9, Utc::now(), ConsolidationTier::Episodic, 0.1);
        assert!(!result);
    }

    #[test]
    fn test_very_old_episodic_is_gc() {
        // 30 days old episodic memory with stability=48h
        // e^(-720/48) = e^(-15) ~ 3e-7 — well below 0.1
        let ancient = Utc::now() - Duration::days(30);
        let result = should_gc(1.0, ancient, ConsolidationTier::Episodic, 0.1);
        assert!(result);
    }

    #[test]
    fn test_old_procedural_not_gc() {
        // 7 days old procedural memory with stability=720h
        // e^(-168/720) = e^(-0.233) ~ 0.792 — above 0.1
        let week_ago = Utc::now() - Duration::days(7);
        let result = should_gc(1.0, week_ago, ConsolidationTier::Procedural, 0.1);
        assert!(!result);
    }
}
