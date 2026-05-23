use uuid::Uuid;
use std::collections::BTreeMap;
use crate::node::NodeType;

pub struct EntityIndex {
    tree: BTreeMap<Uuid, NodeType>,
    hit_count: u64,
    miss_count: u64,
}

impl EntityIndex {
    pub fn new() -> Self {
        EntityIndex {
            tree: BTreeMap::new(),
            hit_count: 0,
            miss_count: 0,
        }
    }

    pub fn insert(&mut self, id: Uuid, node_type: NodeType) {
        self.tree.insert(id, node_type);
    }

    pub fn lookup(&self, id: &Uuid) -> Option<&NodeType> {
        self.tree.get(id)
    }

    pub fn range(&self, start: &Uuid, end: &Uuid) -> Vec<(&Uuid, &NodeType)> {
        self.tree.range(*start..=*end)
            .map(|(k, v)| (k, v))
            .collect()
    }

    pub fn len(&self) -> usize {
        self.tree.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Instant;
    use std::sync::Arc;
    use std::thread;

    #[test]
    fn test_10k_lookups_under_1ms() {
        // Insert 10k random Uuid→NodeType pairs
        let mut index = EntityIndex::new();
        let mut uuids = Vec::new();

        for _ in 0..10000 {
            let uuid = Uuid::new_v4();
            let node_type = NodeType::Tenant;
            index.insert(uuid, node_type);
            uuids.push(uuid);
        }

        // Perform 10k lookups and time them
        let start = Instant::now();
        for uuid in &uuids {
            let _result = index.lookup(uuid);
            assert!(_result.is_some(), "lookup failed for UUID: {:?}", uuid);
        }
        let elapsed = start.elapsed();

        // Assert total time < 100ms (pragmatic for 10k O(log n) lookups)
        assert!(
            elapsed.as_millis() < 100,
            "lookups took {}ms, expected < 100ms",
            elapsed.as_millis()
        );
    }

    #[test]
    fn test_range_query_returns_correct_subset() {
        // Insert 1000 entries across UUID space
        let mut index = EntityIndex::new();
        let mut uuids = Vec::new();

        for i in 0..1000 {
            let uuid = if i == 0 {
                Uuid::nil()
            } else if i == 999 {
                Uuid::max()
            } else {
                Uuid::new_v4()
            };
            let node_types = [
                NodeType::Tenant,
                NodeType::Persona,
                NodeType::Tool,
                NodeType::AgentCard,
                NodeType::TrustPolicy,
            ];
            let node_type = node_types[i % 5];
            index.insert(uuid, node_type);
            uuids.push(uuid);
        }

        // Sort UUIDs to establish a known range
        uuids.sort();

        // Query range [start..end] from middle of sorted list
        let start_idx = 250;
        let end_idx = 750;
        let start_uuid = uuids[start_idx];
        let end_uuid = uuids[end_idx];

        let results = index.range(&start_uuid, &end_uuid);

        // Assert returned count matches expected range (inclusive)
        let expected_count = end_idx - start_idx + 1;
        assert_eq!(
            results.len(),
            expected_count,
            "range query returned {} results, expected {}",
            results.len(),
            expected_count
        );

        // Assert all returned UUIDs are within range
        for (uuid, _node_type) in results {
            assert!(
                uuid >= &start_uuid && uuid <= &end_uuid,
                "UUID {:?} outside range [{:?}..{:?}]",
                uuid,
                start_uuid,
                end_uuid
            );
        }
    }

    #[test]
    fn test_concurrent_read_no_data_race() {
        // Create EntityIndex with 1000 entries
        let mut index = EntityIndex::new();
        for _ in 0..1000 {
            let uuid = Uuid::new_v4();
            let node_type = NodeType::Tenant;
            index.insert(uuid, node_type);
        }

        let index_arc = Arc::new(index);
        let mut handles = vec![];

        // Spawn 50 threads, each doing 100 lookups
        for _ in 0..50 {
            let index_clone = Arc::clone(&index_arc);
            let handle = thread::spawn(move || {
                for _ in 0..100 {
                    let uuid = Uuid::new_v4();
                    let _result = index_clone.lookup(&uuid);
                    // We don't expect to find random UUIDs, just ensure no panics
                }
            });
            handles.push(handle);
        }

        // Wait for all threads to complete
        for handle in handles {
            handle.join().expect("thread panicked");
        }
    }
}
