use dashmap::DashMap;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;

use crate::license_model::LicenseEnforcer;
use crate::types::{LicenseError, Sku};

pub struct UsageTracker {
    counters: Arc<DashMap<String, Arc<AtomicU64>>>,
}

impl UsageTracker {
    pub fn new() -> Self {
        Self {
            counters: Arc::new(DashMap::new()),
        }
    }

    pub fn record_call(&self, license_key: &str, sku: &Sku) -> Result<(), LicenseError> {
        let enforcer = LicenseEnforcer;

        let counter = self
            .counters
            .entry(license_key.to_string())
            .or_insert_with(|| Arc::new(AtomicU64::new(0)))
            .clone();

        let current = counter.load(Ordering::SeqCst);
        enforcer.check_api_quota(sku, current)?;

        counter.fetch_add(1, Ordering::SeqCst);
        Ok(())
    }

    pub fn get_count(&self, license_key: &str) -> u64 {
        self.counters
            .get(license_key)
            .map(|entry| entry.load(Ordering::SeqCst))
            .unwrap_or(0)
    }

    pub fn reset_count(&self, license_key: &str) {
        if let Some(counter) = self.counters.get(license_key) {
            counter.store(0, Ordering::SeqCst);
        }
    }
}

impl Default for UsageTracker {
    fn default() -> Self {
        Self::new()
    }
}

impl Clone for UsageTracker {
    fn clone(&self) -> Self {
        Self {
            counters: Arc::clone(&self.counters),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_usage_counter_increments() {
        let tracker = UsageTracker::new();
        let key = "SISS-Pro-0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000-20251225";

        assert!(tracker.record_call(key, &Sku::Pro).is_ok());
        assert_eq!(tracker.get_count(key), 1);
    }

    #[test]
    fn test_usage_counter_per_license_key() {
        let tracker = UsageTracker::new();
        let key1 = "SISS-Pro-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-20251225";
        let key2 = "SISS-Pro-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb-20251225";

        tracker.record_call(key1, &Sku::Pro).ok();
        tracker.record_call(key1, &Sku::Pro).ok();
        tracker.record_call(key2, &Sku::Pro).ok();

        assert_eq!(tracker.get_count(key1), 2);
        assert_eq!(tracker.get_count(key2), 1);
    }

    #[test]
    fn test_usage_concurrent_increments_atomic() {
        let tracker = Arc::new(UsageTracker::new());
        let key = "SISS-Enterprise-cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc-20251225";

        let mut handles = vec![];
        for _ in 0..10 {
            let tracker_clone = Arc::clone(&tracker);
            let key_clone = key.to_string();
            let handle = std::thread::spawn(move || {
                for _ in 0..10 {
                    tracker_clone.record_call(&key_clone, &Sku::Enterprise).ok();
                }
            });
            handles.push(handle);
        }

        for handle in handles {
            handle.join().unwrap();
        }

        assert_eq!(tracker.get_count(key), 100);
    }

    #[test]
    fn test_usage_quota_check_before_increment() {
        let tracker = UsageTracker::new();
        let key = "SISS-Starter-dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd-20251225";

        for i in 0..1000 {
            assert!(tracker.record_call(key, &Sku::Starter).is_ok());
            assert_eq!(tracker.get_count(key), i + 1);
        }
    }

    #[test]
    fn test_usage_quota_exceeded_returns_429() {
        let tracker = UsageTracker::new();
        let key = "SISS-Starter-eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee-20251225";

        for _ in 0..1000 {
            tracker.record_call(key, &Sku::Starter).ok();
        }

        let result = tracker.record_call(key, &Sku::Starter);
        assert!(matches!(result, Err(LicenseError::QuotaExceeded)));
    }

    #[test]
    fn test_usage_quota_reset_daily_midnight() {
        let tracker = UsageTracker::new();
        let key = "SISS-Starter-ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff-20251225";

        for _ in 0..1000 {
            tracker.record_call(key, &Sku::Starter).ok();
        }

        tracker.reset_count(key);
        assert_eq!(tracker.get_count(key), 0);
        assert!(tracker.record_call(key, &Sku::Starter).is_ok());
    }

    #[test]
    fn test_usage_counter_accuracy_100_calls() {
        let tracker = UsageTracker::new();
        let key = "SISS-Pro-0101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101-20251225";

        for i in 0..100 {
            assert!(tracker.record_call(key, &Sku::Pro).is_ok());
            assert_eq!(tracker.get_count(key), i + 1);
        }

        assert_eq!(tracker.get_count(key), 100);
    }

    #[test]
    fn test_usage_enterprise_unlimited() {
        let tracker = UsageTracker::new();
        let key = "SISS-Enterprise-1111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111-20251225";

        for _ in 0..10000 {
            assert!(tracker.record_call(key, &Sku::Enterprise).is_ok());
        }
    }

    #[test]
    fn test_usage_pro_quota_100k() {
        let tracker = UsageTracker::new();
        let key = "SISS-Pro-2222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222-20251225";

        for _ in 0..100_000 {
            assert!(tracker.record_call(key, &Sku::Pro).is_ok());
        }

        let result = tracker.record_call(key, &Sku::Pro);
        assert!(matches!(result, Err(LicenseError::QuotaExceeded)));
    }

    #[test]
    fn test_usage_untracked_key_starts_at_zero() {
        let tracker = UsageTracker::new();
        let key = "SISS-Pro-3333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333-20251225";

        assert_eq!(tracker.get_count(key), 0);
    }

    #[test]
    fn test_usage_different_skus_different_limits() {
        let tracker = UsageTracker::new();
        let starter_key = "SISS-Starter-4444444444444444444444444444444444444444444444444444444444444444444444444444444444444444444444444444444444444444444444444444-20251225";
        let pro_key = "SISS-Pro-5555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555-20251225";

        for _ in 0..1000 {
            tracker.record_call(starter_key, &Sku::Starter).ok();
            tracker.record_call(pro_key, &Sku::Pro).ok();
        }

        assert!(tracker.record_call(starter_key, &Sku::Starter).is_err());
        assert!(tracker.record_call(pro_key, &Sku::Pro).is_ok());
    }
}
