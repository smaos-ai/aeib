// Content-addressed cache store with LRU eviction
// In-memory cache backed by optional disk storage

use crate::content_hash::ContentHasher;
use chrono::{DateTime, Utc};
use dashmap::DashMap;
use std::path::PathBuf;
use std::sync::Arc;
use thiserror::Error;

/// Cache key combining artifact ID and content hash
#[derive(Clone, Debug, Eq, PartialEq, serde::Serialize, serde::Deserialize)]
pub struct CacheKey {
    pub artifact_id: String,
    pub content_hash: String,
    pub timestamp: u64,
}

impl CacheKey {
    pub fn new(artifact_id: String, content_hash: String) -> Self {
        CacheKey {
            artifact_id,
            content_hash,
            timestamp: Utc::now().timestamp() as u64,
        }
    }
}

/// Cached artifact with metadata
#[derive(Clone, Debug)]
pub struct CachedArtifact {
    pub key: CacheKey,
    pub data: Vec<u8>,
    pub created_at: DateTime<Utc>,
    pub accessed_at: DateTime<Utc>,
    pub size_bytes: u64,
}

#[derive(Error, Debug)]
pub enum CacheError {
    #[error("Cache miss for key {0}")]
    CacheMiss(String),
    #[error("Cache full: {0}")]
    CacheFull(String),
    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),
    #[error("Serialization error: {0}")]
    SerializationError(#[from] serde_json::error::Error),
    #[error("Hash mismatch for key {0}")]
    HashMismatch(String),
}

type Result<T> = std::result::Result<T, CacheError>;

/// Content-addressed cache store with LRU eviction
pub struct CacheStore {
    memory: Arc<DashMap<String, CachedArtifact>>,
    #[allow(dead_code)]
    disk_path: PathBuf,
    max_size: u64, // Default 10GB
    current_size: Arc<std::sync::Mutex<u64>>,
}

impl CacheStore {
    /// Create new cache store
    pub fn new(disk_path: PathBuf) -> Self {
        Self::with_max_size(disk_path, 10 * 1024 * 1024 * 1024) // 10GB default
    }

    /// Create cache store with custom max size
    pub fn with_max_size(disk_path: PathBuf, max_size: u64) -> Self {
        CacheStore {
            memory: Arc::new(DashMap::new()),
            disk_path,
            max_size,
            current_size: Arc::new(std::sync::Mutex::new(0)),
        }
    }

    /// Get cache key as string
    fn key_string(artifact_id: &str, content_hash: &str) -> String {
        format!("{}:{}", artifact_id, content_hash)
    }

    /// Retrieve artifact from cache
    pub fn get(&self, key: &CacheKey) -> Result<Vec<u8>> {
        let key_str = Self::key_string(&key.artifact_id, &key.content_hash);

        if let Some(mut artifact) = self.memory.get_mut(&key_str) {
            // Update access time (LRU tracking)
            artifact.accessed_at = Utc::now();
            return Ok(artifact.data.clone());
        }

        Err(CacheError::CacheMiss(key_str))
    }

    /// Store artifact in cache
    pub fn put(&self, key: CacheKey, artifact: Vec<u8>) -> Result<()> {
        // Verify hash matches data
        let computed_hash = ContentHasher::hash(&artifact);
        if computed_hash.hex != key.content_hash {
            return Err(CacheError::HashMismatch(format!(
                "Expected {}, got {}",
                key.content_hash, computed_hash.hex
            )));
        }

        let size = artifact.len() as u64;
        let key_str = Self::key_string(&key.artifact_id, &key.content_hash);

        let cached = CachedArtifact {
            key,
            data: artifact,
            created_at: Utc::now(),
            accessed_at: Utc::now(),
            size_bytes: size,
        };

        // Check if we need to evict
        let mut current_size = self.current_size.lock().unwrap();
        if *current_size + size > self.max_size {
            drop(current_size); // Release lock before eviction
            self.evict_lru()?;
            current_size = self.current_size.lock().unwrap();
        }

        self.memory.insert(key_str, cached);
        *current_size += size;

        Ok(())
    }

