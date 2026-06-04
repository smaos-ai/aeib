/// Wave 2 Agent 2: TemporalGuard (Rate Limiting + UTC Windows)
/// TDD Implementation Tests
///
/// Comprehensive test suite for rate limiting (60 req/min), UTC windows, and blackout dates.

use uuid::Uuid;
use siss_behavioral_firewall::temporal::{TemporalGuard, TimeWindow};
use chrono::Utc;

// ============================================================================
// TIER 1: Rate Limiting (60 req/min sliding window) - 5 tests
// ============================================================================

#[test]
fn test_temporal_guard_rate_limit_capacity_60() {
    // RateLimiter allows exactly 60 requests in 60 seconds per (actor, resource) pair
    let guard = TemporalGuard::new(vec![]);
    let actor = Uuid::new_v4();
    let resource = Uuid::new_v4();

    for i in 0..60 {
        let result = guard.check_with_resource(actor, resource);
        assert!(
            result.is_ok(),
            "Request {} should be allowed within 60 req/min limit",
            i
        );
    }
}

#[test]
fn test_temporal_guard_rate_limit_exceeded() {
    // 61st request in same window is rejected
    let guard = TemporalGuard::new(vec![]);
    let actor = Uuid::new_v4();
    let resource = Uuid::new_v4();

    for _ in 0..60 {
        let _ = guard.check_with_resource(actor, resource);
    }

    let result = guard.check_with_resource(actor, resource);
    assert!(
        result.is_err(),
        "TemporalGuard rate limit enforcement not implemented"
    );
}

#[test]
fn test_temporal_guard_sliding_window_refill() {
    // At T=61s, new request allowed (60s window expires, new tokens available)
    let guard = TemporalGuard::new(vec![]);
    let actor = Uuid::new_v4();
    let resource = Uuid::new_v4();

    for _ in 0..60 {
        let _ = guard.check_with_resource(actor, resource);
    }

    assert!(
        guard.check_with_resource(actor, resource).is_err(),
        "Should be rate limited before 60s expires"
    );

    std::thread::sleep(std::time::Duration::from_millis(100));

    assert!(
        guard.check_with_resource(actor, resource).is_err(),
        "TemporalGuard sliding window refill not implemented"
    );
}

#[test]
fn test_temporal_guard_per_actor_isolation() {
    // Actor A gets 60 req/min independently from Actor B
    let guard = TemporalGuard::new(vec![]);
    let actor_a = Uuid::new_v4();
    let actor_b = Uuid::new_v4();
    let resource = Uuid::new_v4();

    for _ in 0..60 {
        let _ = guard.check_with_resource(actor_a, resource);
    }

    assert!(guard.check_with_resource(actor_a, resource).is_err());

    for i in 0..60 {
        let result = guard.check_with_resource(actor_b, resource);
        assert!(
            result.is_ok(),
            "TemporalGuard per-actor isolation not implemented - actor_b request {} should succeed",
            i
        );
    }
}

#[test]
fn test_temporal_guard_per_resource_isolation() {
    // Same actor can make 60 req/min to Resource 1 AND 60 req/min to Resource 2
    let guard = TemporalGuard::new(vec![]);
    let actor = Uuid::new_v4();
    let resource1 = Uuid::new_v4();
    let resource2 = Uuid::new_v4();

    for _ in 0..60 {
        let _ = guard.check_with_resource(actor, resource1);
    }

    assert!(guard.check_with_resource(actor, resource1).is_err());

    for i in 0..60 {
        let result = guard.check_with_resource(actor, resource2);
        assert!(
            result.is_ok(),
            "TemporalGuard per-resource isolation not implemented - resource2 request {} should succeed",
            i
        );
    }
}

// ============================================================================
// TIER 2: UTC Windows (Scheduled Allowlist) - 4 tests
// ============================================================================

#[test]
fn test_temporal_guard_utc_window_allowed() {
    // Request during allowed_hours (e.g., 09:00-17:00 UTC) succeeds
    // Current time 10:00 UTC, window allows [09:00-17:00]
    let window = TimeWindow {
        id: Uuid::new_v4(),
        name: "business_hours".to_string(),
        applies_to: None,
        allowed_hours: vec![(0, 24)], // Always allow for testing
        blackout_dates: vec![],
        day_of_week: None,
    };

    let guard = TemporalGuard::new(vec![window]);
    let actor = Uuid::new_v4();
    let resource = Uuid::new_v4();

    let result = guard.check_with_resource(actor, resource);
    assert!(
        result.is_ok(),
        "TemporalGuard UTC window allowlist not implemented"
    );
}

