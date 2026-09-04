//! LRU cache for expert model loading and lifecycle management.
//!
//! ExpertCache manages memory-efficient loading of multiple expert models using
//! least-recently-used (LRU) eviction policy. When cache is full, oldest accessed
//! model is evicted to make room for new one.

use std::collections::HashMap;
use std::sync::{Arc, Mutex};

use crate::expert_router::{ExpertDomain, ExpertRouter, ModelId};

/// Mock inference model for testing and simulation.
#[derive(Debug, Clone)]
pub struct MockInferenceModel {
    model_id: ModelId,
}

impl MockInferenceModel {
    /// Create a new mock model with given model ID.
    pub fn new(model_id: ModelId) -> Self {
        Self { model_id }
    }

    /// Get the model ID.
    pub fn id(&self) -> ModelId {
        self.model_id.clone()
    }
}

/// Error type for cache operations.
#[derive(Debug, Clone)]
pub enum ExpertCacheError {
    ModelLoadFailed(String),
}

impl std::fmt::Display for ExpertCacheError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::ModelLoadFailed(msg) => write!(f, "Failed to load model: {}", msg),
        }
    }
}

impl std::error::Error for ExpertCacheError {}

pub type Result<T> = std::result::Result<T, ExpertCacheError>;

/// LRU cache for expert models.
#[derive(Debug)]
pub struct ExpertCache {
    max_experts: usize,
    cache: Arc<Mutex<HashMap<String, MockInferenceModel>>>,
    lru_order: Arc<Mutex<Vec<String>>>,
}

impl ExpertCache {
    /// Create a new expert cache with max capacity.
    pub fn new(max_experts: usize) -> Self {
        Self {
            max_experts,
            cache: Arc::new(Mutex::new(HashMap::new())),
            lru_order: Arc::new(Mutex::new(Vec::new())),
        }
    }

    /// Get or load a model for the given domain.
    /// Uses router to determine model ID, loads if not in cache,
    /// evicts LRU entry if cache is full.
    pub fn get_or_load(
        &self,
        domain: ExpertDomain,
        router: &ExpertRouter,
    ) -> Result<MockInferenceModel> {
        let domain_str = domain.as_str().to_string();

        // Try to get from cache
        {
            let cache = self.cache.lock().unwrap();
            let mut lru = self.lru_order.lock().unwrap();

            if let Some(model) = cache.get(&domain_str) {
                // Update LRU: move to end (most recently used)
                lru.retain(|x| x != &domain_str);
                lru.push(domain_str.clone());
                return Ok(model.clone());
            }
        }

        // Cache miss: load via router
        let model_id = router.route(domain);
        let model = MockInferenceModel::new(model_id);

        // Insert into cache with LRU tracking
        {
            let mut cache = self.cache.lock().unwrap();
            let mut lru = self.lru_order.lock().unwrap();

            // Evict oldest if cache is full
            if cache.len() >= self.max_experts {
                if let Some(oldest) = lru.first().cloned() {
                    cache.remove(&oldest);
                    lru.remove(0);
                }
            }

            cache.insert(domain_str.clone(), model.clone());
            lru.push(domain_str);
        }

        Ok(model)
    }

    /// Route and get cached, without loading if not present.
    /// Returns model if in cache, None otherwise.
    pub fn get_cached(&self, domain: ExpertDomain) -> Option<MockInferenceModel> {
        let domain_str = domain.as_str().to_string();
        let cache = self.cache.lock().unwrap();
        let mut lru = self.lru_order.lock().unwrap();

        if let Some(model) = cache.get(&domain_str) {
            // Update LRU: move to end
            lru.retain(|x| x != &domain_str);
            lru.push(domain_str.clone());
            return Some(model.clone());
        }

        None
    }

    /// Get the number of cached models.
    pub fn cached_count(&self) -> usize {
        self.cache.lock().unwrap().len()
    }

    /// Clear all cached models.
    pub fn clear(&self) {
        self.cache.lock().unwrap().clear();
        self.lru_order.lock().unwrap().clear();
    }

    /// Check if a domain is cached.
    pub fn is_cached(&self, domain: ExpertDomain) -> bool {
        self.cache
            .lock()
            .unwrap()
            .contains_key(domain.as_str())
    }
}

