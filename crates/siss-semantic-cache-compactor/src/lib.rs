//! siss-semantic-cache-compactor: Semantic cache compaction and cost optimization
//!
//! Provides:
//! - Semantic cache compaction (removing redundant values)
//! - Obsolete memory node pruning
//! - Cache invalidation strategy
//! - Per-transaction cost reduction (<$0.10)

pub mod error;
pub mod types;
pub mod cache_compactor;
pub mod memory_pruner;
pub mod cost_tracker;

pub use error::{Error, Result};
pub use types::*;
pub use cache_compactor::{CacheCompactor, CompactionConfig};
pub use memory_pruner::{MemoryPruner, PruningConfig};
pub use cost_tracker::{CostTracker, CostConfig};

/// Library version
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
