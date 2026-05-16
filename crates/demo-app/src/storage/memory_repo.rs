use crate::models::memory::{MemorySnippet, MemoryTier, MemoryWrite};
use std::sync::{Arc, RwLock};

#[derive(Clone)]
pub struct ConcurrentMemoryRepo {
    // Arc<RwLock> ensures multiple agents (Alpha, Beta) can query simultaneously,
    // while writes are safely queued.
    l2_store: Arc<RwLock<Vec<MemoryWrite>>>,
}

impl ConcurrentMemoryRepo {
    pub fn new() -> Self {
        Self {
            l2_store: Arc::new(RwLock::new(Vec::new())),
        }
    }

    /// Thread-safe write execution invoked by OpenClaw after AP2 validation
    pub fn insert_l2(&self, write: MemoryWrite) {
        let mut db = self.l2_store.write().unwrap();
        db.push(write);
    }

    /// Cross-pane state synchronization query
    pub fn query_l2_by_task(&self, task_id: &str) -> Vec<MemorySnippet> {
        let db = self.l2_store.read().unwrap();

        db.iter()
            .filter(|w| w.task_id == task_id && w.memory_type == MemoryTier::L2Semantic)
            .enumerate()
            .map(|(i, w)| MemorySnippet {
                memory_id: format!("mem-l2-{}-{}", task_id, i),
                snippet_type: MemoryTier::L2Semantic,
                relevance_score: 0.99,
                compressed_summary: w.raw_span.clone(),
            })
            .collect()
    }
}

impl Default for ConcurrentMemoryRepo {
    fn default() -> Self {
        Self::new()
    }
}