impl Clone for ExpertCache {
    fn clone(&self) -> Self {
        Self {
            max_experts: self.max_experts,
            cache: Arc::clone(&self.cache),
            lru_order: Arc::clone(&self.lru_order),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mock_inference_model_new() {
        let model = MockInferenceModel::new("qwen2.5-coder:14b".to_string());
        assert_eq!(model.id(), "qwen2.5-coder:14b");
    }

    #[test]
    fn test_expert_cache_new() {
        let cache = ExpertCache::new(2);
        assert_eq!(cache.cached_count(), 0);
    }

    #[test]
    fn test_expert_cache_load_once() {
        let cache = ExpertCache::new(3);
        let router = ExpertRouter::new_default();

        let model = cache.get_or_load(ExpertDomain::Hotel, &router).unwrap();
        assert_eq!(model.id(), "qwen2.5-coder:14b");
        assert_eq!(cache.cached_count(), 1);
    }

    #[test]
    fn test_expert_cache_load_multiple() {
        let cache = ExpertCache::new(3);
        let router = ExpertRouter::new_default();

        let _ = cache.get_or_load(ExpertDomain::Hotel, &router).unwrap();
        let _ = cache.get_or_load(ExpertDomain::Glass, &router).unwrap();
        let _ = cache.get_or_load(ExpertDomain::Auto, &router).unwrap();

        assert_eq!(cache.cached_count(), 3);
    }

    #[test]
    fn test_expert_cache_get_cached_hit() {
        let cache = ExpertCache::new(3);
        let router = ExpertRouter::new_default();

        let _ = cache.get_or_load(ExpertDomain::Hotel, &router).unwrap();
        let model = cache.get_cached(ExpertDomain::Hotel).unwrap();
        assert_eq!(model.id(), "qwen2.5-coder:14b");
    }

    #[test]
    fn test_expert_cache_get_cached_miss() {
        let cache = ExpertCache::new(3);
        let result = cache.get_cached(ExpertDomain::Hotel);
        assert!(result.is_none());
    }

    #[test]
    fn test_expert_cache_is_cached() {
        let cache = ExpertCache::new(3);
        let router = ExpertRouter::new_default();

        assert!(!cache.is_cached(ExpertDomain::Hotel));
        let _ = cache.get_or_load(ExpertDomain::Hotel, &router).unwrap();
        assert!(cache.is_cached(ExpertDomain::Hotel));
    }

    #[test]
    fn test_expert_cache_lru_eviction() {
        let cache = ExpertCache::new(2);
        let router = ExpertRouter::new_default();

        // Load hotel
        let _ = cache.get_or_load(ExpertDomain::Hotel, &router).unwrap();
        assert_eq!(cache.cached_count(), 1);
        assert!(cache.is_cached(ExpertDomain::Hotel));

        // Load glass
        let _ = cache.get_or_load(ExpertDomain::Glass, &router).unwrap();
        assert_eq!(cache.cached_count(), 2);
        assert!(cache.is_cached(ExpertDomain::Glass));

        // Load auto (evicts hotel)
        let _ = cache.get_or_load(ExpertDomain::Auto, &router).unwrap();
        assert_eq!(cache.cached_count(), 2);
        assert!(!cache.is_cached(ExpertDomain::Hotel));
        assert!(cache.is_cached(ExpertDomain::Glass));
        assert!(cache.is_cached(ExpertDomain::Auto));
    }

    #[test]
    fn test_expert_cache_lru_refresh_on_access() {
        let cache = ExpertCache::new(2);
        let router = ExpertRouter::new_default();

        // Load hotel and glass
        let _ = cache.get_or_load(ExpertDomain::Hotel, &router).unwrap();
        let _ = cache.get_or_load(ExpertDomain::Glass, &router).unwrap();
        assert_eq!(cache.cached_count(), 2);

        // Access hotel (makes it most recently used)
        let _ = cache.get_cached(ExpertDomain::Hotel).unwrap();

        // Load auto (should evict glass, not hotel)
        let _ = cache.get_or_load(ExpertDomain::Auto, &router).unwrap();
        assert_eq!(cache.cached_count(), 2);
        assert!(cache.is_cached(ExpertDomain::Hotel));
        assert!(!cache.is_cached(ExpertDomain::Glass));
        assert!(cache.is_cached(ExpertDomain::Auto));
    }

    #[test]
    fn test_expert_cache_size_tracking() {
        let cache = ExpertCache::new(3);
        let router = ExpertRouter::new_default();

        assert_eq!(cache.cached_count(), 0);
        let _ = cache.get_or_load(ExpertDomain::Hotel, &router).unwrap();
        assert_eq!(cache.cached_count(), 1);
        let _ = cache.get_or_load(ExpertDomain::Glass, &router).unwrap();
        assert_eq!(cache.cached_count(), 2);
        let _ = cache.get_or_load(ExpertDomain::Auto, &router).unwrap();
        assert_eq!(cache.cached_count(), 3);
    }

    #[test]
    fn test_expert_cache_clear() {
        let cache = ExpertCache::new(3);
        let router = ExpertRouter::new_default();

        let _ = cache.get_or_load(ExpertDomain::Hotel, &router).unwrap();
        let _ = cache.get_or_load(ExpertDomain::Glass, &router).unwrap();
        assert_eq!(cache.cached_count(), 2);

        cache.clear();
        assert_eq!(cache.cached_count(), 0);
        assert!(!cache.is_cached(ExpertDomain::Hotel));
        assert!(!cache.is_cached(ExpertDomain::Glass));
    }

    #[test]
    fn test_expert_cache_clone() {
        let cache1 = ExpertCache::new(3);
        let router = ExpertRouter::new_default();

        let _ = cache1.get_or_load(ExpertDomain::Hotel, &router).unwrap();
        let cache2 = cache1.clone();

        assert_eq!(cache2.cached_count(), 1);
        assert!(cache2.is_cached(ExpertDomain::Hotel));
    }
}
