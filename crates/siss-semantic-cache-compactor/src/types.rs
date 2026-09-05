//! Core types for semantic cache compaction

use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Cache entry identifier
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct CacheEntryId(pub Uuid);

impl CacheEntryId {
    pub fn new() -> Self {
        CacheEntryId(Uuid::new_v4())
    }
}

impl Default for CacheEntryId {
    fn default() -> Self {
        Self::new()
    }
}

/// Cache entry
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CacheEntry {
    pub id: CacheEntryId,
    pub key: String,
    pub value: serde_json::Value,
    pub semantic_hash: u64,
    pub size_bytes: usize,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub last_accessed: chrono::DateTime<chrono::Utc>,
    pub access_count: u64,
    pub cost_tokens: f64,
}

/// Memory node for tracking cache structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryNode {
    pub id: Uuid,
    pub entries: Vec<CacheEntryId>,
    pub total_size: usize,
    pub obsolescence_score: f32,
    pub last_compacted: Option<chrono::DateTime<chrono::Utc>>,
}

/// Compaction statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompactionStats {
    pub entries_compacted: u64,
    pub bytes_freed: usize,
    pub duplicate_entries_removed: u64,
    pub cost_savings_tokens: f64,
    pub time_ms: u128,
}

/// Cost tracking record
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CostRecord {
    pub transaction_id: Uuid,
    pub initial_cost: f64,
    pub final_cost: f64,
    pub savings: f64,
    pub timestamp: chrono::DateTime<chrono::Utc>,
}

/// Similarity score (0.0 to 1.0)
#[derive(Debug, Clone, Copy)]
pub struct SimilarityScore(pub f32);

impl SimilarityScore {
    pub fn from_f32(val: f32) -> Option<Self> {
        if (0.0..=1.0).contains(&val) {
            Some(SimilarityScore(val))
        } else {
            None
        }
    }

    pub fn is_similar(&self, threshold: f32) -> bool {
        self.0 >= threshold
    }
}

/// Pruning recommendation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PruningRecommendation {
    pub entry_id: CacheEntryId,
    pub reason: String,
    pub obsolescence_score: f32,
    pub potential_savings_bytes: usize,
}
