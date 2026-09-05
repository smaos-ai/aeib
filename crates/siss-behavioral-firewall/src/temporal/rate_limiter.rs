use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct RateLimiter {
    pub max_requests: u32,
    pub window_seconds: u64, // 60 for 60 req/min
}

impl RateLimiter {
    pub fn new(max_requests: u32, window_seconds: u64) -> Self {
        RateLimiter {
            max_requests,
            window_seconds,
        }
    }

    pub fn is_within_limit(&self, current_count: u32) -> bool {
        current_count < self.max_requests
    }

    pub fn should_expire(&self, request_time: DateTime<Utc>, now: DateTime<Utc>) -> bool {
        let age_seconds = now.timestamp() - request_time.timestamp();
        age_seconds >= self.window_seconds as i64
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_rate_limiter_creation() {
        let limiter = RateLimiter::new(60, 60);
        assert_eq!(limiter.max_requests, 60);
        assert_eq!(limiter.window_seconds, 60);
    }

    #[test]
    fn test_is_within_limit() {
        let limiter = RateLimiter::new(60, 60);
        assert!(limiter.is_within_limit(59));
        assert!(!limiter.is_within_limit(60));
        assert!(!limiter.is_within_limit(61));
    }

    #[test]
    fn test_should_expire() {
        let limiter = RateLimiter::new(60, 60);
        let now = Utc::now();
        let old_time = now - chrono::Duration::seconds(61);
        let recent_time = now - chrono::Duration::seconds(30);

        assert!(limiter.should_expire(old_time, now));
        assert!(!limiter.should_expire(recent_time, now));
    }
}