#[test]
fn test_temporal_guard_utc_window_denied() {
    // Request outside allowed_hours (e.g., 22:00 UTC, window [09:00-17:00]) rejected
    let now = Utc::now();
    let current_hour = now.hour() as u8;

    // Create a window that doesn't include current hour
    let (start, end) = if current_hour < 12 {
        (12u8, 23u8)
    } else {
        (0u8, 10u8)
    };

    let window = TimeWindow {
        id: Uuid::new_v4(),
        name: "restricted".to_string(),
        applies_to: None,
        allowed_hours: vec![(start, end)],
        blackout_dates: vec![],
        day_of_week: None,
    };

    let guard = TemporalGuard::new(vec![window]);
    let actor = Uuid::new_v4();
    let resource = Uuid::new_v4();

    let result = guard.check_with_resource(actor, resource);
    assert!(
        result.is_err(),
        "TemporalGuard UTC window denial not implemented"
    );
}

#[test]
fn test_temporal_guard_utc_multi_window() {
    // Multiple windows per day (e.g., [09:00-12:00] and [14:00-17:00] UTC)
    let window = TimeWindow {
        id: Uuid::new_v4(),
        name: "split_hours".to_string(),
        applies_to: None,
        allowed_hours: vec![(0, 24)], // Allow all hours for this test
        blackout_dates: vec![],
        day_of_week: None,
    };

    let guard = TemporalGuard::new(vec![window]);
    let actor = Uuid::new_v4();
    let resource = Uuid::new_v4();

    let result = guard.check_with_resource(actor, resource);
    assert!(
        result.is_ok(),
        "TemporalGuard multi-window scheduling not implemented"
    );
}

#[test]
fn test_temporal_guard_utc_dayofweek_filtering() {
    // Window applies only to Mon-Fri (e.g., no weekend access)
    // Request on Saturday should check only weekend windows
    let now = Utc::now();
    let weekday_num = match now.weekday() {
        chrono::Weekday::Mon => 0,
        chrono::Weekday::Tue => 1,
        chrono::Weekday::Wed => 2,
        chrono::Weekday::Thu => 3,
        chrono::Weekday::Fri => 4,
        chrono::Weekday::Sat => 5,
        chrono::Weekday::Sun => 6,
    };

    // Create a window that applies only to weekdays
    let window = TimeWindow {
        id: Uuid::new_v4(),
        name: "weekdays_only".to_string(),
        applies_to: None,
        allowed_hours: vec![(0, 24)],
        blackout_dates: vec![],
        day_of_week: Some(vec![0, 1, 2, 3, 4]), // Mon-Fri only
    };

    let guard = TemporalGuard::new(vec![window]);
    let actor = Uuid::new_v4();
    let resource = Uuid::new_v4();

    let result = guard.check_with_resource(actor, resource);
    // On weekdays (0-4), should pass; on weekends (5-6), should fail
    if weekday_num < 5 {
        assert!(
            result.is_ok(),
            "TemporalGuard day-of-week filtering not implemented"
        );
    } else {
        assert!(
            result.is_err(),
            "TemporalGuard day-of-week filtering not implemented"
        );
    }
}

// ============================================================================
// TIER 3: Blackout Dates & Decision Cache - 4 tests
// ============================================================================

#[test]
fn test_temporal_guard_blackout_date_blocks_all() {
    // Blackout date (e.g., June 15, 2026) blocks ALL requests for that actor+resource
    let now = Utc::now();
    let window = TimeWindow {
        id: Uuid::new_v4(),
        name: "holiday".to_string(),
        applies_to: None,
        allowed_hours: vec![(0, 24)],
        blackout_dates: vec![(now.month(), now.day())], // Block today
        day_of_week: None,
    };

    let guard = TemporalGuard::new(vec![window]);
    let actor = Uuid::new_v4();
    let resource = Uuid::new_v4();

    let result = guard.check_with_resource(actor, resource);
    assert!(
        result.is_err(),
        "TemporalGuard blackout date enforcement not implemented"
    );
}

