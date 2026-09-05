//! Cache compaction: semantic deduplication and optimization

use crate::error::Result;
use crate::types::{CacheEntry, CacheEntryId, CompactionStats, SimilarityScore};
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;

/// Compaction configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompactionConfig {
    pub similarity_threshold: f32,
    pub max_iterations: usize,
    pub target_compression_ratio: f32,
}

impl Default for CompactionConfig {
    fn default() -> Self {
        Self {
            similarity_threshold: 0.85,
            max_iterations: 10,
            target_compression_ratio: 0.8,
        }
    }
}

/// Cache compactor: deduplicates and compresses semantic cache
pub struct CacheCompactor {
    config: CompactionConfig,
    cache: Arc<RwLock<HashMap<CacheEntryId, CacheEntry>>>,
    stats: Arc<RwLock<CompactionStats>>,
}

impl CacheCompactor {
    /// Create new cache compactor
    pub fn new(config: CompactionConfig) -> Self {
        Self {
            config,
            cache: Arc::new(RwLock::new(HashMap::new())),
            stats: Arc::new(RwLock::new(CompactionStats {
                entries_compacted: 0,
                bytes_freed: 0,
                duplicate_entries_removed: 0,
                cost_savings_tokens: 0.0,
                time_ms: 0,
            })),
        }
    }

    /// Add entry to cache
    pub fn insert(&self, entry: CacheEntry) -> Result<()> {
        let mut cache = self.cache.write();
        cache.insert(entry.id, entry);
        Ok(())
    }

    /// Compute semantic similarity between entries
    pub fn semantic_similarity(&self, entry1: &CacheEntry, entry2: &CacheEntry) -> SimilarityScore {
        // Simple similarity based on semantic hash and value structure
        let hash_match: f64 = if entry1.semantic_hash == entry2.semantic_hash {
            1.0
        } else {
            0.0
        };

        // Check if values are structurally similar
        let value_match: f64 = if entry1.value.to_string() == entry2.value.to_string() {
            1.0
        } else if entry1.key.contains(&entry2.key) || entry2.key.contains(&entry1.key) {
            0.5
        } else {
            0.0
        };

        let similarity_val = ((hash_match * 0.6 + value_match * 0.4).min(1.0).max(0.0)) as f32;
        SimilarityScore(similarity_val)
    }

    /// Compact cache by removing duplicates
    pub fn compact(&self) -> Result<CompactionStats> {
        let start_time = std::time::Instant::now();
        let mut cache = self.cache.write();

        let initial_size: usize = cache.values().map(|e| e.size_bytes).sum();
        let mut removed_ids = Vec::new();

        // Find and remove duplicate entries
        let entries: Vec<_> = cache.values().cloned().collect();
        for i in 0..entries.len() {
            for j in (i + 1)..entries.len() {
                let similarity = self.semantic_similarity(&entries[i], &entries[j]);

                if similarity.is_similar(self.config.similarity_threshold) {
                    // Keep higher access count entry, remove the other
                    if entries[i].access_count >= entries[j].access_count {
                        removed_ids.push(entries[j].id);
                    } else {
                        removed_ids.push(entries[i].id);
                    }
                }
            }
        }

        // Remove duplicates
        for id in &removed_ids {
            cache.remove(id);
        }

        let final_size: usize = cache.values().map(|e| e.size_bytes).sum();
        let bytes_freed = initial_size.saturating_sub(final_size);

        let elapsed = start_time.elapsed();

        let stats = CompactionStats {
            entries_compacted: cache.len() as u64,
            bytes_freed,
            duplicate_entries_removed: removed_ids.len() as u64,
            cost_savings_tokens: (removed_ids.len() as f64 * 0.05),
            time_ms: elapsed.as_millis(),
        };

        let mut current_stats = self.stats.write();
        *current_stats = stats.clone();

        Ok(stats)
    }

    /// Get cache statistics
    pub fn stats(&self) -> CompactionStats {
        self.stats.read().clone()
    }

    /// Get number of entries in cache
    pub fn entry_count(&self) -> usize {
        self.cache.read().len()
    }

    /// Get total cache size in bytes
    pub fn total_size(&self) -> usize {
        self.cache.read().values().map(|e| e.size_bytes).sum()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_entry(key: &str, semantic_hash: u64) -> CacheEntry {
        CacheEntry {
            id: CacheEntryId::new(),
            key: key.to_string(),
            value: serde_json::json!({"data": key}),
            semantic_hash,
            size_bytes: 1024,
            created_at: chrono::Utc::now(),
            last_accessed: chrono::Utc::now(),
            access_count: 1,
            cost_tokens: 0.1,
        }
    }

    #[test]
    fn test_compactor_creation() {
        let compactor = CacheCompactor::new(CompactionConfig::default());
        assert_eq!(compactor.entry_count(), 0);
    }

    #[test]
    fn test_insert_entry() {
        let compactor = CacheCompactor::new(CompactionConfig::default());
        let entry = create_test_entry("test_key", 12345);
        let result = compactor.insert(entry);
        assert!(result.is_ok());
        assert_eq!(compactor.entry_count(), 1);
    }

    #[test]
    fn test_semantic_similarity_identical() {
        let compactor = CacheCompactor::new(CompactionConfig::default());
        let entry1 = create_test_entry("key", 12345);
        let entry2 = create_test_entry("key", 12345);

        let similarity = compactor.semantic_similarity(&entry1, &entry2);
        assert!(similarity.0 > 0.9);
    }

    #[test]
    fn test_semantic_similarity_different() {
        let compactor = CacheCompactor::new(CompactionConfig::default());
        let entry1 = create_test_entry("key1", 12345);
        let entry2 = create_test_entry("key2", 67890);

        let similarity = compactor.semantic_similarity(&entry1, &entry2);
        assert!(similarity.0 < 0.5);
    }

    #[test]
    fn test_compact_removes_duplicates() {
        let compactor = CacheCompactor::new(CompactionConfig::default());

        let entry1 = create_test_entry("duplicate", 12345);
        let entry2 = create_test_entry("duplicate", 12345);

        compactor.insert(entry1).unwrap();
        compactor.insert(entry2).unwrap();

        assert_eq!(compactor.entry_count(), 2);

        let stats = compactor.compact().unwrap();
        assert!(stats.duplicate_entries_removed > 0);
    }

    #[test]
    fn test_total_size() {
        let compactor = CacheCompactor::new(CompactionConfig::default());
        let entry = create_test_entry("test", 12345);
        compactor.insert(entry).unwrap();

        let total_size = compactor.total_size();
        assert!(total_size > 0);
    }
}
