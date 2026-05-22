use std::collections::VecDeque;
use std::sync::Arc;
use std::time::{SystemTime, Duration};
use uuid::Uuid;
use dashmap::DashMap;
use chrono::{Utc, Datelike, Timelike};
use serde::{Serialize, Deserialize};

use crate::rebac::DenyReason;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum PolicyAction {
    Spawn, Pause, Resume, Abort, Terminate,
    AssignTask, CancelTask, FinalizeTask,
    InitiateConsent, VoteConsent, RevokeGrant,
    ReadMetrics, StreamEvents,
    CreatePolicy, UpdatePolicy, DeletePolicy,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimeWindow {
    pub id: Uuid,
    pub name: String,
    pub applies_to: PolicyAction,
    pub allowed_hours: Vec<(u8, u8)>,
    pub blackout_dates: Vec<(u32, u32)>,
}

#[derive(Debug, Clone)]
struct RateLimit {
    max_per_minute: u32,
    requests: VecDeque<SystemTime>,
}

pub struct TemporalGuard {
    rate_limiter: Arc<DashMap<Uuid, RateLimit>>,
    time_windows: Arc<Vec<TimeWindow>>,
}

impl TemporalGuard {
    pub fn new(time_windows: Vec<TimeWindow>) -> Self {
        TemporalGuard {
            rate_limiter: Arc::new(DashMap::new()),
            time_windows: Arc::new(time_windows),
        }
    }

    pub fn check_rate_limit(&self, sovereign_id: Uuid) -> Result<(), DenyReason> {
        let now = SystemTime::now();
        let mut rate = self
            .rate_limiter
            .entry(sovereign_id)
            .or_insert_with(|| RateLimit {
                max_per_minute: 60,
                requests: VecDeque::new(),
            });

        // Expire old requests (older than 60 seconds)
        while let Some(&oldest) = rate.requests.front() {
            match now.duration_since(oldest) {
                Ok(elapsed) if elapsed > Duration::from_secs(60) => {
                    rate.requests.pop_front();
                }
                _ => break,
            }
        }

        if rate.requests.len() >= rate.max_per_minute as usize {
            return Err(DenyReason::TemporalViolation(format!(
                "Rate limit exceeded: {} req/min",
                rate.requests.len()
            )));
        }

        rate.requests.push_back(now);
        Ok(())
    }

    pub fn check_time_window(&self, action: PolicyAction) -> Result<(), DenyReason> {
        let now = Utc::now();
        let hour = now.hour() as u8;
        let (month, day) = (now.month(), now.day());

        for window in self.time_windows.iter() {
            if window.applies_to != action {
                continue;
            }

            // Check blackout date
            if window.blackout_dates.contains(&(month, day)) {
                return Err(DenyReason::TemporalViolation(format!(
                    "Action blocked on {}-{}",
                    month, day
                )));
            }

            // Check allowed hours
            let allowed = window
                .allowed_hours
                .iter()
                .any(|(start, end)| hour >= *start && hour < *end);

            if !allowed {
                return Err(DenyReason::TemporalViolation(format!(
                    "Action not allowed at hour {}",
                    hour
                )));
            }
        }

        Ok(())
    }

    pub fn check(&self, sovereign_id: Uuid, action: PolicyAction) -> Result<(), DenyReason> {
        self.check_rate_limit(sovereign_id)?;
        self.check_time_window(action)?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sovereign(id: u64) -> Uuid {
        Uuid::from_u64_pair(id, 0)
    }

    #[test]
    fn test_rate_limit_60_allowed() {
        let guard = TemporalGuard::new(vec![]);
        let s1 = sovereign(1);

        for i in 0..60 {
            let result = guard.check_rate_limit(s1);
            assert!(result.is_ok(), "Request {} should be allowed", i);
        }
    }

    #[test]
    fn test_rate_limit_61st_denied() {
        let guard = TemporalGuard::new(vec![]);
        let s1 = sovereign(1);

        for _ in 0..60 {
            let _ = guard.check_rate_limit(s1);
        }

        let result = guard.check_rate_limit(s1);
        assert!(result.is_err());
    }

    #[test]
    fn test_rate_limit_sliding_window() {
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
    fn test_independent_rate_limits() {
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
    fn test_time_window_allowed_hours() {
        let window = TimeWindow {
            id: Uuid::new_v4(),
            name: "business_hours".to_string(),
            applies_to: PolicyAction::Spawn,
            allowed_hours: vec![(9, 17)],
            blackout_dates: vec![],
        };

        let guard = TemporalGuard::new(vec![window]);
        let _ = guard.check_time_window(PolicyAction::Spawn);
    }

    #[test]
    fn test_time_window_blackout_dates() {
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
        assert!(result.is_err());
    }

    #[test]
    fn test_no_applicable_time_window() {
        let window = TimeWindow {
            id: Uuid::new_v4(),
            name: "other_action".to_string(),
            applies_to: PolicyAction::Pause,
            allowed_hours: vec![(9, 17)],
            blackout_dates: vec![],
        };

        let guard = TemporalGuard::new(vec![window]);
        let result = guard.check_time_window(PolicyAction::Spawn);
        assert!(result.is_ok());
    }

    #[test]
    fn test_composite_check_both_pass() {
        let guard = TemporalGuard::new(vec![]);
        let s1 = sovereign(1);

        let result = guard.check(s1, PolicyAction::Spawn);
        assert!(result.is_ok());
    }

    #[test]
    fn test_composite_check_rate_limit_fail() {
        let guard = TemporalGuard::new(vec![]);
        let s1 = sovereign(1);

        for _ in 0..60 {
            let _ = guard.check_rate_limit(s1);
        }

        let result = guard.check(s1, PolicyAction::Spawn);
        assert!(result.is_err());
    }

    #[test]
    fn test_composite_check_time_window_fail() {
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
        assert!(result.is_err());
    }

    #[test]
    fn test_utc_only_time() {
        let guard = TemporalGuard::new(vec![]);
        let _ = guard.check_time_window(PolicyAction::Spawn);
    }

    #[test]
    fn test_concurrent_rate_checks() {
        let guard = Arc::new(TemporalGuard::new(vec![]));
        let s1 = sovereign(1);

        let mut handles = vec![];

        for _ in 0..5 {
            let guard_clone = guard.clone();
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
}
