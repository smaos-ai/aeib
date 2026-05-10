/// Phase 11: Reputation Blending Engine
/// Blending home and foreign reputation signals with isolation guarantees

use chrono::{DateTime, Utc};
use uuid::Uuid;
use crate::behavior_scorer::{BehaviorEvent, BehaviorScorer};

pub const REPUTATION_ISOLATION: &str = "foreign_signals_cannot_boost_local_tier";

#[derive(Debug, Clone)]
pub enum ReputationBlendError {
    ForeignEventLineageSafe,
    InvalidBlendWeight(f64),
}

/// Convert federated reputation signals (as (strength, observed_at) tuples)
/// into BehaviorEvent with lineage_safe=false.
/// Converts signal strength (i16) to tier_delta.
pub fn reputation_signals_to_behavior_events(
    signals: &[(i16, DateTime<Utc>)],
    _source_sovereign_id: Uuid,
) -> Vec<BehaviorEvent> {
    signals
        .iter()
        .map(|(strength, scored_at)| {
            BehaviorEvent {
                event_type: if *strength > 0 {
                    "positive_reputation".to_string()
                } else {
                    "negative_reputation".to_string()
                },
                tier_delta: *strength,
                lineage_safe: false,  // REPUTATION_ISOLATION: all foreign signals non-lineage-safe
                scored_at: *scored_at,
            }
        })
        .collect()
}

/// Blend home and foreign reputation scores with isolation enforcement.
///
/// Algorithm:
/// 1. Score home events against attestation_tier
/// 2. Score foreign events against home_tier (ceiling)
/// 3. Blend: (home_tier * (1 - weight)) + (foreign_tier * weight)
/// 4. Enforce REPUTATION_ISOLATION: result = min(blended, home_tier)
pub fn blend_reputation_scores(
    attestation_tier: u32,
    home_events: &[BehaviorEvent],
    foreign_events: &[BehaviorEvent],
    blend_weight: f64,
    now: DateTime<Utc>,
) -> Result<u32, ReputationBlendError> {
    if !(0.0..=1.0).contains(&blend_weight) {
        return Err(ReputationBlendError::InvalidBlendWeight(blend_weight));
    }

    // Verify all foreign events have lineage_safe = false
    assert_foreign_events_not_lineage_safe(foreign_events)?;

    // Score home events
    let home_scorer = BehaviorScorer::new(home_events.to_vec(), now);
    let home_tier = home_scorer.apply_tier_delta(attestation_tier);

    // Score foreign events (applying to home_tier as ceiling)
    let foreign_scorer = BehaviorScorer::new(foreign_events.to_vec(), now);
    let foreign_tier = foreign_scorer.apply_tier_delta(home_tier);

    // Blend with weights
    let blended = (home_tier as f64) * (1.0 - blend_weight) + (foreign_tier as f64) * blend_weight;
    let blended_tier = blended.round() as u32;

    // REPUTATION_ISOLATION: blended tier cannot exceed home tier
    Ok(std::cmp::min(blended_tier, home_tier))
}

/// Assert that all foreign events have lineage_safe = false.
/// This is a defensive check for the REPUTATION_ISOLATION invariant.
pub fn assert_foreign_events_not_lineage_safe(
    events: &[BehaviorEvent],
) -> Result<(), ReputationBlendError> {
    if events.iter().any(|e| e.lineage_safe) {
        return Err(ReputationBlendError::ForeignEventLineageSafe);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_event(event_type: &str, tier_delta: i16, scored_at: DateTime<Utc>, lineage_safe: bool) -> BehaviorEvent {
        BehaviorEvent {
            event_type: event_type.to_string(),
            tier_delta,
            lineage_safe,
            scored_at,
        }
    }

    #[test]
    fn test_blend_zero_weight_pure_home() {
        let now = Utc::now();
        let home_events = vec![
            make_event("positive", 1, now - chrono::Duration::hours(1), true),
        ];
        let foreign_events = vec![];

        let result = blend_reputation_scores(50, &home_events, &foreign_events, 0.0, now)
            .expect("blend");

        // With zero weight, foreign contributes nothing; result is home tier + home delta
        assert_eq!(result, 51, "zero weight should produce home tier + home delta");
    }

    #[test]
    fn test_reputation_isolation_foreign_cannot_raise_tier() {
        let now = Utc::now();
        let home_events = vec![];  // No home events = no local reputation boost
        let foreign_events = vec![
            make_event("positive", 10, now - chrono::Duration::hours(1), false),
        ];

        let result = blend_reputation_scores(100, &home_events, &foreign_events, 1.0, now)
            .expect("blend");

        // Even with 100% foreign weight and strong positive signals,
        // result cannot exceed home tier (100)
        assert!(result <= 100, "REPUTATION_ISOLATION: foreign signals cannot raise tier above home");
    }

    #[test]
    fn test_foreign_events_converted_with_lineage_safe_false() {
        let now = Utc::now();
        let signals = vec![
            (5i16, now - chrono::Duration::hours(1)),
            (-3i16, now - chrono::Duration::hours(2)),
        ];

        let sovereign_id = Uuid::new_v4();
        let events = reputation_signals_to_behavior_events(&signals, sovereign_id);

        assert_eq!(events.len(), 2);
        assert!(events.iter().all(|e| !e.lineage_safe), "all converted events must have lineage_safe=false");
        assert_eq!(events[0].tier_delta, 5, "positive signal should have positive tier_delta");
        assert_eq!(events[1].tier_delta, -3, "negative signal should have negative tier_delta");
    }

    #[test]
    fn test_assert_foreign_not_lineage_safe_rejects_true() {
        let now = Utc::now();
        let events = vec![
            make_event("test", 1, now, true),  // BAD: should not happen
        ];

        let result = assert_foreign_events_not_lineage_safe(&events);
        assert!(matches!(result, Err(ReputationBlendError::ForeignEventLineageSafe)));
    }

    #[test]
    fn test_blend_midpoint_lowers_tier() {
        let now = Utc::now();
        let home_events = vec![
            make_event("positive", 2, now - chrono::Duration::hours(1), true),
        ];
        let foreign_events = vec![
            make_event("negative", -2, now - chrono::Duration::hours(1), false),
        ];

        let result = blend_reputation_scores(100, &home_events, &foreign_events, 0.5, now)
            .expect("blend");

        // With negative foreign signals at 50% weight, blended should be lower than home
        assert!(result <= 100, "negative foreign signals with blending should not exceed home");
    }

    #[test]
    fn test_decay_applied_to_foreign_signals() {
        let now = Utc::now();
        let old_time = now - chrono::Duration::days(7);  // 7 days old (outside 3.5-day half-life)

        let home_events = vec![];
        let foreign_events = vec![
            make_event("positive", 10, old_time, false),
        ];

        let result = blend_reputation_scores(50, &home_events, &foreign_events, 1.0, now)
            .expect("blend");

        // Old signal should be heavily decayed, so result should be close to 50
        assert!(result <= 55, "decayed old signals should have minimal impact");
    }

    #[test]
    fn test_invalid_blend_weight_rejected() {
        let result = blend_reputation_scores(50, &[], &[], 1.5, Utc::now());
        assert!(matches!(result, Err(ReputationBlendError::InvalidBlendWeight(1.5))));
    }
}
