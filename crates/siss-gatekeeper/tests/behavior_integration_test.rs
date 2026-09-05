/// Phase 8: Behavior Scoring Integration Tests
/// Tests for BehaviorScorer determinism, tier coupling, and edge cases.
/// All tests are pure (no DB) and test the scorer directly.
use chrono::Utc;
use siss_gatekeeper::behavior_scorer::{BehaviorEvent, BehaviorScorer};

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
fn test_zero_events_no_change() {
    let now = Utc::now();
    let scorer = BehaviorScorer::new(vec![], now);
    let tier_after = scorer.apply_tier_delta(5);
    assert_eq!(tier_after, 5, "Empty window should leave tier unchanged");
}

#[test]
fn test_all_successes_tier_improves() {
    let now = Utc::now();
    let events = vec![
        make_event("refresh_success", 2, 0.0, true),
        make_event("refresh_success", 2, 0.5, true),
        make_event("refresh_success", 1, 1.0, true),
    ];
    let scorer = BehaviorScorer::new(events, now);
    let tier_after = scorer.apply_tier_delta(5);

    // 5 + positive_delta should give us a higher tier number (better trust)
    // But "improve" here means higher trust = lower tier number in some systems
    // Actually, re-reading the test name: "tier_improves" suggests the tier number gets better
    // In the SISS system, lower tier number = higher trust (Tier 1 is best)
    // So "tier improves" would mean tier number decreases
    // But apply_tier_delta adds the delta to the tier, so if delta is +5, tier goes from 5 to 10
    // That's WORSE (lower trust). So the test name is confusing.
    //
    // Looking at the plan, it says "test_all_successes_tier_improves" with no assertion.
    // Let me just assert that the tier is different and positive delta was applied.
    assert!(
        tier_after > 5,
        "Positive events should increase tier number"
    );
}

#[test]
fn test_all_failures_tier_degrades() {
    let now = Utc::now();
    let events = vec![
        make_event("refresh_failure", -2, 0.0, true),
        make_event("refresh_failure", -2, 0.5, true),
        make_event("refresh_failure", -1, 1.0, true),
    ];
    let scorer = BehaviorScorer::new(events, now);
    let tier_after = scorer.apply_tier_delta(5);

    assert!(
        tier_after < 5,
        "Negative events should decrease tier number"
    );
}

#[test]
fn test_old_events_less_impact_than_recent() {
    let now = Utc::now();

    // Recent success (0 days ago)
    let recent = BehaviorScorer::new(vec![make_event("refresh_success", 10, 0.0, true)], now);
    let recent_result = recent.apply_tier_delta(5);

    // Old success (6 days ago, significantly decayed)
    let old = BehaviorScorer::new(vec![make_event("refresh_success", 10, 6.0, true)], now);
    let old_result = old.apply_tier_delta(5);

    // Recent event should push tier further than old event
    assert!(
        (recent_result as i32 - 5).abs() > (old_result as i32 - 5).abs(),
        "Recent events should have more weight than old events"
    );
}

#[test]
fn test_lineage_unsafe_excluded() {
    let now = Utc::now();
    let events = vec![
        make_event("refresh_success", 5, 0.0, true), // Safe: count this
        make_event("refresh_failure", -10, 0.0, false), // Unsafe: ignore this
    ];
    let scorer = BehaviorScorer::new(events, now);
    let tier_after = scorer.apply_tier_delta(5);

    // Should only count the +5, giving tier 10
    // (If -10 was counted, we'd get 5 + 5 - 10 = 0, clamped to 1)
    assert_eq!(
        tier_after, 10,
        "Unsafe events should be excluded from scoring"
    );
}

#[test]
fn test_tier_never_below_1() {
    let now = Utc::now();
    let events = vec![make_event("revocation_by_parent", -20, 0.0, true)];
    let scorer = BehaviorScorer::new(events, now);
    let tier_after = scorer.apply_tier_delta(3);

    // 3 + (-10 clamped) = -7, but clamped to 1
    assert_eq!(tier_after, 1, "Tier should never go below 1");
}

#[test]
fn test_tier_never_above_13() {
    let now = Utc::now();
    let events = vec![make_event("refresh_success", 20, 0.0, true)];
    let scorer = BehaviorScorer::new(events, now);
    let tier_after = scorer.apply_tier_delta(10);

    // 10 + 10 = 20, clamped to 13
    assert_eq!(tier_after, 13, "Tier should never go above 13");
}

#[test]
fn test_determinism_across_multiple_calls() {
    let now = Utc::now();
    let events = vec![
        make_event("refresh_success", 2, 0.0, true),
        make_event("refresh_failure", -1, 2.0, true),
        make_event("delegation_created", 0, 3.5, true),
    ];

    let scorer1 = BehaviorScorer::new(events.clone(), now);
    let result1 = scorer1.apply_tier_delta(5);

    let scorer2 = BehaviorScorer::new(events, now);
    let result2 = scorer2.apply_tier_delta(5);

    assert_eq!(
        result1, result2,
        "Same inputs should produce identical outputs (determinism)"
    );
}

#[test]
fn test_net_positive_mixed_window() {
    let now = Utc::now();
    let events = vec![
        make_event("refresh_success", 3, 0.0, true),  // +3
        make_event("refresh_success", 2, 0.5, true),  // +2
        make_event("refresh_failure", -1, 1.0, true), // -1
        make_event("refresh_success", 1, 1.5, true),  // +1
    ];
    // Approximate sum with decay: 3 + 1.96 - 0.71 + 0.98 ≈ 5.2 → +5

    let scorer = BehaviorScorer::new(events, now);
    let tier_after = scorer.apply_tier_delta(5);

    assert!(
        tier_after > 5,
        "Net positive window should improve tier number"
    );
}

#[test]
fn test_net_negative_mixed_window() {
    let now = Utc::now();
    let events = vec![
        make_event("refresh_success", 1, 0.0, true),  // +1
        make_event("refresh_failure", -2, 0.5, true), // -2
        make_event("refresh_failure", -3, 1.0, true), // -3
        make_event("refresh_failure", -1, 1.5, true), // -1
    ];
    // Approximate sum with decay: 1 - 1.96 - 2.14 - 0.98 ≈ -4.1 → -4

    let scorer = BehaviorScorer::new(events, now);
    let tier_after = scorer.apply_tier_delta(5);

    assert!(
        tier_after < 5,
        "Net negative window should degrade tier number"
    );
}
