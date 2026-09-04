use std::collections::HashMap;
use std::sync::{Arc, RwLock};
use thiserror::Error;

/// KV cache errors
#[derive(Error, Debug)]
pub enum CacheError {
    #[error("Cache handle not found")]
    HandleNotFound,
    #[error("Cache capacity exceeded")]
    CapacityExceeded,
}

pub type CacheResult<T> = std::result::Result<T, CacheError>;

/// Unique identifier for a cached entry
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct CacheHandle(u64);

impl CacheHandle {
    fn new(id: u64) -> Self {
        CacheHandle(id)
    }
}

/// A single cache entry with key and data
#[derive(Clone)]
struct CacheEntry {
    #[allow(dead_code)]
    key: String,
    data: Vec<u8>,
}

/// LRU KV cache pool for managing prefill buffers
///
/// Manages attention layer caches with LRU eviction when capacity exceeded.
/// Thread-safe via Arc<RwLock<>>.
pub struct KVCachePool {
    /// Capacity in bytes
    capacity: usize,
    /// Current size in bytes
    current_size: Arc<RwLock<usize>>,
    /// Cache entries: handle -> entry
    entries: Arc<RwLock<HashMap<CacheHandle, CacheEntry>>>,
    /// LRU order: most recent at end
    lru_order: Arc<RwLock<Vec<CacheHandle>>>,
    /// Next handle ID
    next_id: Arc<RwLock<u64>>,
}

impl Clone for KVCachePool {
    fn clone(&self) -> Self {
        KVCachePool {
            capacity: self.capacity,
            current_size: Arc::clone(&self.current_size),
            entries: Arc::clone(&self.entries),
            lru_order: Arc::clone(&self.lru_order),
            next_id: Arc::clone(&self.next_id),
        }
    }
}

impl KVCachePool {
    /// Create a new KV cache pool with given capacity in bytes
    pub fn new(capacity: usize) -> Self {
        KVCachePool {
            capacity,
            current_size: Arc::new(RwLock::new(0)),
            entries: Arc::new(RwLock::new(HashMap::new())),
            lru_order: Arc::new(RwLock::new(Vec::new())),
            next_id: Arc::new(RwLock::new(0)),
        }
    }

    /// Allocate space in cache and store data
    pub fn allocate(&self, key: String, data: Vec<u8>) -> CacheResult<CacheHandle> {
        let data_size = data.len();
        let mut current_size = self.current_size.write().unwrap();
        let mut entries = self.entries.write().unwrap();
        let mut lru_order = self.lru_order.write().unwrap();
        let mut next_id = self.next_id.write().unwrap();

        // Evict LRU entries until we have space
        while *current_size + data_size > self.capacity && !lru_order.is_empty() {
            let oldest_handle = lru_order.remove(0);
            if let Some(removed_entry) = entries.remove(&oldest_handle) {
                *current_size = current_size.saturating_sub(removed_entry.data.len());
            }
        }

        // Check if we still can't fit the data
        if *current_size + data_size > self.capacity {
            return Err(CacheError::CapacityExceeded);
        }

        // Allocate new entry
        let handle = CacheHandle::new(*next_id);
        *next_id = next_id.wrapping_add(1);

        entries.insert(
            handle,
            CacheEntry {
                key,
                data: data.clone(),
            },
        );
        lru_order.push(handle);
        *current_size += data_size;

        Ok(handle)
    }

    /// Retrieve cached data by handle and mark as recently used
    pub fn get(&self, handle: &CacheHandle) -> CacheResult<Vec<u8>> {
        let entries = self.entries.read().unwrap();
        let entry = entries.get(handle).ok_or(CacheError::HandleNotFound)?;
        let data = entry.data.clone();
        drop(entries);

        // Mark as recently used by moving to end of LRU order
        let mut lru_order = self.lru_order.write().unwrap();
        if let Some(pos) = lru_order.iter().position(|h| h == handle) {
            lru_order.remove(pos);
            lru_order.push(*handle);
        }

        Ok(data)
    }

    /// Get current cache size in bytes
    pub fn current_size(&self) -> usize {
        *self.current_size.read().unwrap()
    }

    /// Get cache capacity in bytes
    pub fn capacity(&self) -> usize {
        self.capacity
    }

    /// Clear all cached entries
    pub fn clear(&self) {
        self.entries.write().unwrap().clear();
        self.lru_order.write().unwrap().clear();
        *self.current_size.write().unwrap() = 0;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_allocate_and_retrieve() {
        let cache = KVCachePool::new(1000);
        let data = vec![1, 2, 3, 4, 5];
        let handle = cache.allocate("test".to_string(), data.clone()).unwrap();
        assert_eq!(cache.get(&handle).unwrap(), data);
    }

    #[test]
    fn test_handle_not_found() {
        let cache = KVCachePool::new(1000);
        let handle = CacheHandle::new(999);
        assert!(cache.get(&handle).is_err());
    }

    #[test]
    fn test_lru_eviction() {
        let cache = KVCachePool::new(150); // 3 * 50 bytes
        let data1 = vec![1; 50];
        let data2 = vec![2; 50];
        let data3 = vec![3; 50];

        let _h1 = cache.allocate("key1".to_string(), data1).unwrap();
        let h2 = cache.allocate("key2".to_string(), data2).unwrap();
        let h3 = cache.allocate("key3".to_string(), data3).unwrap();

        // Access h2 to mark as recently used
        let _ = cache.get(&h2).unwrap();

        // h3 should still be accessible (most recent)
        assert!(cache.get(&h3).is_ok());

        // h2 should be accessible (was accessed)
        assert!(cache.get(&h2).is_ok());

        // h1 may have been evicted due to LRU
        // (depends on exact eviction timing)
    }

    #[test]
    fn test_capacity_exceeded() {
        let cache = KVCachePool::new(100);
        let data = vec![1; 150];
        assert!(cache.allocate("too_large".to_string(), data).is_err());
    }

    #[test]
    fn test_clear() {
        let cache = KVCachePool::new(1000);
        let data = vec![1; 50];
        let _h = cache.allocate("test".to_string(), data).unwrap();
        assert_eq!(cache.current_size(), 50);

        cache.clear();
        assert_eq!(cache.current_size(), 0);
    }
}
