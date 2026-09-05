use anyhow::{Result, anyhow};
use chrono::{DateTime, Utc};
use dashmap::DashMap;
use redis::aio::ConnectionManager;
use std::sync::Arc;
use uuid::Uuid;

/// In-process cache for comparison operations
pub struct LocalCache {
    shas: Arc<DashMap<String, CacheEntry>>,
}

#[derive(Debug, Clone)]
struct CacheEntry {
    sha: String,
    #[allow(dead_code)]
    timestamp: DateTime<Utc>,
}

/// Redis-backed persistent cache
pub struct RedisCache {
    conn: ConnectionManager,
    ttl_seconds: usize,
}

/// Combined cache layer (hot + warm)
pub struct CacheLayer {
    local: LocalCache,
    redis: Option<RedisCache>,
}

impl LocalCache {
    pub fn new() -> Self {
        Self {
            shas: Arc::new(DashMap::new()),
        }
    }

    /// Store SHA in local cache
    pub fn set(&self, repo_id: &Uuid, sha: String) {
        self.shas.insert(
            repo_id.to_string(),
            CacheEntry {
                sha,
                timestamp: Utc::now(),
            },
        );
    }

    /// Get SHA from local cache
    pub fn get(&self, repo_id: &Uuid) -> Option<String> {
        self.shas
            .get(&repo_id.to_string())
            .map(|entry| entry.sha.clone())
    }

    /// Check if entry exists
    pub fn contains_key(&self, repo_id: &Uuid) -> bool {
        self.shas.contains_key(&repo_id.to_string())
    }

    /// Get cache size
    pub fn len(&self) -> usize {
        self.shas.len()
    }

    /// Check if cache is empty
    pub fn is_empty(&self) -> bool {
        self.shas.is_empty()
    }

    /// Clear cache
    pub fn clear(&self) {
        self.shas.clear();
    }
}

impl Default for LocalCache {
    fn default() -> Self {
        Self::new()
    }
}

impl RedisCache {
    /// Connect to Redis
    pub async fn new(redis_url: &str, ttl_seconds: usize) -> Result<Self> {
        let client = redis::Client::open(redis_url)?;
        let conn = ConnectionManager::new(client).await?;

        Ok(Self { conn, ttl_seconds })
    }

    /// Set SHA with TTL
    pub async fn set(&mut self, repo_id: &Uuid, sha: &str) -> Result<()> {
        let key = format!("radar:repo:{}:sha", repo_id);
        let _: () = redis::cmd("SET")
            .arg(&key)
            .arg(sha)
            .arg("EX")
            .arg(self.ttl_seconds)
            .query_async(&mut self.conn)
            .await?;

        let ts_key = format!("radar:repo:{}:ts", repo_id);
        let _: () = redis::cmd("SET")
            .arg(&ts_key)
            .arg(Utc::now().timestamp())
            .arg("EX")
            .arg(self.ttl_seconds)
            .query_async(&mut self.conn)
            .await?;

        Ok(())
    }

    /// Get SHA from cache
    pub async fn get(&mut self, repo_id: &Uuid) -> Result<Option<String>> {
        let key = format!("radar:repo:{}:sha", repo_id);
        let sha: Option<String> = redis::cmd("GET")
            .arg(&key)
            .query_async(&mut self.conn)
            .await?;

        Ok(sha)
    }

    /// Check cache hit rate (requires Redis stats)
    pub async fn hit_rate(&mut self) -> Result<f64> {
        let info: String = redis::cmd("INFO")
            .arg("stats")
            .query_async(&mut self.conn)
            .await?;

        // Parse "keyspace_hits" and "keyspace_misses"
        let hits = info
            .lines()
            .find(|line| line.contains("keyspace_hits:"))
            .and_then(|line| line.split(':').nth(1))
            .and_then(|s| s.trim().parse::<u64>().ok())
            .unwrap_or(0);

        let misses = info
            .lines()
            .find(|line| line.contains("keyspace_misses:"))
            .and_then(|line| line.split(':').nth(1))
            .and_then(|s| s.trim().parse::<u64>().ok())
            .unwrap_or(0);

        let total = hits + misses;
        Ok(if total == 0 {
            0.0
        } else {
            hits as f64 / total as f64 * 100.0
        })
    }
}

impl CacheLayer {
    pub fn new(local: LocalCache, redis: Option<RedisCache>) -> Self {
        Self { local, redis }
    }

    /// Set SHA across all cache layers
    pub async fn set(&mut self, repo_id: &Uuid, sha: String) -> Result<()> {
        // Always set local
        self.local.set(repo_id, sha.clone());

        // Try Redis if available
        if let Some(redis) = &mut self.redis {
            redis.set(repo_id, &sha).await.ok(); // Ignore Redis failures
        }

        Ok(())
    }

    /// Get SHA with fallback
    pub async fn get(&mut self, repo_id: &Uuid) -> Result<Option<String>> {
        // Try local first
        if let Some(sha) = self.local.get(repo_id) {
            return Ok(Some(sha));
        }

        // Try Redis
        if let Some(redis) = &mut self.redis {
            if let Some(sha) = redis.get(repo_id).await? {
                self.local.set(repo_id, sha.clone()); // Repopulate local
                Ok(Some(sha))
            } else {
                Ok(None)
            }
        } else {
            Ok(None)
        }
    }

    /// Check cache hit rate
    pub async fn hit_rate(&mut self) -> Result<f64> {
        if let Some(redis) = &mut self.redis {
            redis.hit_rate().await
        } else {
            Err(anyhow!("Redis not configured"))
        }
    }

    /// Check local cache size
    pub fn local_cache_size(&self) -> usize {
        self.local.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_local_cache_operations() {
        let cache = LocalCache::new();
        let repo_id = Uuid::new_v4();
        let sha = "abc123def456".to_string();

        // Set and retrieve
        cache.set(&repo_id, sha.clone());
        assert_eq!(cache.get(&repo_id), Some(sha));

        // Check containment
        assert!(cache.contains_key(&repo_id));

        // Non-existent key
        let other_id = Uuid::new_v4();
        assert!(!cache.contains_key(&other_id));
    }

    #[test]
    fn test_local_cache_clear() {
        let cache = LocalCache::new();
        let repo_id = Uuid::new_v4();

        cache.set(&repo_id, "sha1".to_string());
        assert_eq!(cache.len(), 1);

        cache.clear();
        assert_eq!(cache.len(), 0);
    }

    #[test]
    fn test_local_cache_multiple_entries() {
        let cache = LocalCache::new();

        for i in 0..100 {
            let repo_id = Uuid::new_v4();
            cache.set(&repo_id, format!("sha_{}", i));
        }

        assert_eq!(cache.len(), 100);
    }

    #[tokio::test]
    async fn test_cache_layer_without_redis() {
        let local = LocalCache::new();
        let mut layer = CacheLayer::new(local, None);
        let repo_id = Uuid::new_v4();
        let sha = "test_sha".to_string();

        layer.set(&repo_id, sha.clone()).await.unwrap();
        let retrieved = layer.get(&repo_id).await.unwrap();

        assert_eq!(retrieved, Some(sha));
    }
}
