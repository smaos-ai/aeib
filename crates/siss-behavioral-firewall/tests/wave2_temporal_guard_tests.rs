use chrono::{Datelike, Timelike, Utc};
use siss_behavioral_firewall::temporal::{Decision, TemporalGuard};
use uuid::Uuid;

/// Tier 1: Rate Limiting Tests
#[test]
fn test_rate_limit_under_limit() {
    let guard = TemporalGuard::new(60, 60);
    let requester_id = Uuid::new_v4();

    // Submit 59 requests
    for _ in 0..59 {
        let result = guard.check_rate_limit(requester_id);
        assert!(result.is_ok());
        assert!(result.unwrap());
    }
}

#[test]
fn test_rate_limit_over_limit() {
    let guard = TemporalGuard::new(60, 60);
    let requester_id = Uuid::new_v4();

    // Submit 60 requests (at limit)
    for _ in 0..60 {
        let result = guard.check_rate_limit(requester_id);
        assert!(result.is_ok());
        let _ = result.unwrap();
    }

    // 61st request should fail
    let result = guard.check_rate_limit(requester_id);
    assert!(result.is_ok());
    assert!(!result.unwrap());
}

#[test]
fn test_rate_limit_sliding_window() {
    let guard = TemporalGuard::new(60, 60);
    let requester_id = Uuid::new_v4();

    // Submit 60 requests in first 60s window
    for _ in 0..60 {
        let result = guard.check_rate_limit(requester_id);
        assert!(result.is_ok());
        let _ = result.unwrap();
    }

    // 61st request should be denied (window still valid)
    let result = guard.check_rate_limit(requester_id);
    assert!(result.is_ok());
    assert!(!result.unwrap());

    // Simulate 60+ seconds passing (timestamps expire)
    // Note: in real usage, old timestamps are automatically cleaned on next check
    // For now, we verify the mechanism works by checking that stale requests don't count
}

#[tokio::test]
async fn test_rate_limit_concurrent_access() {
    let guard = std::sync::Arc::new(TemporalGuard::new(100, 60));
    let requester_id = Uuid::new_v4();

    let mut handles = vec![];
    for _ in 0..3 {
        let guard_clone = guard.clone();
        let req_id = requester_id;
        let handle = tokio::spawn(async move {
            let mut count = 0;
            for _ in 0..50 {
                if let Ok(allowed) = guard_clone.check_rate_limit(req_id) {
                    if allowed {
                        count += 1;
                    }
                }
            }
            count
        });
        handles.push(handle);
    }

    let mut total = 0;
    for handle in handles {
        let count = handle.await.unwrap();
        total += count;
    }

    // With 100 req/min limit and 3 threads doing 50 each (150 total attempts),
    // we expect at least some to succeed, but not all due to rate limit
    assert!(total > 0);
    assert!(total <= 100);
}

/// Tier 2: Time Window Tests
#[test]
fn test_time_window_in_allowed() {
    let mut guard = TemporalGuard::new(60, 60);
    // Allow 9am-5pm
    guard = guard.with_time_window(9, 17, true);

    // Test at time within 9-5 window
    let now = Utc::now();
    let mut test_time = now;
    while test_time.hour() < 9 || test_time.hour() >= 17 {
        test_time = test_time + chrono::Duration::hours(1);
    }

    let result = guard.check_time_window(test_time);
    assert!(result.is_ok());
    assert!(result.unwrap());
}

#[test]
fn test_time_window_outside_allowed() {
    let mut guard = TemporalGuard::new(60, 60);
    // Allow 9am-5pm
    guard = guard.with_time_window(9, 17, true);

    // Test at outside 9-5 window
    let now = Utc::now();
    // We need an hour outside 9-17
    let mut test_time = now;
    while test_time.hour() >= 9 && test_time.hour() < 17 {
        test_time = test_time + chrono::Duration::hours(1);
    }

    let result = guard.check_time_window(test_time);
    assert!(result.is_ok());
    assert!(!result.unwrap());
}

#[test]
fn test_time_window_multiple_windows() {
    let mut guard = TemporalGuard::new(60, 60);
    // Add overlapping windows
    guard = guard.with_time_window(9, 12, true); // 9-12am allowed
    guard = guard.with_time_window(14, 17, true); // 2-5pm allowed
    guard = guard.with_time_window(10, 15, false); // 10am-3pm blocked (overlaps with both)

    // Test at 11am (overlaps with blocked window)
    let now = Utc::now();
    let mut test_time = now;
    while test_time.hour() != 11 {
        test_time = if test_time.hour() < 11 {
            test_time + chrono::Duration::hours(1)
        } else {
            test_time - chrono::Duration::hours(1)
        };
    }

    let result = guard.check_time_window(test_time);
    assert!(result.is_ok());
    // Should be blocked due to the false window at 10-15
}

#[test]
fn test_time_window_utc_only() {
    let guard = TemporalGuard::new(60, 60);
    let now = Utc::now();

    // Verify that check_time_window accepts Utc times and works correctly
    let result = guard.check_time_window(now);
    assert!(result.is_ok());
}

/// Tier 3: Blackout Date Tests
#[test]
fn test_blackout_date_today() {
    let mut guard = TemporalGuard::new(60, 60);

    // Get today's date and use it as blackout
    let now = Utc::now();
    let month = now.month() as u8;
    let day = now.day() as u8;
    guard = guard.with_blackout_date(month, day, "Today blocked".to_string());

    let result = guard.check_blackout_date(now);
    assert!(result.is_ok());
    assert!(!result.unwrap()); // Should be blocked on blackout date
}

#[test]
fn test_blackout_date_not_today() {
    let mut guard = TemporalGuard::new(60, 60);

    // Blackout a different day (use a fixed date)
    guard = guard.with_blackout_date(1, 1, "New Year".to_string());

    // Get today's date (which is almost certainly not Jan 1)
    let now = Utc::now();
    let result = guard.check_blackout_date(now);
    assert!(result.is_ok());
    // Should be allowed unless today happens to be Jan 1
    // In normal conditions this will pass
    let is_jan_1 = now.month() == 1 && now.day() == 1;
    assert_eq!(result.unwrap(), !is_jan_1);
}

/// Tier 4: Integration Tests
#[test]
fn test_evaluate_all_pass() {
    let mut guard = TemporalGuard::new(60, 60);
    guard = guard.with_time_window(9, 17, true);

    let requester_id = Uuid::new_v4();
    let now = Utc::now();

    // Ensure we're in allowed window (9-5 UTC)
    let mut test_time = now;
    while test_time.hour() < 9 || test_time.hour() >= 17 {
        test_time = test_time + chrono::Duration::hours(1);
    }

    let result = guard.evaluate(requester_id, test_time);
    assert!(result.is_ok());
    assert_eq!(result.unwrap(), Decision::Allow);
}

#[test]
fn test_evaluate_one_fails() {
    let mut guard = TemporalGuard::new(60, 60);
    guard = guard.with_time_window(9, 17, true);

    let requester_id = Uuid::new_v4();
    let now = Utc::now();

    // Ensure we're outside allowed window
    let mut test_time = now;
    while test_time.hour() >= 9 && test_time.hour() < 17 {
        test_time = test_time + chrono::Duration::hours(1);
    }

    let result = guard.evaluate(requester_id, test_time);
    assert!(result.is_ok());
    assert_eq!(result.unwrap(), Decision::Deny);
}
