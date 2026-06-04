use std::collections::VecDeque;
use std::sync::Arc;
use std::sync::Mutex;
use std::time::{SystemTime, Duration};
use uuid::Uuid;
use dashmap::DashMap;
use chrono::{Utc, Datelike, Timelike, Weekday};
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
    pub applies_to: Option<PolicyAction>,  // None = applies to all
    pub allowed_hours: Vec<(u8, u8)>,
    pub blackout_dates: Vec<(u32, u32)>,
    pub day_of_week: Option<Vec<u32>>,  // 0=Mon, 6=Sun, None = all days
}

#[derive(Debug, Clone)]
struct RateLimit {
    max_per_minute: u32,
    requests: VecDeque<SystemTime>,
}

/// Token bucket rate limiter with configurable capacity and refill period.
/// Allows a maximum number of tokens (capacity) that refill over the refill_period.
pub struct RateLimiter {
    capacity: u32,
    refill_period: Duration,
    tokens: Mutex<f64>,
    last_refill: Mutex<SystemTime>,
}

impl RateLimiter {
    /// Create a new RateLimiter with the given capacity and refill period.
    ///
    /// # Arguments
    /// * `capacity` - Maximum number of tokens
    /// * `refill_period` - Duration after which the bucket is refilled to capacity
    pub fn new(capacity: u32, refill_period: Duration) -> Self {
        RateLimiter {
            capacity,
            refill_period,
            tokens: Mutex::new(capacity as f64),
            last_refill: Mutex::new(SystemTime::now()),
        }
    }

    /// Attempt to consume one token. Returns Ok if a token was consumed, Err otherwise.
    pub fn try_consume(&self) -> Result<(), String> {
        let now = SystemTime::now();
        let mut tokens = self.tokens.lock().unwrap();
        let mut last_refill = self.last_refill.lock().unwrap();

        // Calculate tokens to add based on elapsed time
        if let Ok(elapsed) = now.duration_since(*last_refill) {
            let refill_count = elapsed.as_secs_f64() / self.refill_period.as_secs_f64();
            let new_tokens = *tokens + (refill_count * self.capacity as f64);
            *tokens = new_tokens.min(self.capacity as f64);
            *last_refill = now;
        }

        if *tokens >= 1.0 {
            *tokens -= 1.0;
            Ok(())
        } else {
            Err("Rate limit exceeded".to_string())
        }
    }
}

/// Cached decision with timestamp for 1-minute TTL
#[derive(Debug, Clone)]
struct CachedDecision {
    allowed: bool,
    reason: Option<String>,
    timestamp: SystemTime,
}

impl CachedDecision {
    fn is_expired(&self) -> bool {
        match SystemTime::now().duration_since(self.timestamp) {
            Ok(elapsed) => elapsed > Duration::from_secs(60),
            Err(_) => true,
        }
    }
}

/// Per-actor, per-resource rate limiter using sliding window
#[derive(Debug, Clone)]
struct RateLimitState {
    requests: VecDeque<SystemTime>,
    max_per_minute: u32,
}

impl RateLimitState {
    fn new(max_per_minute: u32) -> Self {
        RateLimitState {
            requests: VecDeque::new(),
            max_per_minute,
        }
    }

    fn try_request(&mut self) -> bool {
        let now = SystemTime::now();

        // Expire old requests (older than 60 seconds)
        while let Some(&oldest) = self.requests.front() {
            match now.duration_since(oldest) {
                Ok(elapsed) if elapsed > Duration::from_secs(60) => {
                    self.requests.pop_front();
                }
                _ => break,
            }
        }

        // Check if at capacity
        if self.requests.len() >= self.max_per_minute as usize {
            return false;
        }

        // Record this request
        self.requests.push_back(now);
        true
    }

    fn current_count(&mut self) -> usize {
        let now = SystemTime::now();

        // Expire old requests
        while let Some(&oldest) = self.requests.front() {
            match now.duration_since(oldest) {
                Ok(elapsed) if elapsed > Duration::from_secs(60) => {
                    self.requests.pop_front();
                }
                _ => break,
            }
        }

        self.requests.len()
    }
}

