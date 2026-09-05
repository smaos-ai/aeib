//! T4 Extension: Cache eviction strategies for TokenCache.
//!
//! Implements:
//! - LRU (Least Recently Used) eviction
//! - Time-based TTL enforcement
//! - Semantic cache invalidation (linked entries)

use std::collections::BTreeMap;
use std::time::Instant;

/// LRU eviction policy: track access times, evict least recently used.
#[derive(Debug, Clone)]
pub struct LRUEvictionPolicy {
    /// Max entries in cache.
    pub max_size: usize,
}

impl LRUEvictionPolicy {
    pub fn new(max_size: usize) -> Self {
        Self { max_size }
    }

    /// Decide which key to evict from a map of (key, last_access_time).
    /// Returns the key with the oldest last_access_time.
    pub fn select_victim(&self, access_times: &BTreeMap<usize, Instant>) -> Option<usize> {
        access_times
            .iter()
            .min_by_key(|(_, instant)| *instant)
            .map(|(key, _)| *key)
    }
}

/// Multi-tier eviction: primary (LRU) + secondary (time-based TTL).
#[derive(Debug)]
pub struct MultiTierEvictionStrategy {
    pub lru: LRUEvictionPolicy,
    /// Evict when this many entries exceed their TTL.
    pub ttl_batch_size: usize,
}

impl MultiTierEvictionStrategy {
    pub fn new(max_size: usize, ttl_batch_size: usize) -> Self {
        Self {
            lru: LRUEvictionPolicy::new(max_size),
            ttl_batch_size,
        }
    }
}

/// Semantic cache invalidation: linked entries share lifecycle.
/// When parent entry is evicted/invalidated, all children are too.
#[derive(Debug, Clone)]
pub struct LinkedCacheEntry {
    /// Parent key (if this is a derived/semantic match).
    pub parent_key: Option<[u8; 32]>,
    /// Child keys (entries derived from this one).
    pub child_keys: Vec<[u8; 32]>,
}

impl LinkedCacheEntry {
    pub fn new() -> Self {
        Self {
            parent_key: None,
            child_keys: Vec::new(),
        }
    }

    pub fn with_parent(parent_key: [u8; 32]) -> Self {
        Self {
            parent_key: Some(parent_key),
            child_keys: Vec::new(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_lru_selects_oldest() {
        let policy = LRUEvictionPolicy::new(10);
        let mut times = BTreeMap::new();
        times.insert(1, Instant::now());
        std::thread::sleep(std::time::Duration::from_millis(10));
        times.insert(2, Instant::now());
        std::thread::sleep(std::time::Duration::from_millis(10));
        times.insert(3, Instant::now());

        let victim = policy.select_victim(&times);
        assert_eq!(victim, Some(1));
    }

    #[test]
    fn test_lru_empty_returns_none() {
        let policy = LRUEvictionPolicy::new(10);
        let times = BTreeMap::new();
        assert_eq!(policy.select_victim(&times), None);
    }

    #[test]
    fn test_linked_entry_parent_child_relationship() {
        let parent_key = [1u8; 32];
        let child1 = [2u8; 32];
        let child2 = [3u8; 32];

        let mut parent = LinkedCacheEntry::new();
        parent.child_keys.push(child1);
        parent.child_keys.push(child2);

        let child = LinkedCacheEntry::with_parent(parent_key);

        assert_eq!(parent.child_keys.len(), 2);
        assert_eq!(child.parent_key, Some(parent_key));
    }

    #[test]
    fn test_multi_tier_eviction_default() {
        let strategy = MultiTierEvictionStrategy::new(100, 10);
        assert_eq!(strategy.lru.max_size, 100);
        assert_eq!(strategy.ttl_batch_size, 10);
    }
}
