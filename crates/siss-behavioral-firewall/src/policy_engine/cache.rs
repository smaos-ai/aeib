//! Decision Cache with TTL and Invalidation
//!
//! Implements caching for mandate decisions with per-sovereign invalidation.

use dashmap::DashMap;
use std::sync::Arc;
use std::time::{SystemTime, Duration};
use uuid::Uuid;

use super::mandate_verifier::Mandate;

/// Decision cache with 1-minute TTL and atomic per-sovereign invalidation.
pub struct MandateCache {
    cache: Arc<DashMap<String, CachedMandate>>,
    ttl: Duration,
}

#[derive(Clone)]
struct CachedMandate {
    mandate: Mandate,
    cached_at: SystemTime,
}

impl MandateCache {
    pub fn new(ttl: Duration) -> Self {
        Self {
            cache: Arc::new(DashMap::new()),
            ttl,
        }
    }

    /// Generate a cache key from requester UUID, action, and resource.
    pub fn cache_key(requester: Uuid, action: &str, resource: &str) -> String {
        format!("{}:{}:{}", requester, action, resource)
    }

    /// Store a mandate in the cache.
    pub fn put(&self, key: String, mandate: Mandate) {
        self.cache.insert(
            key,
            CachedMandate {
                mandate,
                cached_at: SystemTime::now(),
            },
        );
    }

    /// Retrieve a cached mandate if it's within TTL.
    pub fn get(&self, key: &str) -> Option<Mandate> {
        let entry = self.cache.get(key)?;
        let age = SystemTime::now()
            .duration_since(entry.cached_at)
            .unwrap_or(Duration::from_secs(0));

        if age < self.ttl {
            Some(entry.mandate.clone())
        } else {
            drop(entry);
            self.cache.remove(key);
            None
        }
    }

    /// Invalidate all cache entries for a sovereign.
    pub fn invalidate_sovereign(&self, sovereign_uuid: Uuid) {
        let prefix = format!("{}:", sovereign_uuid);
        self.cache.retain(|k, _| !k.starts_with(&prefix));
    }

    /// Invalidate all entries (for testing/admin).
    pub fn invalidate_all(&self) {
        self.cache.clear();
    }

    /// Return the number of cached entries (including stale).
    pub fn len(&self) -> usize {
        self.cache.len()
    }

    pub fn is_empty(&self) -> bool {
        self.cache.is_empty()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn placeholder_test() {
        // Real tests in integration test file
    }
}
