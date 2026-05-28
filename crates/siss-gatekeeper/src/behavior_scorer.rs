/// Phase 8: Behavior Scoring
///
/// Deterministic behavior window scoring with exponential decay.
/// Scores are pure: same events + same now = same output every time.
/// No Utc::now() calls inside this module (anchor is passed at construction).
use chrono::{DateTime, Utc};

pub const DECAY_HALF_LIFE_DAYS: f64 = 3.5;
pub const WINDOW_DAYS: i32 = 7;
pub const TIER_MIN: u32 = 1;
pub const TIER_MAX: u32 = 13;
pub const MAX_TIER_DELTA: i32 = 10;
pub const MIN_TIER_DELTA: i32 = -10;

/// A single behavior event in the scoring window.
#[derive(Debug, Clone)]
pub struct BehaviorEvent {
    pub event_type: String,
    pub tier_delta: i16, // Raw delta when event was scored
    pub scored_at: DateTime<Utc>,
    pub lineage_safe: bool,
}

/// Pure, stateless behavior scorer.
/// Computes tier adjustments from a snapshot of behavior events.
#[derive(Debug, Clone)]
pub struct BehaviorScorer {
    pub events: Vec<BehaviorEvent>,
    pub now: DateTime<Utc>, // Fixed anchor for age calculation (no Utc::now() inside methods)
}

impl BehaviorScorer {
    /// Create a new scorer with a fixed time anchor.
    pub fn new(events: Vec<BehaviorEvent>, now: DateTime<Utc>) -> Self {
        Self { events, now }
    }

    /// Exponential decay weight for an event given its age in days.
    /// Formula: e^(-age_days / half_life * ln(2))
    /// At age = half_life, weight = 0.5
    /// At age = 2*half_life, weight ≈ 0.25
    fn decay_weight(age_days: f64) -> f64 {
        (-age_days / DECAY_HALF_LIFE_DAYS * std::f64::consts::LN_2).exp()
    }

    /// Compute the tier adjustment from the behavior window.
    /// 1. Filter lineage_safe=true events only
    /// 2. Sum: tier_delta * decay_weight(age) for each event
    /// 3. Clamp result to [MIN_TIER_DELTA, MAX_TIER_DELTA]
    pub fn compute_tier_delta(&self) -> i32 {
        let mut sum: f64 = 0.0;

        for event in &self.events {
            // Skip lineage-unsafe events
            if !event.lineage_safe {
                continue;
            }

            // Calculate age in days
            let age_duration = self.now.signed_duration_since(event.scored_at);
            let age_days = age_duration.num_seconds() as f64 / 86400.0;

            // Apply exponential decay
            let weight = Self::decay_weight(age_days);
            sum += event.tier_delta as f64 * weight;
        }

        // Clamp to [MIN_TIER_DELTA, MAX_TIER_DELTA]
        let delta = (sum.round() as i32).max(MIN_TIER_DELTA).min(MAX_TIER_DELTA);

        delta
    }

    /// Apply tier delta to a tier, clamping result to [TIER_MIN, TIER_MAX].
    pub fn apply_tier_delta(&self, tier_before: u32) -> u32 {
        let delta = self.compute_tier_delta();
        let tier_after_i32 = (tier_before as i32 + delta)
            .max(TIER_MIN as i32)
            .min(TIER_MAX as i32);
        tier_after_i32 as u32
    }

