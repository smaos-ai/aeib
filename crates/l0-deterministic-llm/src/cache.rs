use crate::types::CachedInferenceResponse;
use dashmap::DashMap;
use std::sync::Arc;
use chrono::{DateTime, Utc};

/// Prompt cache with SHA256 fingerprinting and LRU eviction
pub struct PromptCache {
    cache: Arc<DashMap<String, CacheEntry>>,
    max_size: usize,
    ttl_hours: i64,
}

struct CacheEntry {
    response: CachedInferenceResponse,
    last_accessed: DateTime<Utc>,
}

impl PromptCache {
    pub fn new(max_size: usize, ttl_hours: i64) -> Self {
        Self {
            cache: Arc::new(DashMap::new()),
            max_size,
            ttl_hours,
        }
    }

    /// Get cached response by fingerprint
    pub fn get(&self, fingerprint: &str) -> Option<CachedInferenceResponse> {
        if let Some(mut entry) = self.cache.get_mut(fingerprint) {
            let stale = (Utc::now() - entry.value().last_accessed).num_hours() > self.ttl_hours;
            if !stale {
                entry.value_mut().last_accessed = Utc::now();
                return Some(entry.value().response.clone());
            } else {
                drop(entry);
                self.cache.remove(fingerprint);
            }
        }
        None
    }

    /// Set cache entry
    pub fn set(&self, fingerprint: String, response: CachedInferenceResponse) -> Result<(), String> {
        if self.cache.len() >= self.max_size {
            self.evict_lru()?;
        }
        self.cache.insert(
            fingerprint,
            CacheEntry {
                response,
                last_accessed: Utc::now(),
            },
        );
        Ok(())
    }

    /// Evict least recently used entry
    fn evict_lru(&self) -> Result<(), String> {
        let mut oldest_fp: Option<String> = None;
        let mut oldest_time = Utc::now();

        for entry in self.cache.iter() {
            if entry.value().last_accessed < oldest_time {
                oldest_time = entry.value().last_accessed;
                oldest_fp = Some(entry.key().clone());
            }
        }

        if let Some(fp) = oldest_fp {
            self.cache.remove(&fp);
            Ok(())
        } else {
            Err("No entries to evict".to_string())
        }
    }

    /// Clear all cache
    pub fn clear(&self) {
        self.cache.clear();
    }

    /// Get cache size
    pub fn size(&self) -> usize {
        self.cache.len()
    }

    /// Get cache hit rate (target: 80%)
    pub fn hit_rate(&self, total_requests: usize) -> f64 {
        if total_requests == 0 {
            return 0.0;
        }
        let hits: usize = self.cache.iter().filter(|e| e.value().response.cache_hit).count();
        (hits as f64 / total_requests as f64) * 100.0
    }
}

impl Default for PromptCache {
    fn default() -> Self {
        Self::new(1000, 24) // 1000 entries, 24-hour TTL
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cache_set_and_get() {
        let cache = PromptCache::new(100, 24);
        let response = CachedInferenceResponse::new(
            "test output".to_string(),
            10,
            5,
            "test_fp".to_string(),
            false,
        );

        cache.set("test_fp".to_string(), response.clone()).unwrap();
        let retrieved = cache.get("test_fp");

        assert!(retrieved.is_some());
        assert_eq!(retrieved.unwrap().output, "test output");
    }

    #[test]
    fn test_cache_miss() {
        let cache = PromptCache::new(100, 24);
        let result = cache.get("nonexistent");
        assert!(result.is_none());
    }

    #[test]
    fn test_cache_lru_eviction() {
        let cache = PromptCache::new(2, 24);

        let resp1 = CachedInferenceResponse::new("output1".to_string(), 10, 5, "fp1".to_string(), false);
        let resp2 = CachedInferenceResponse::new("output2".to_string(), 10, 5, "fp2".to_string(), false);
        let resp3 = CachedInferenceResponse::new("output3".to_string(), 10, 5, "fp3".to_string(), false);

        cache.set("fp1".to_string(), resp1).unwrap();
        cache.set("fp2".to_string(), resp2).unwrap();
        // This should trigger eviction of fp1
        cache.set("fp3".to_string(), resp3).unwrap();

        assert_eq!(cache.size(), 2);
        assert!(cache.get("fp1").is_none()); // Should be evicted
        assert!(cache.get("fp2").is_some()); // Should still exist
        assert!(cache.get("fp3").is_some()); // Should exist
    }

    #[test]
    fn test_cache_ttl_expiration() {
        let cache = PromptCache::new(100, -1); // Negative TTL = immediate expiration
        let response = CachedInferenceResponse::new(
            "test output".to_string(),
            10,
            5,
            "test_fp".to_string(),
            false,
        );

        cache.set("test_fp".to_string(), response).unwrap();
        // TTL expired, should return None
        let retrieved = cache.get("test_fp");
        assert!(retrieved.is_none());
    }

    #[test]
    fn test_cache_clear() {
        let cache = PromptCache::new(100, 24);
        let response = CachedInferenceResponse::new(
            "test output".to_string(),
            10,
            5,
            "test_fp".to_string(),
            false,
        );

        cache.set("test_fp".to_string(), response).unwrap();
        assert_eq!(cache.size(), 1);

        cache.clear();
        assert_eq!(cache.size(), 0);
    }
}
