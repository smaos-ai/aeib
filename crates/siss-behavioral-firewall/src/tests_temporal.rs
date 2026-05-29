// Comprehensive TDD tests for TemporalGuard + RateLimiter
// Phase 25 Wave 2 Agent 2

use crate::temporal::{TemporalGuard, TimeWindow, PolicyAction, RateLimiter};
use std::sync::Arc;
use std::time::Duration;
use uuid::Uuid;
use chrono::{Utc, Datelike};

fn sovereign(id: u64) -> Uuid {
    Uuid::from_u64_pair(id, 0)
}

// ============================================================================
// RATE LIMITER TESTS (Token Bucket Algorithm)
// ============================================================================

#[test]
fn test_rate_limiter_single_token_allowed() {
    let limiter = RateLimiter::new(10, Duration::from_secs(1));
    assert!(limiter.try_consume().is_ok());
}

#[test]
fn test_rate_limiter_multiple_tokens_allowed() {
    let limiter = RateLimiter::new(5, Duration::from_secs(1));
    for i in 0..5 {
        assert!(limiter.try_consume().is_ok(), "Token {} should be allowed", i);
    }
}

#[test]
fn test_rate_limiter_exceeds_capacity() {
    let limiter = RateLimiter::new(3, Duration::from_secs(1));
    for _ in 0..3 {
        let _ = limiter.try_consume();
    }
    assert!(limiter.try_consume().is_err(), "4th token should be denied");
}

#[test]
fn test_rate_limiter_token_refill() {
    let limiter = RateLimiter::new(2, Duration::from_millis(100));
    for _ in 0..2 {
        let _ = limiter.try_consume();
    }
    assert!(limiter.try_consume().is_err(), "Should be empty");

    std::thread::sleep(Duration::from_millis(150));

    assert!(limiter.try_consume().is_ok(), "Token should be refilled after refill period");
}

#[test]
fn test_rate_limiter_concurrent_access() {
    let limiter = Arc::new(RateLimiter::new(20, Duration::from_secs(1)));
    let mut handles = vec![];

    for _ in 0..5 {
        let limiter_clone = Arc::clone(&limiter);
        let handle = std::thread::spawn(move || {
            let mut count = 0;
            for _ in 0..5 {
                if limiter_clone.try_consume().is_ok() {
                    count += 1;
                }
            }
            count
        });
        handles.push(handle);
    }

    let total: usize = handles.into_iter().map(|h| h.join().unwrap()).sum();
    assert_eq!(total, 20, "All 20 tokens should be consumed");
}

#[test]
fn test_rate_limiter_partial_refill() {
    let limiter = RateLimiter::new(10, Duration::from_millis(50));
    for _ in 0..7 {
        let _ = limiter.try_consume();
    }

    std::thread::sleep(Duration::from_millis(75));

    // Should have refilled with some tokens
    let mut consumed = 0;
    while limiter.try_consume().is_ok() {
        consumed += 1;
    }
    assert!(consumed > 0, "Should have refilled at least some tokens");
}

// ============================================================================
// TEMPORAL GUARD TESTS (Sliding Window + Time Windows)
// ============================================================================

#[test]
fn test_temporal_guard_rate_limit_60_allowed() {
    let guard = TemporalGuard::new(vec![]);
    let s1 = sovereign(1);

    for i in 0..60 {
        let result = guard.check_rate_limit(s1);
        assert!(result.is_ok(), "Request {} should be allowed", i);
    }
}

#[test]
fn test_temporal_guard_rate_limit_61st_denied() {
    let guard = TemporalGuard::new(vec![]);
    let s1 = sovereign(1);

    for _ in 0..60 {
        let _ = guard.check_rate_limit(s1);
    }

    let result = guard.check_rate_limit(s1);
    assert!(result.is_err(), "61st request should exceed limit");
}

#[test]
fn test_temporal_guard_sliding_window_boundary() {
    let guard = TemporalGuard::new(vec![]);
    let s1 = sovereign(1);

    for _ in 0..60 {
        let _ = guard.check_rate_limit(s1);
    }

    std::thread::sleep(Duration::from_millis(100));

    let result = guard.check_rate_limit(s1);
    assert!(result.is_err(), "Requests within 1-minute window should still be counted");
}

