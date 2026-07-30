use chrono::{DateTime, Datelike, Timelike, Utc};
use dashmap::DashMap;
use uuid::Uuid;

use super::rate_limiter::RateLimiter;
use super::types::{BlackoutDate, Decision, TemporalError, TimeWindow};

pub struct TemporalGuard {
    rate_limiter: RateLimiter,
    request_tracker: DashMap<Uuid, Vec<DateTime<Utc>>>, // requester_id → timestamps
    allowed_windows: Vec<TimeWindow>,
    blackout_dates: Vec<BlackoutDate>,
}

impl TemporalGuard {
    pub fn new(max_requests: u32, window_seconds: u64) -> Self {
        TemporalGuard {
            rate_limiter: RateLimiter::new(max_requests, window_seconds),
            request_tracker: DashMap::new(),
            allowed_windows: Vec::new(),
            blackout_dates: Vec::new(),
        }
    }

    pub fn with_time_window(mut self, start_hour: u8, end_hour: u8, allowed: bool) -> Self {
        if let Ok(window) = TimeWindow::new(start_hour, end_hour, allowed) {
            self.allowed_windows.push(window);
        }
        self
    }

    pub fn with_blackout_date(mut self, month: u8, day: u8, reason: String) -> Self {
        if let Ok(blackout) = BlackoutDate::new(month, day, reason) {
            self.blackout_dates.push(blackout);
        }
        self
    }

    pub fn check_rate_limit(&self, requester_id: Uuid) -> Result<bool, TemporalError> {
        let now = Utc::now();

        // Get or create entry for requester
        let mut entry = self.request_tracker.entry(requester_id).or_default();

        // Remove expired timestamps (older than window_seconds)
        entry.retain(|&ts| !self.rate_limiter.should_expire(ts, now));

        // Check if we're within limit
        let current_count = entry.len() as u32;
        if self.rate_limiter.is_within_limit(current_count) {
            // Add current request
            entry.push(now);
            Ok(true)
        } else {
            // Over limit
            Ok(false)
        }
    }

    pub fn check_time_window(&self, now: DateTime<Utc>) -> Result<bool, TemporalError> {
        let hour = now.hour() as u8;

        // If no windows configured, allow all times
        if self.allowed_windows.is_empty() {
            return Ok(true);
        }

        // Track whether we found any matching window
        let mut found_matching_window = false;
        let mut allowed_result = true;

        // Check each window
        for window in &self.allowed_windows {
            if window.contains_hour(hour) {
                found_matching_window = true;
                // Hour matches this window - check the allowed flag
                if !window.allowed {
                    // This window blocks the hour
                    allowed_result = false;
                    break;
                }
                // Continue checking - if multiple windows match, any block=false blocks it
            }
        }

        // If no window matched the hour, deny (when windows are configured)
        // If a window matched with allowed=false, deny
        // If only allowed=true windows matched, allow
        if found_matching_window {
            Ok(allowed_result)
        } else {
            // Hour not in any window - deny since windows are configured
            Ok(false)
        }
    }

    pub fn check_blackout_date(&self, now: DateTime<Utc>) -> Result<bool, TemporalError> {
        let month = now.month() as u8;
        let day = now.day() as u8;

        // Check if today matches any blackout date
        for blackout in &self.blackout_dates {
            if blackout.matches_date(month, day) {
                // Today is a blackout date
                return Ok(false);
            }
        }

        // Not a blackout date
        Ok(true)
    }

    pub fn evaluate(
        &self,
        requester_id: Uuid,
        now: DateTime<Utc>,
    ) -> Result<Decision, TemporalError> {
        // All three checks must pass: rate limit AND time window AND not blackout
        let rate_ok = self.check_rate_limit(requester_id)?;
        let time_ok = self.check_time_window(now)?;
        let date_ok = self.check_blackout_date(now)?;

        if rate_ok && time_ok && date_ok {
            Ok(Decision::Allow)
        } else {
            Ok(Decision::Deny)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new_temporal_guard() {
        let guard = TemporalGuard::new(60, 60);
        assert_eq!(guard.rate_limiter.max_requests, 60);
        assert_eq!(guard.rate_limiter.window_seconds, 60);
    }

    #[test]
    fn test_with_time_window() {
        let guard = TemporalGuard::new(60, 60).with_time_window(9, 17, true);
        assert_eq!(guard.allowed_windows.len(), 1);
        assert_eq!(guard.allowed_windows[0].start_hour, 9);
        assert_eq!(guard.allowed_windows[0].end_hour, 17);
        assert!(guard.allowed_windows[0].allowed);
    }

    #[test]
    fn test_with_blackout_date() {
        let guard = TemporalGuard::new(60, 60).with_blackout_date(12, 25, "Christmas".to_string());
        assert_eq!(guard.blackout_dates.len(), 1);
        assert_eq!(guard.blackout_dates[0].month, 12);
        assert_eq!(guard.blackout_dates[0].day, 25);
    }

    #[test]
    fn test_check_time_window_no_windows() {
        let guard = TemporalGuard::new(60, 60);
        let now = Utc::now();
        let result = guard.check_time_window(now);
        assert!(result.is_ok());
        assert!(result.unwrap());
    }

    #[test]
    fn test_check_blackout_date_no_blackouts() {
        let guard = TemporalGuard::new(60, 60);
        let now = Utc::now();
        let result = guard.check_blackout_date(now);
        assert!(result.is_ok());
        assert!(result.unwrap());
    }
}