pub struct TemporalGuard {
    // Old API: per-actor-only rate limiting for backward compatibility
    rate_limiter_legacy: Arc<DashMap<Uuid, RateLimit>>,

    // New API: per-(actor, resource) rate limiting
    rate_limiter: Arc<DashMap<(Uuid, Uuid), RateLimitState>>,

    time_windows: Arc<Vec<TimeWindow>>,
    scheduled_revocations: Arc<DashMap<Uuid, SystemTime>>,

    // Decision cache: (actor_id, resource_id) -> CachedDecision
    decision_cache: Arc<DashMap<(Uuid, Uuid), CachedDecision>>,
}

impl TemporalGuard {
    pub fn new(time_windows: Vec<TimeWindow>) -> Self {
        TemporalGuard {
            rate_limiter_legacy: Arc::new(DashMap::new()),
            rate_limiter: Arc::new(DashMap::new()),
            time_windows: Arc::new(time_windows),
            scheduled_revocations: Arc::new(DashMap::new()),
            decision_cache: Arc::new(DashMap::new()),
        }
    }

    /// NEW API: Check (actor_id, resource_id) pair with rate limit + time window
    /// Uses decision caching (1-min TTL)
    pub fn check_with_resource(&self, actor_id: Uuid, resource_id: Uuid) -> Result<(), DenyReason> {
        let key = (actor_id, resource_id);

        // Check cache first
        if let Some(cached) = self.decision_cache.get(&key) {
            if !cached.is_expired() {
                if cached.allowed {
                    return Ok(());
                } else {
                    return Err(DenyReason::TemporalViolation(
                        cached.reason.clone().unwrap_or_default(),
                    ));
                }
            }
        }

        // Cache miss or expired: re-evaluate

        // Check rate limit first (per-actor, per-resource)
        let mut entry = self
            .rate_limiter
            .entry(key)
            .or_insert_with(|| RateLimitState::new(60));

        if !entry.try_request() {
            let count = entry.current_count();
            let reason = format!("Rate limit exceeded: {}/60 requests in last 60s", count);
            drop(entry); // Release the entry

            self.decision_cache.insert(
                key,
                CachedDecision {
                    allowed: false,
                    reason: Some(reason.clone()),
                    timestamp: SystemTime::now(),
                },
            );
            return Err(DenyReason::TemporalViolation(reason));
        }

        // Check time windows
        if let Err(e) = self.check_time_window_utc(resource_id) {
            self.decision_cache.insert(
                key,
                CachedDecision {
                    allowed: false,
                    reason: Some(format!("{:?}", e)),
                    timestamp: SystemTime::now(),
                },
            );
            return Err(e);
        }

        self.decision_cache.insert(
            key,
            CachedDecision {
                allowed: true,
                reason: None,
                timestamp: SystemTime::now(),
            },
        );
        Ok(())
    }

    /// Invalidate entire cache (for policy changes)
    pub fn invalidate_cache(&self) {
        self.decision_cache.clear();
    }

    /// Invalidate cache for specific actor+resource
    pub fn invalidate_cache_for(&self, actor_id: Uuid, resource_id: Uuid) {
        self.decision_cache.remove(&(actor_id, resource_id));
    }

