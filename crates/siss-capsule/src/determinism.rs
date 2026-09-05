// Phase 26 Tier 2: Deterministic Abstraction
// Prompt caching + temperature=0.0 enforcement

use chrono::{DateTime, Utc};
use dashmap::DashMap;
use sha2::{Digest, Sha256};
use std::sync::Arc;

#[derive(Clone, Debug)]
pub struct CachedPrompt {
    pub hash: [u8; 32],
    pub content: String,
    pub cached_at: DateTime<Utc>,
    pub hit_count: u64,
}

#[derive(Clone, Debug)]
pub struct CacheStats {
    pub total_hits: u64,
    pub total_misses: u64,
    pub avg_latency_ms: f64,
    pub memory_bytes: usize,
}

/// Enforces deterministic execution with prompt caching and zero temperature
pub struct DeterministicExecutor {
    prompt_cache: Arc<DashMap<String, CachedPrompt>>,
    #[allow(dead_code)]
    temperature: f32,
    stats: Arc<DashMap<String, u64>>,
}

impl DeterministicExecutor {
    /// Create new executor with temperature fixed at 0.0
    pub fn new() -> Self {
        Self {
            prompt_cache: Arc::new(DashMap::new()),
            temperature: 0.0,
            stats: Arc::new(DashMap::new()),
        }
    }

    /// Get temperature (always 0.0 for determinism)
    pub fn temperature(&self) -> f32 {
        0.0
    }

    /// Cache a system prompt and return its SHA256 hash
    pub fn cache_prompt(&self, system_prompt: &str) -> std::result::Result<[u8; 32], &'static str> {
        let mut hasher = Sha256::new();
        hasher.update(system_prompt.as_bytes());
        let hash_bytes = hasher.finalize();
        let mut hash = [0u8; 32];
        hash.copy_from_slice(&hash_bytes);

        let key = hex::encode(hash);

        self.prompt_cache.insert(
            key.clone(),
            CachedPrompt {
                hash,
                content: system_prompt.to_string(),
                cached_at: Utc::now(),
                hit_count: 0,
            },
        );

        // Record miss for stats
        let misses = self.stats.get("total_misses").map(|v| *v).unwrap_or(0);
        self.stats.insert("total_misses".to_string(), misses + 1);

        Ok(hash)
    }

    /// Retrieve cached prompt by hash
    pub fn get_cached_prompt(&self, hash: &[u8; 32]) -> Option<CachedPrompt> {
        let key = hex::encode(hash);

        if let Some(mut cached) = self.prompt_cache.get_mut(&key) {
            cached.hit_count += 1;

            // Record hit for stats
            let hits = self.stats.get("total_hits").map(|v| *v).unwrap_or(0);
            self.stats.insert("total_hits".to_string(), hits + 1);

            Some(cached.clone())
        } else {
            // Record miss
            let misses = self.stats.get("total_misses").map(|v| *v).unwrap_or(0);
            self.stats.insert("total_misses".to_string(), misses + 1);

            None
        }
    }

    /// Get cache statistics
    pub fn cache_stats(&self) -> CacheStats {
        let total_hits = self.stats.get("total_hits").map(|v| *v).unwrap_or(0);
        let total_misses = self.stats.get("total_misses").map(|v| *v).unwrap_or(0);

        let memory_bytes = self
            .prompt_cache
            .iter()
            .map(|entry| entry.content.len() + 64)
            .sum();

        CacheStats {
            total_hits,
            total_misses,
            avg_latency_ms: 0.0,
            memory_bytes,
        }
    }
}

impl Default for DeterministicExecutor {
    fn default() -> Self {
        Self::new()
    }
}