#[test]
fn test_temporal_guard_independent_rate_limits() {
    let guard = TemporalGuard::new(vec![]);
    let s1 = sovereign(1);
    let s2 = sovereign(2);

    for _ in 0..60 {
        let _ = guard.check_rate_limit(s1);
    }

    assert!(guard.check_rate_limit(s1).is_err());

    for _ in 0..60 {
        let result = guard.check_rate_limit(s2);
        assert!(result.is_ok(), "s2 should have independent rate limit");
    }
}

#[test]
fn test_temporal_guard_time_window_allowed_hours() {
    let window = TimeWindow {
        id: Uuid::new_v4(),
        name: "business_hours".to_string(),
        applies_to: PolicyAction::Spawn,
        allowed_hours: vec![(0, 24)], // Allow all hours for testing
        blackout_dates: vec![],
    };

    let guard = TemporalGuard::new(vec![window]);
    assert!(guard.check_time_window(PolicyAction::Spawn).is_ok());
}

#[test]
fn test_temporal_guard_time_window_blackout_dates() {
    let today = Utc::now();
    let window = TimeWindow {
        id: Uuid::new_v4(),
        name: "holiday".to_string(),
        applies_to: PolicyAction::CreatePolicy,
        allowed_hours: vec![(0, 24)],
        blackout_dates: vec![(today.month(), today.day())],
    };

    let guard = TemporalGuard::new(vec![window]);
    let result = guard.check_time_window(PolicyAction::CreatePolicy);
    assert!(result.is_err(), "Blackout date should block action");
}

#[test]
fn test_temporal_guard_no_applicable_time_window() {
    let window = TimeWindow {
        id: Uuid::new_v4(),
        name: "other_action".to_string(),
        applies_to: PolicyAction::Pause,
        allowed_hours: vec![(9, 17)],
        blackout_dates: vec![],
    };

    let guard = TemporalGuard::new(vec![window]);
    let result = guard.check_time_window(PolicyAction::Spawn);
    assert!(result.is_ok(), "No applicable window should allow action");
}

#[test]
fn test_temporal_guard_composite_check_both_pass() {
    let guard = TemporalGuard::new(vec![]);
    let s1 = sovereign(1);

    let result = guard.check(s1, PolicyAction::Spawn);
    assert!(result.is_ok());
}

#[test]
fn test_temporal_guard_composite_check_rate_limit_fail() {
    let guard = TemporalGuard::new(vec![]);
    let s1 = sovereign(1);

    for _ in 0..60 {
        let _ = guard.check_rate_limit(s1);
    }

    let result = guard.check(s1, PolicyAction::Spawn);
    assert!(result.is_err());
}

#[test]
fn test_temporal_guard_composite_check_time_window_fail() {
    let today = Utc::now();
    let window = TimeWindow {
        id: Uuid::new_v4(),
        name: "holiday".to_string(),
        applies_to: PolicyAction::Spawn,
        allowed_hours: vec![(0, 24)],
        blackout_dates: vec![(today.month(), today.day())],
    };

    let guard = TemporalGuard::new(vec![window]);
    let s1 = sovereign(1);

    let result = guard.check(s1, PolicyAction::Spawn);
    assert!(result.is_err(), "Blackout date should fail composite check");
}

#[test]
fn test_temporal_guard_utc_only_time() {
    let guard = TemporalGuard::new(vec![]);
    let _ = guard.check_time_window(PolicyAction::Spawn);
}

#[test]
fn test_temporal_guard_concurrent_rate_checks() {
    let guard = Arc::new(TemporalGuard::new(vec![]));
    let s1 = sovereign(1);

    let mut handles = vec![];

    for _ in 0..5 {
        let guard_clone = Arc::clone(&guard);
        let handle = std::thread::spawn(move || {
            for _ in 0..12 {
                let _ = guard_clone.check_rate_limit(s1);
            }
        });
        handles.push(handle);
    }

    for handle in handles {
        let _ = handle.join();
    }

    let result = guard.check_rate_limit(s1);
    assert!(result.is_err(), "61st request should fail (rate limit is 60/min)");
}

