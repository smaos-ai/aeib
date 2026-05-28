use siss_multi_region::health_check::{CircuitBreakerState, HealthChecker};
use std::time::Duration;

#[test]
fn test_closed_to_open_after_threshold() {
    let mut cb = CircuitBreakerState::new();

    assert!(cb.is_closed());
    cb.record_failure(3);
    assert!(cb.is_closed());
    cb.record_failure(3);
    assert!(cb.is_closed());
    cb.record_failure(3);
    assert!(cb.is_open());
}

#[test]
fn test_open_half_opens_after_timeout() {
    let mut cb = CircuitBreakerState::new();

    for _ in 0..3 {
        cb.record_failure(3);
    }
    assert!(cb.is_open());

    cb.try_reset();
    assert!(cb.is_half_open());
}

#[test]
fn test_half_open_closes_on_success() {
    let mut cb = CircuitBreakerState::new();

    for _ in 0..3 {
        cb.record_failure(3);
    }
    assert!(cb.is_open());

    cb.try_reset();
    assert!(cb.is_half_open());

    cb.record_success();
    assert!(cb.is_closed());
}

#[test]
fn test_half_open_reopens_on_failure() {
    let mut cb = CircuitBreakerState::new();

    for _ in 0..3 {
        cb.record_failure(3);
    }
    assert!(cb.is_open());

    cb.try_reset();
    assert!(cb.is_half_open());

    cb.record_failure(3);
    assert!(cb.is_open());
}

#[tokio::test]
async fn test_circuit_breaker_integration_with_health_checker() {
    let checker = HealthChecker::new(Duration::from_secs(5));
    checker.register_region("test_region".to_string()).await.unwrap();

    for _ in 0..3 {
        checker.record_failure("test_region").await.unwrap();
    }

    let status = checker.get_region_status("test_region").await.unwrap();
    assert_eq!(status, siss_multi_region::health_check::HealthStatus::Unhealthy);
}
