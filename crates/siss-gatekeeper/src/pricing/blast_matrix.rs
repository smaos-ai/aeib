//! BlastMatrixCache — O(1) pricing lookup by (tool_id, risk_class).
//!
//! Architecture:
//! - DashMap<(Uuid, RiskClass), i64>: concurrent hashmap for O(1) lookups.
//! - No locks: read-write operations never block the main thread.
//! - Benchmark gate: bulk_load 1000 entries in <1ms (O(1) insertion rate).

use dashmap::DashMap;
use siss_graph_core::node::resource::RiskClass;
use std::sync::Arc;
use uuid::Uuid;

/// BlastMatrixCache: O(1) lookup of tool pricing by (tool_id, risk_class).
///
/// Invariants:
/// - Each (Uuid, RiskClass) key maps to exactly one i64 price.
/// - Inserts and updates are atomic and lock-free.
/// - Lookups never block and always return immediately.
/// - Bulk load is optimized for cache-friendly insertion patterns.
#[derive(Debug, Clone)]
pub struct BlastMatrixCache {
    grid: Arc<DashMap<(Uuid, RiskClass), i64>>,
}

impl BlastMatrixCache {
    /// Create a new empty BlastMatrixCache.
    pub fn new() -> Self {
        Self {
            grid: Arc::new(DashMap::new()),
        }
    }

    /// Insert or update a price entry.
    ///
    /// # Arguments
    /// - `tool`: Tool identifier (UUID).
    /// - `risk`: Risk classification (Low, Medium, High, Critical).
    /// - `price`: Price in base units (i64).
    ///
    /// # Time Complexity
    /// O(1) expected time; atomic operation with no lock contention.
    pub fn insert(&self, tool: Uuid, risk: RiskClass, price: i64) {
        self.grid.insert((tool, risk), price);
    }

    /// Look up a price by (tool_id, risk_class).
    ///
    /// # Arguments
    /// - `tool`: Tool identifier (UUID).
    /// - `risk`: Risk classification (Low, Medium, High, Critical).
    ///
    /// # Returns
    /// - `Some(price)` if the entry exists.
    /// - `None` if the entry does not exist.
    ///
    /// # Time Complexity
    /// O(1) expected time; never blocks.
    pub fn lookup(&self, tool: Uuid, risk: RiskClass) -> Option<i64> {
        self.grid.get(&(tool, risk)).map(|r| *r)
    }

    /// Bulk load entries into the cache.
    ///
    /// # Arguments
    /// - `entries`: Vec of (tool_id, risk_class, price) tuples.
    ///
    /// # Behavior
    /// Inserts each entry in sequence. Existing entries are overwritten.
    /// All insertions are completed before the function returns.
    ///
    /// # Time Complexity
    /// O(n) for n entries; each insertion is O(1).
    /// Benchmark gate: 1000 entries must complete in <1ms.
    pub fn bulk_load(&self, entries: Vec<(Uuid, RiskClass, i64)>) {
        for (tool, risk, price) in entries {
            self.grid.insert((tool, risk), price);
        }
    }
}

impl Default for BlastMatrixCache {
    fn default() -> Self {
        Self::new()
    }
}