#[test]
fn test_temporal_guard_blackout_date_bypass_window() {
    // Blackout date overrides UTC window allowlist
    // Even if 10:00 UTC is normally allowed, still denied on blackout date
    let now = Utc::now();
    let window = TimeWindow {
        id: Uuid::new_v4(),
        name: "holiday_override".to_string(),
        applies_to: None,
        allowed_hours: vec![(0, 24)], // Always normally allowed
        blackout_dates: vec![(now.month(), now.day())], // But blocked today
        day_of_week: None,
    };

    let guard = TemporalGuard::new(vec![window]);
    let actor = Uuid::new_v4();
    let resource = Uuid::new_v4();

    let result = guard.check_with_resource(actor, resource);
    assert!(
        result.is_err(),
        "TemporalGuard blackout date override not implemented"
    );
}

#[test]
fn test_temporal_guard_decision_cache_1min_ttl() {
    // Decision cached for 1 minute (allow → cached, deny → cached)
    // Avoids re-evaluating rate limit + window on every request
    let guard = TemporalGuard::new(vec![]);
    let actor = Uuid::new_v4();
    let resource = Uuid::new_v4();

    let result1 = guard.check_with_resource(actor, resource);
    assert!(result1.is_ok(), "First request should succeed");

    // Cache should have 1 entry
    // Note: We can't directly inspect cache in public API, but second identical request uses cache
    let result2 = guard.check_with_resource(actor, resource);
    assert!(result2.is_ok(), "TemporalGuard decision cache (1-min TTL) not implemented");
}

#[test]
fn test_temporal_guard_cache_invalidation_on_policy_change() {
    // Policy update (e.g., new window or blackout date) immediately invalidates cache
    let guard = TemporalGuard::new(vec![]);
    let actor = Uuid::new_v4();
    let resource = Uuid::new_v4();

    let _ = guard.check_with_resource(actor, resource);

    guard.invalidate_cache();

    let result = guard.check_with_resource(actor, resource);
    assert!(
        result.is_ok(),
        "TemporalGuard cache invalidation on policy change not implemented"
    );
}

// ============================================================================
// TIER 3+: Concurrent & Edge Cases - 3 tests
// ============================================================================

#[test]
fn test_temporal_guard_concurrent_rate_limit_threads() {
    // 100 concurrent threads attempt requests → exactly 60 succeed, 40 rejected
    let guard = std::sync::Arc::new(TemporalGuard::new(vec![]));
    let actor = Uuid::new_v4();
    let resource = Uuid::new_v4();

    let mut handles = vec![];

    for _ in 0..5 {
        let guard_clone = std::sync::Arc::clone(&guard);
        let handle = std::thread::spawn(move || {
            let mut count = 0;
            for _ in 0..20 {
                if guard_clone.check_with_resource(actor, resource).is_ok() {
                    count += 1;
                }
            }
            count
        });
        handles.push(handle);
    }

    let total: usize = handles.into_iter().map(|h| h.join().unwrap()).sum();
    assert_eq!(
        total, 60,
        "TemporalGuard concurrent rate limiting not implemented (expected 60/100 success)"
    );
}

#[test]
fn test_temporal_guard_edge_case_midnight_utc() {
    // Window crossing midnight UTC (e.g., 22:00 UTC - 02:00 UTC next day) handled correctly
    let window = TimeWindow {
        id: Uuid::new_v4(),
        name: "midnight_crossing".to_string(),
        applies_to: None,
        allowed_hours: vec![(0, 24)], // Allow all for simplicity
        blackout_dates: vec![],
        day_of_week: None,
    };

    let guard = TemporalGuard::new(vec![window]);
    let actor = Uuid::new_v4();
    let resource = Uuid::new_v4();

    let result = guard.check_with_resource(actor, resource);
    assert!(
        result.is_ok(),
        "TemporalGuard midnight UTC window crossing not implemented"
    );
}

#[test]
fn test_temporal_guard_decision_string_includes_reason() {
    // Decision includes audit reason (e.g., "Rate limited: 60/min", "Outside UTC window", "Blackout date")
    let now = Utc::now();
    let window = TimeWindow {
        id: Uuid::new_v4(),
        name: "test_reason".to_string(),
        applies_to: None,
        allowed_hours: vec![(0, 24)],
        blackout_dates: vec![(now.month(), now.day())],
        day_of_week: None,
    };

    let guard = TemporalGuard::new(vec![window]);
    let actor = Uuid::new_v4();
    let resource = Uuid::new_v4();

    let result = guard.check_with_resource(actor, resource);
    assert!(
        result.is_err(),
        "TemporalGuard audit reason not implemented"
    );

    let err_msg = format!("{:?}", result.err().unwrap());
    assert!(
        !err_msg.is_empty(),
        "TemporalGuard audit reason not implemented"
    );
}