    /// OLD API: Check rate limit per sovereign (backward compat)
    pub fn check_rate_limit(&self, sovereign_id: Uuid) -> Result<(), DenyReason> {
        // Check scheduled revocation first
        self.check_scheduled_revocation(sovereign_id)?;

        let now = SystemTime::now();
        let mut rate = self
            .rate_limiter_legacy
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

    /// Check time window using UTC time
    pub fn check_time_window_utc(&self, _resource_id: Uuid) -> Result<(), DenyReason> {
        let now = Utc::now();
        let hour = now.hour() as u8;
        let (month, day) = (now.month(), now.day());
        let weekday = now.weekday();
        let weekday_num = match weekday {
            Weekday::Mon => 0,
            Weekday::Tue => 1,
            Weekday::Wed => 2,
            Weekday::Thu => 3,
            Weekday::Fri => 4,
            Weekday::Sat => 5,
            Weekday::Sun => 6,
        };

        for window in self.time_windows.iter() {
            // Skip windows that don't apply to this resource
            if let Some(applies_to) = window.applies_to {
                // If applies_to is set, this window only applies to specific actions
                // For the new API, we ignore this and apply to resources
                let _ = applies_to;
            }

            // Check blackout date first (highest priority)
            if window.blackout_dates.contains(&(month, day)) {
                return Err(DenyReason::TemporalViolation(format!(
                    "Blackout date: {}-{}",
                    month, day
                )));
            }

            // Check day-of-week filtering if specified
            if let Some(ref allowed_days) = window.day_of_week {
                if !allowed_days.contains(&weekday_num) {
                    continue; // This window doesn't apply to this day
                }
            }

            // Check allowed hours
            let hour_allowed = window
                .allowed_hours
                .iter()
                .any(|(start, end)| hour >= *start && hour < *end);

            if !hour_allowed {
                return Err(DenyReason::TemporalViolation(format!(
                    "Outside allowed hours: {} UTC",
                    hour
                )));
            }

            // If we get here, this window allows it
            return Ok(());
        }

        // No windows configured or none blocked it
        Ok(())
    }

    /// OLD API: Check time window by action
    pub fn check_time_window(&self, action: PolicyAction) -> Result<(), DenyReason> {
        let now = Utc::now();
        let hour = now.hour() as u8;
        let (month, day) = (now.month(), now.day());

        for window in self.time_windows.iter() {
            if let Some(applies_to) = window.applies_to {
                if applies_to != action {
                    continue;
                }
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

    /// OLD API: Check both rate limit and time window
    pub fn check(&self, sovereign_id: Uuid, action: PolicyAction) -> Result<(), DenyReason> {
        self.check_rate_limit(sovereign_id)?;
        self.check_time_window(action)?;
        Ok(())
    }

    /// Check if action is allowed with a deadline constraint.
    /// Returns Err if the deadline has passed.
    pub fn check_with_deadline(
        &self,
        sovereign_id: Uuid,
        action: PolicyAction,
        deadline: SystemTime,
    ) -> Result<(), DenyReason> {
        let now = SystemTime::now();
        if now > deadline {
            return Err(DenyReason::TemporalViolation(
                "Deadline has passed".to_string(),
            ));
        }
        self.check(sovereign_id, action)
    }

    /// Register a scheduled revocation time for a sovereign.
    /// After this time, actions by this sovereign will be blocked.
    pub fn register_scheduled_revocation(&self, sovereign_id: Uuid, revocation_time: SystemTime) {
        self.scheduled_revocations.insert(sovereign_id, revocation_time);
    }

    /// Check if a sovereign has been revoked due to scheduled revocation.
    fn check_scheduled_revocation(&self, sovereign_id: Uuid) -> Result<(), DenyReason> {
        if let Some(revocation_entry) = self.scheduled_revocations.get(&sovereign_id) {
            let revocation_time = *revocation_entry;
            if SystemTime::now() >= revocation_time {
                return Err(DenyReason::TemporalViolation(
                    "Sovereign access revoked".to_string(),
                ));
            }
        }
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
            applies_to: Some(PolicyAction::Spawn),
            allowed_hours: vec![(9, 17)],
            blackout_dates: vec![],
            day_of_week: None,
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
            applies_to: Some(PolicyAction::CreatePolicy),
            allowed_hours: vec![(0, 24)],
            blackout_dates: vec![(today.month(), today.day())],
            day_of_week: None,
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
            applies_to: Some(PolicyAction::Pause),
            allowed_hours: vec![(9, 17)],
            blackout_dates: vec![],
            day_of_week: None,
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
            applies_to: Some(PolicyAction::Spawn),
            allowed_hours: vec![(0, 24)],
            blackout_dates: vec![(today.month(), today.day())],
            day_of_week: None,
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
