use std::collections::{HashMap, HashSet};
use uuid::Uuid;

pub struct ReachabilityCache {
    graph: HashMap<Uuid, Vec<Uuid>>,
    cache: HashMap<(Uuid, Uuid), bool>,
    hits: u64,
    misses: u64,
}

impl ReachabilityCache {
    pub fn new() -> Self {
        Self {
            graph: HashMap::new(),
            cache: HashMap::new(),
            hits: 0,
            misses: 0,
        }
    }

    pub fn add_edge(&mut self, from: Uuid, to: Uuid) {
        self.graph.entry(from).or_insert_with(Vec::new).push(to);
    }

    pub fn reachable(&mut self, from: Uuid, to: Uuid) -> bool {
        let key = (from, to);

        // Check cache
        if let Some(&result) = self.cache.get(&key) {
            self.hits += 1;
            return result;
        }

        // Cache miss
        self.misses += 1;

        // Perform DFS to find reachability
        let mut visited = HashSet::new();
        let result = self.dfs(from, to, &mut visited);

        // Cache the result
        self.cache.insert(key, result);
        result
    }

    fn dfs(&self, current: Uuid, target: Uuid, visited: &mut HashSet<Uuid>) -> bool {
        if current == target {
            return true;
        }

        if visited.contains(&current) {
            return false;
        }

        visited.insert(current);

        if let Some(neighbors) = self.graph.get(&current) {
            for &neighbor in neighbors {
                if self.dfs(neighbor, target, visited) {
                    return true;
                }
            }
        }

        false
    }

    pub fn hit_ratio(&self) -> f64 {
        let total = self.hits + self.misses;
        if total == 0 {
            0.0
        } else {
            self.hits as f64 / total as f64
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_transitive_reachability_3_hops() {
        let mut cache = ReachabilityCache::new();
        let a = Uuid::new_v4();
        let b = Uuid::new_v4();
        let c = Uuid::new_v4();
        let d = Uuid::new_v4();

        // A -> B -> C -> D
        cache.add_edge(a, b);
        cache.add_edge(b, c);
        cache.add_edge(c, d);

        // Should reach D from A after 3 hops
        assert!(cache.reachable(a, d));
    }

    #[test]
    fn test_disconnected_subgraph_not_reachable() {
        let mut cache = ReachabilityCache::new();
        let a = Uuid::new_v4();
        let b = Uuid::new_v4();
        let c = Uuid::new_v4();
        let d = Uuid::new_v4();

        // A -> B and C -> D (two separate subgraphs)
        cache.add_edge(a, b);
        cache.add_edge(c, d);

        // Should not reach D from A
        assert!(!cache.reachable(a, d));
    }

    #[test]
    fn test_repeated_query_cache_hit_ratio() {
        let mut cache = ReachabilityCache::new();
        let a = Uuid::new_v4();
        let b = Uuid::new_v4();

        cache.add_edge(a, b);

        // First query: cache miss
        let _ = cache.reachable(a, b);

        // Next 99 queries: cache hits
        for _ in 0..99 {
            let _ = cache.reachable(a, b);
        }

        // With 1 miss and 99 hits, hit ratio should be >= 0.99
        let ratio = cache.hit_ratio();
        assert!(ratio >= 0.99);
    }
}