    /// Evict least recently used items until size permits new artifact
    pub fn evict_lru(&self) -> Result<()> {
        if self.memory.is_empty() {
            return Err(CacheError::CacheFull(
                "Cannot evict: cache is empty".to_string(),
            ));
        }

        // Find LRU item (oldest accessed_at)
        let mut oldest_key = None;
        let mut oldest_time = Utc::now();

        for entry in self.memory.iter() {
            if entry.accessed_at < oldest_time {
                oldest_time = entry.accessed_at;
                oldest_key = Some(entry.key().clone());
            }
        }

        if let Some(key) = oldest_key {
            if let Some((_, artifact)) = self.memory.remove(&key) {
                let mut current_size = self.current_size.lock().unwrap();
                *current_size = current_size.saturating_sub(artifact.size_bytes);
            }
        }

        Ok(())
    }

    /// Get current cache size in bytes
    pub fn current_size(&self) -> u64 {
        *self.current_size.lock().unwrap()
    }

    /// Get number of cached artifacts
    pub fn artifact_count(&self) -> usize {
        self.memory.len()
    }

    /// Clear entire cache
    pub fn clear(&self) -> Result<()> {
        self.memory.clear();
        *self.current_size.lock().unwrap() = 0;
        Ok(())
    }

    /// Check if key exists in cache
    pub fn contains(&self, key: &CacheKey) -> bool {
        let key_str = Self::key_string(&key.artifact_id, &key.content_hash);
        self.memory.contains_key(&key_str)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    fn create_test_cache() -> CacheStore {
        CacheStore::with_max_size(PathBuf::from("/tmp/test_cache"), 1024 * 1024) // 1MB for testing
    }

    #[test]
    fn test_cache_store_put_get() {
        let cache = create_test_cache();
        let data = b"test artifact data";
        let hash = ContentHasher::hash(data);
        let key = CacheKey::new("test-artifact".to_string(), hash.hex.clone());

        // Put and get
        assert!(cache.put(key.clone(), data.to_vec()).is_ok());
        let retrieved = cache.get(&key).unwrap();
        assert_eq!(retrieved, data);
    }

    #[test]
    fn test_cache_store_cache_miss() {
        let cache = create_test_cache();
        let key = CacheKey::new("nonexistent".to_string(), "abc123".to_string());
        assert!(cache.get(&key).is_err());
    }

    #[test]
    fn test_cache_store_multiple_artifacts() {
        let cache = create_test_cache();

        let data1 = b"artifact 1";
        let hash1 = ContentHasher::hash(data1);
        let key1 = CacheKey::new("artifact1".to_string(), hash1.hex.clone());

        let data2 = b"artifact 2";
        let hash2 = ContentHasher::hash(data2);
        let key2 = CacheKey::new("artifact2".to_string(), hash2.hex.clone());

        cache.put(key1.clone(), data1.to_vec()).unwrap();
        cache.put(key2.clone(), data2.to_vec()).unwrap();

        assert_eq!(cache.artifact_count(), 2);
        assert_eq!(cache.get(&key1).unwrap(), data1);
        assert_eq!(cache.get(&key2).unwrap(), data2);
    }

    #[test]
    fn test_cache_store_lru_eviction() {
        let cache = CacheStore::with_max_size(PathBuf::from("/tmp/test_lru"), 100); // 100 bytes

        let data1 = b"data1"; // 5 bytes
        let hash1 = ContentHasher::hash(data1);
        let key1 = CacheKey::new("artifact1".to_string(), hash1.hex.clone());

        let data2 = b"data2data2data2"; // 15 bytes
        let hash2 = ContentHasher::hash(data2);
        let key2 = CacheKey::new("artifact2".to_string(), hash2.hex.clone());

        // Put first artifact
        cache.put(key1.clone(), data1.to_vec()).unwrap();
        assert_eq!(cache.artifact_count(), 1);

        // Put second artifact
        cache.put(key2.clone(), data2.to_vec()).unwrap();
        assert_eq!(cache.artifact_count(), 2);

        // Add large artifact that triggers eviction
        let large_data = vec![0u8; 90]; // 90 bytes
        let large_hash = ContentHasher::hash(&large_data);
        let large_key = CacheKey::new("large".to_string(), large_hash.hex.clone());
        cache.put(large_key.clone(), large_data).unwrap();

        // LRU item (key1) should be evicted
        assert!(!cache.contains(&key1));
        assert!(cache.contains(&key2));
        assert!(cache.contains(&large_key));
    }

    #[test]
    fn test_cache_store_hash_mismatch() {
        let cache = create_test_cache();
        let data = b"test data";
        let wrong_hash = "0".repeat(64); // Invalid hash
        let key = CacheKey::new("test".to_string(), wrong_hash);

        let result = cache.put(key, data.to_vec());
        assert!(result.is_err());
        assert!(matches!(result, Err(CacheError::HashMismatch(_))));
    }

    #[test]
    fn test_cache_store_clear() {
        let cache = create_test_cache();
        let data = b"test";
        let hash = ContentHasher::hash(data);
        let key = CacheKey::new("test".to_string(), hash.hex.clone());

        cache.put(key, data.to_vec()).unwrap();
        assert_eq!(cache.artifact_count(), 1);

        cache.clear().unwrap();
        assert_eq!(cache.artifact_count(), 0);
        assert_eq!(cache.current_size(), 0);
    }

    #[test]
    fn test_cache_store_contains() {
        let cache = create_test_cache();
        let data = b"test";
        let hash = ContentHasher::hash(data);
        let key = CacheKey::new("test".to_string(), hash.hex.clone());

        assert!(!cache.contains(&key));
        cache.put(key.clone(), data.to_vec()).unwrap();
        assert!(cache.contains(&key));
    }

    #[test]
    fn test_cache_store_size_tracking() {
        let cache = create_test_cache();
        let data1 = b"small";
        let hash1 = ContentHasher::hash(data1);
        let key1 = CacheKey::new("s1".to_string(), hash1.hex.clone());

        let data2 = b"medium data here";
        let hash2 = ContentHasher::hash(data2);
        let key2 = CacheKey::new("s2".to_string(), hash2.hex.clone());

        assert_eq!(cache.current_size(), 0);
        cache.put(key1, data1.to_vec()).unwrap();
        assert_eq!(cache.current_size(), data1.len() as u64);
        let size_after_first = cache.current_size();
        cache.put(key2, data2.to_vec()).unwrap();
        let size_after_second = cache.current_size();
        assert_eq!(size_after_second, size_after_first + data2.len() as u64);
    }

    #[test]
    fn test_cache_store_lru_updates_on_access() {
        let cache = CacheStore::with_max_size(PathBuf::from("/tmp/test_lru_access"), 100);

        let data1 = b"d1";
        let hash1 = ContentHasher::hash(data1);
        let key1 = CacheKey::new("artifact1".to_string(), hash1.hex.clone());

        let data2 = b"d2";
        let hash2 = ContentHasher::hash(data2);
        let key2 = CacheKey::new("artifact2".to_string(), hash2.hex.clone());

        cache.put(key1.clone(), data1.to_vec()).unwrap();
        std::thread::sleep(std::time::Duration::from_millis(100)); // Longer sleep for clearer time separation
        cache.put(key2.clone(), data2.to_vec()).unwrap();

        // Access key1 to update its access time (must be after key2)
        std::thread::sleep(std::time::Duration::from_millis(100));
        let _ = cache.get(&key1);

        // Add large artifact - should evict key2 (least recently used now)
        let large_data = vec![0u8; 90];
        let large_hash = ContentHasher::hash(&large_data);
        let large_key = CacheKey::new("large".to_string(), large_hash.hex.clone());
        cache.put(large_key, large_data).unwrap();

        assert!(cache.contains(&key1)); // key1 still there (recently accessed)
        assert!(!cache.contains(&key2)); // key2 evicted (oldest access time)
    }

    #[test]
    fn test_cache_store_key_string_format() {
        let key_str = CacheStore::key_string("my-artifact", "abc123");
        assert_eq!(key_str, "my-artifact:abc123");
    }

    #[test]
    fn test_cache_store_empty_evict_error() {
        let cache = create_test_cache();
        // Try evicting from empty cache
        let result = cache.evict_lru();
        assert!(result.is_err());
    }

    #[test]
    fn test_cache_store_artifact_count() {
        let cache = create_test_cache();
        assert_eq!(cache.artifact_count(), 0);

        let data = b"test";
        let hash = ContentHasher::hash(data);
        let key = CacheKey::new("test".to_string(), hash.hex.clone());
        cache.put(key, data.to_vec()).unwrap();
        assert_eq!(cache.artifact_count(), 1);
    }

    #[test]
    fn test_cache_store_same_artifact_different_hashes() {
        let cache = create_test_cache();
        let data = b"test";

        // Create two keys with different hashes (edge case)
        let key1 = CacheKey::new("artifact".to_string(), "hash1".repeat(16));
        let key2 = CacheKey::new("artifact".to_string(), "hash2".repeat(16));

        // Both put operations should fail due to hash mismatch
        assert!(cache.put(key1, data.to_vec()).is_err());
        assert!(cache.put(key2, data.to_vec()).is_err());
    }
}