    /// Apply tier delta with optional Trust Mesh boost (Layer 13 integration).
    /// Adds trust_mesh_boost to the computed delta, clamped to [0, 5].
    pub fn apply_tier_delta_with_trust(&self, tier_before: u32, trust_mesh_boost: Option<i16>) -> u32 {
        let delta = self.compute_tier_delta();
        let boost = trust_mesh_boost.unwrap_or(0).max(0).min(5) as i32;
        let total_delta = delta + boost;
        let tier_after_i32 = (tier_before as i32 + total_delta)
            .max(TIER_MIN as i32)
            .min(TIER_MAX as i32);
        tier_after_i32 as u32
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_event(
        event_type: &str,
        tier_delta: i16,
        days_ago: f64,
        lineage_safe: bool,
    ) -> BehaviorEvent {
        let now = Utc::now();
        let ago_secs = (days_ago * 86400.0) as i64;
        let scored_at = now - chrono::Duration::seconds(ago_secs);

        BehaviorEvent {
            event_type: event_type.to_string(),
            tier_delta,
            scored_at,
            lineage_safe,
        }
    }

    #[test]
    fn test_empty_window_zero_delta() {
        let scorer = BehaviorScorer::new(vec![], Utc::now());
        assert_eq!(scorer.compute_tier_delta(), 0);
    }

    #[test]
    fn test_single_success_positive_delta() {
        let now = Utc::now();
        let events = vec![make_event("refresh_success", 2, 0.0, true)];
        let scorer = BehaviorScorer::new(events, now);
        let delta = scorer.compute_tier_delta();
        assert_eq!(delta, 2);
    }

    #[test]
    fn test_single_failure_negative_delta() {
        let now = Utc::now();
        let events = vec![make_event("refresh_failure", -1, 0.0, true)];
        let scorer = BehaviorScorer::new(events, now);
        let delta = scorer.compute_tier_delta();
        assert_eq!(delta, -1);
    }

    #[test]
    fn test_decay_reduces_old_event_weight() {
        let now = Utc::now();

        // Recent success
        let recent = BehaviorScorer::new(vec![make_event("refresh_success", 10, 0.0, true)], now);
        let recent_delta = recent.compute_tier_delta();

        // Old success (6 days ago, decayed to ~3% of original)
        let old = BehaviorScorer::new(vec![make_event("refresh_success", 10, 6.0, true)], now);
        let old_delta = old.compute_tier_delta();

        // Old event should be much weaker
        assert!(
            old_delta < recent_delta,
            "Old event should have less weight"
        );
    }

    #[test]
    fn test_scoring_determinism() {
        let now = Utc::now();
        let events = vec![
            make_event("refresh_success", 2, 0.0, true),
            make_event("refresh_failure", -1, 2.0, true),
            make_event("delegation_created", 0, 3.5, true),
        ];

        let scorer1 = BehaviorScorer::new(events.clone(), now);
        let delta1 = scorer1.compute_tier_delta();

        let scorer2 = BehaviorScorer::new(events, now);
        let delta2 = scorer2.compute_tier_delta();

        assert_eq!(delta1, delta2, "Same inputs should produce same output");
    }

    #[test]
    fn test_lineage_unsafe_events_excluded() {
        let now = Utc::now();
        let events = vec![
            make_event("refresh_success", 5, 0.0, true),
            make_event("refresh_failure", -10, 0.0, false), // unsafe: should be ignored
        ];

        let scorer = BehaviorScorer::new(events, now);
        let delta = scorer.compute_tier_delta();

        // Should only count the +5 from refresh_success
        assert_eq!(delta, 5, "Unsafe events should be excluded");
    }

    #[test]
    fn test_clamped_at_max_plus_10() {
        let now = Utc::now();
        let events = vec![
            make_event("refresh_success", 5, 0.0, true),
            make_event("refresh_success", 5, 0.5, true),
            make_event("refresh_success", 5, 1.0, true),
            make_event("refresh_success", 5, 1.5, true),
        ];

        let scorer = BehaviorScorer::new(events, now);
        let delta = scorer.compute_tier_delta();

        assert_eq!(delta, MAX_TIER_DELTA, "Delta should clamp at +10");
    }

    #[test]
    fn test_clamped_at_min_minus_10() {
        let now = Utc::now();
        let events = vec![
            make_event("refresh_failure", -5, 0.0, true),
            make_event("refresh_failure", -5, 0.5, true),
            make_event("refresh_failure", -5, 1.0, true),
            make_event("refresh_failure", -5, 1.5, true),
        ];

        let scorer = BehaviorScorer::new(events, now);
        let delta = scorer.compute_tier_delta();

        assert_eq!(delta, MIN_TIER_DELTA, "Delta should clamp at -10");
    }

    #[test]
    fn test_apply_delta_clamps_tier_min_1() {
        let now = Utc::now();
        let events = vec![make_event("revocation_by_parent", -20, 0.0, true)];

        let scorer = BehaviorScorer::new(events, now);
        let tier_after = scorer.apply_tier_delta(3);

        // 3 + (-20) would be -17, clamped to TIER_MIN (1)
        assert_eq!(tier_after, TIER_MIN, "Tier should never go below 1");
    }

    #[test]
    fn test_apply_delta_clamps_tier_max_13() {
        let now = Utc::now();
        let events = vec![make_event("refresh_success", 20, 0.0, true)];

        let scorer = BehaviorScorer::new(events, now);
        let tier_after = scorer.apply_tier_delta(10);

        // 10 + 20 would be 30, clamped to TIER_MAX (13)
        assert_eq!(tier_after, TIER_MAX, "Tier should never go above 13");
    }

    // Task 41: Poison Pill Defense — Verify lineage_safe immutability
    //
    // These tests enforce the mathematical guarantee that cross-sovereign operations
    // cannot poison the behavior score of local agents through reputation manipulation.

    #[test]
    fn test_lineage_unsafe_contributes_zero_to_delta() {
        let now = Utc::now();

        // Scenario: Foreign agent injects +10 unsafe event; local agent has -3 safe event
        let events = vec![
            make_event("cross_sovereign_attempt", 10, 0.0, false), // foreign, unsafe
            make_event("refresh_success", -3, 0.0, true),          // local, safe
        ];

        let scorer = BehaviorScorer::new(events, now);
        let delta = scorer.compute_tier_delta();

        // Should only count the -3, completely ignoring the +10 from foreign source
        assert_eq!(delta, -3, "Unsafe events must contribute exactly zero");
    }

    #[test]
    fn test_all_unsafe_events_produce_zero_delta() {
        let now = Utc::now();

        // Extreme case: Only unsafe cross-sovereign events
        let events = vec![
            make_event("delegation_hijack_attempt", 8, 0.0, false),
            make_event("tier_boost_fraud", 7, 0.5, false),
            make_event("budget_overflow_attack", 6, 1.0, false),
        ];

        let scorer = BehaviorScorer::new(events, now);
        let delta = scorer.compute_tier_delta();

        // Pure poison attempt should have zero effect
        assert_eq!(
            delta, 0,
            "All unsafe events must produce zero delta (poison pill)"
        );
    }

    #[test]
    fn test_mixed_safe_unsafe_only_safe_counted() {
        let now = Utc::now();

        // Mix of safe and unsafe: only safe should be scored
        let events = vec![
            make_event("refresh_success", 2, 0.0, true), // safe: counted
            make_event("malicious_boost", 10, 0.0, false), // unsafe: ignored
            make_event("refresh_success", 3, 1.0, true), // safe: counted (decayed)
            make_event("cross_sovereign_inject", 9, 1.5, false), // unsafe: ignored
        ];

        let scorer = BehaviorScorer::new(events, now);
        let delta = scorer.compute_tier_delta();

        // Should only count: 2 + 3*decay(1 day)
        // 3.5-day half-life: decay(1) ≈ 0.822
        // Expected: 2 + 2.466 ≈ 4 (after rounding and decay)
        assert!(
            delta >= 4 && delta <= 5,
            "Should count only safe events; got {}",
            delta
        );
    }

    #[test]
    fn test_lineage_safe_flag_immutable_semantics() {
        let now = Utc::now();

        // Verify that once lineage_safe is set, it never changes behavior contribution
        // Same event with different lineage_safe values should have opposite effects

        let safe_events = vec![make_event("refresh_success", 5, 0.0, true)];
        let unsafe_events = vec![make_event("refresh_success", 5, 0.0, false)];

        let safe_scorer = BehaviorScorer::new(safe_events, now);
        let unsafe_scorer = BehaviorScorer::new(unsafe_events, now);

        let safe_delta = safe_scorer.compute_tier_delta();
        let unsafe_delta = unsafe_scorer.compute_tier_delta();

        // Same event: safe → +5, unsafe → 0 (immutable separation)
        assert_eq!(safe_delta, 5);
        assert_eq!(unsafe_delta, 0);
        assert_ne!(
            safe_delta, unsafe_delta,
            "lineage_safe must immutably determine inclusion"
        );
    }

    #[test]
    fn test_cross_sovereign_cannot_degrade_local_tier() {
        let now = Utc::now();

        // Poison pill test: Foreign agent tries to degrade local agent's tier
        // Even with extreme unsafe events, local tier changes only by local safe events
        let events = vec![
            make_event("cross_sovereign_tier_attack", -10, 0.0, false), // foreign attack: -10
            make_event("local_refresh", 2, 0.0, true),                  // local success: +2
        ];

        let scorer = BehaviorScorer::new(events, now);
        let initial_tier = 5u32;
        let final_tier = scorer.apply_tier_delta(initial_tier);

        // Should apply only +2, resulting in tier 7 (not degraded by -10)
        assert_eq!(
            final_tier, 7,
            "Cross-sovereign unsafe events cannot degrade tier"
        );
    }
}