// ============================================================================
// DEADLINE CONSTRAINT TESTS (New Feature)
// ============================================================================

#[test]
fn test_temporal_guard_deadline_not_exceeded() {
    let guard = TemporalGuard::new(vec![]);
    let s1 = sovereign(1);

    let deadline = std::time::SystemTime::now() + Duration::from_secs(10);
    let result = guard.check_with_deadline(s1, PolicyAction::Spawn, deadline);
    assert!(result.is_ok(), "Action should be allowed before deadline");
}

#[test]
fn test_temporal_guard_deadline_exceeded() {
    let guard = TemporalGuard::new(vec![]);
    let s1 = sovereign(1);

    let deadline = std::time::SystemTime::now() - Duration::from_secs(1);
    let result = guard.check_with_deadline(s1, PolicyAction::Spawn, deadline);
    assert!(result.is_err(), "Action should be denied after deadline");
}

// ============================================================================
// SCHEDULED REVOCATION TESTS (New Feature)
// ============================================================================

#[test]
fn test_temporal_guard_scheduled_revocation_not_active() {
    let guard = TemporalGuard::new(vec![]);
    let s1 = sovereign(1);

    let revoke_time = std::time::SystemTime::now() + Duration::from_secs(10);
    guard.register_scheduled_revocation(s1, revoke_time);

    let result = guard.check_rate_limit(s1);
    assert!(result.is_ok(), "Action should be allowed before revocation time");
}

#[test]
fn test_temporal_guard_scheduled_revocation_active() {
    let guard = TemporalGuard::new(vec![]);
    let s1 = sovereign(1);

    let revoke_time = std::time::SystemTime::now() - Duration::from_secs(1);
    guard.register_scheduled_revocation(s1, revoke_time);

    let result = guard.check_rate_limit(s1);
    assert!(result.is_err(), "Action should be denied after revocation time");
}

// ============================================================================
// EDGE CASES & BOUNDARY CONDITIONS
// ============================================================================

#[test]
fn test_temporal_guard_rate_limit_exactly_at_capacity() {
    let guard = TemporalGuard::new(vec![]);
    let s1 = sovereign(1);

    for _ in 0..60 {
        let _ = guard.check_rate_limit(s1);
    }

    let result = guard.check_rate_limit(s1);
    assert!(result.is_err(), "Request at capacity+1 should fail");
}

#[test]
fn test_rate_limiter_zero_capacity() {
    let limiter = RateLimiter::new(0, Duration::from_secs(1));
    assert!(limiter.try_consume().is_err(), "Zero capacity should deny all requests");
}

#[test]
fn test_rate_limiter_very_short_refill_period() {
    let limiter = RateLimiter::new(1, Duration::from_millis(10));
    assert!(limiter.try_consume().is_ok());
    assert!(limiter.try_consume().is_err());

    std::thread::sleep(Duration::from_millis(20));

    assert!(limiter.try_consume().is_ok(), "Token should be refilled");
}

#[test]
fn test_temporal_guard_multiple_sovereigns_independent() {
    let guard = TemporalGuard::new(vec![]);
    let s1 = sovereign(1);
    let s2 = sovereign(2);
    let s3 = sovereign(3);

    // Each sovereign can make 60 requests independently
    for _ in 0..60 {
        let _ = guard.check_rate_limit(s1);
        let _ = guard.check_rate_limit(s2);
        let _ = guard.check_rate_limit(s3);
    }

    // All should be at capacity
    assert!(guard.check_rate_limit(s1).is_err());
    assert!(guard.check_rate_limit(s2).is_err());
    assert!(guard.check_rate_limit(s3).is_err());
}

#[test]
fn test_temporal_guard_window_multiple_allowed_ranges() {
    let window = TimeWindow {
        id: Uuid::new_v4(),
        name: "split_hours".to_string(),
        applies_to: PolicyAction::Spawn,
        allowed_hours: vec![(9, 12), (14, 17)],
        blackout_dates: vec![],
    };

    let guard = TemporalGuard::new(vec![window]);
    let result = guard.check_time_window(PolicyAction::Spawn);
    // Result depends on current hour, but should not panic
    let _ = result;
}
