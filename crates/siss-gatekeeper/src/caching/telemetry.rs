//! T4 Extension: Cache telemetry and metrics collection.
//!
//! Tracks:
//! - Hit rate (% of lookups that hit cache)
//! - Eviction rate (% of entries evicted due to TTL or LRU)
//! - Memory usage (estimated from entry count and size)
//! - Token savings (estimated from cache hits)

use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;

/// Cache telemetry snapshot.
#[derive(Debug, Clone)]
pub struct CacheTelemetry {
    pub hits: u64,
    pub total_lookups: u64,
    pub entries_evicted: u64,
    pub entries_current: usize,
    pub estimated_memory_bytes: usize,
}

impl CacheTelemetry {
    /// Hit rate as a percentage (0.0-100.0).
    pub fn hit_rate_pct(&self) -> f64 {
        if self.total_lookups == 0 {
            return 0.0;
        }
        (self.hits as f64 / self.total_lookups as f64) * 100.0
    }

    /// Estimated token savings from cache hits (assuming 256 tokens per hit).
    pub fn estimated_token_savings(&self) -> u64 {
        self.hits * 256
    }
}

/// Cache telemetry collector (thread-safe).
#[derive(Clone, Debug)]
pub struct CacheTelemetryCollector {
    hits: Arc<AtomicU64>,
    total_lookups: Arc<AtomicU64>,
    evictions: Arc<AtomicU64>,
}

impl CacheTelemetryCollector {
    pub fn new() -> Self {
        Self {
            hits: Arc::new(AtomicU64::new(0)),
            total_lookups: Arc::new(AtomicU64::new(0)),
            evictions: Arc::new(AtomicU64::new(0)),
        }
    }

    pub fn record_hit(&self) {
        self.hits.fetch_add(1, Ordering::Relaxed);
        self.total_lookups.fetch_add(1, Ordering::Relaxed);
    }

    pub fn record_miss(&self) {
        self.total_lookups.fetch_add(1, Ordering::Relaxed);
    }

    pub fn record_eviction(&self) {
        self.evictions.fetch_add(1, Ordering::Relaxed);
    }

    pub fn snapshot(&self, current_entries: usize) -> CacheTelemetry {
        let estimated_memory = current_entries * 256; // Rough estimate

        CacheTelemetry {
            hits: self.hits.load(Ordering::Relaxed),
            total_lookups: self.total_lookups.load(Ordering::Relaxed),
            entries_evicted: self.evictions.load(Ordering::Relaxed),
            entries_current: current_entries,
            estimated_memory_bytes: estimated_memory,
        }
    }

    pub fn reset(&self) {
        self.hits.store(0, Ordering::Relaxed);
        self.total_lookups.store(0, Ordering::Relaxed);
        self.evictions.store(0, Ordering::Relaxed);
    }
}

impl Default for CacheTelemetryCollector {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_telemetry_hit_rate_calculation() {
        let collector = CacheTelemetryCollector::new();
        for _ in 0..8 {
            collector.record_hit();
        }
        for _ in 0..2 {
            collector.record_miss();
        }

        let telemetry = collector.snapshot(10);
        assert_eq!(telemetry.hit_rate_pct(), 80.0);
    }

    #[test]
    fn test_telemetry_zero_lookups() {
        let collector = CacheTelemetryCollector::new();
        let telemetry = collector.snapshot(0);
        assert_eq!(telemetry.hit_rate_pct(), 0.0);
    }

    #[test]
    fn test_token_savings_estimate() {
        let collector = CacheTelemetryCollector::new();
        for _ in 0..10 {
            collector.record_hit();
        }

        let telemetry = collector.snapshot(5);
        assert_eq!(telemetry.estimated_token_savings(), 10 * 256);
    }

    #[test]
    fn test_eviction_tracking() {
        let collector = CacheTelemetryCollector::new();
        for _ in 0..5 {
            collector.record_eviction();
        }

        let telemetry = collector.snapshot(10);
        assert_eq!(telemetry.entries_evicted, 5);
    }

    #[test]
    fn test_memory_estimate() {
        let collector = CacheTelemetryCollector::new();
        let telemetry = collector.snapshot(100);
        assert_eq!(telemetry.estimated_memory_bytes, 100 * 256);
    }

    #[test]
    fn test_telemetry_reset() {
        let collector = CacheTelemetryCollector::new();
        collector.record_hit();
        collector.record_hit();
        collector.record_miss();

        collector.reset();

        let telemetry = collector.snapshot(0);
        assert_eq!(telemetry.hits, 0);
        assert_eq!(telemetry.total_lookups, 0);
    }
}
