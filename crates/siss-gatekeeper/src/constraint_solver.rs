use std::collections::HashMap;
use uuid::Uuid;

#[derive(Hash, Eq, PartialEq, Clone)]
pub struct ConstraintKey {
    pub entity_a: Uuid,
    pub entity_b: Uuid,
    pub constraint_type: String,
}

pub struct ConstraintSolver {
    cache: HashMap<ConstraintKey, bool>,
    max_depth: u32,
    total_queries: u64,
    cache_hits: u64,
}

impl ConstraintSolver {
    pub fn new(max_depth: u32) -> Self {
        ConstraintSolver {
            cache: HashMap::new(),
            max_depth,
            total_queries: 0,
            cache_hits: 0,
        }
    }

    pub fn solve(&mut self, key: ConstraintKey, edges: &[(Uuid, Uuid)]) -> bool {
        self.total_queries += 1;

        // Check cache first
        if let Some(&cached_result) = self.cache.get(&key) {
            self.cache_hits += 1;
            return cached_result;
        }

        // Not in cache, perform DFS transitive closure query
        let result = self.transitive_closure_dfs(&key.entity_a, &key.entity_b, edges, self.max_depth);

        // Cache the result
        self.cache.insert(key, result);
        result
    }

    fn transitive_closure_dfs(
        &self,
        from: &Uuid,
        to: &Uuid,
        edges: &[(Uuid, Uuid)],
        max_depth: u32,
    ) -> bool {
        if from == to {
            return true;
        }

        let mut visited = std::collections::HashSet::new();
        self.dfs_helper(from, to, edges, &mut visited, max_depth)
    }

    fn dfs_helper(
        &self,
        current: &Uuid,
        target: &Uuid,
        edges: &[(Uuid, Uuid)],
        visited: &mut std::collections::HashSet<Uuid>,
        depth_remaining: u32,
    ) -> bool {
        if depth_remaining == 0 {
            return false;
        }

        if visited.contains(current) {
            return false;
        }

        visited.insert(*current);

        // Find all edges starting from current
        for (from, to) in edges {
            if from == current {
                if to == target {
                    return true;
                }
                if self.dfs_helper(to, target, edges, visited, depth_remaining - 1) {
                    return true;
                }
            }
        }

        false
    }

    pub fn detect_cycle(&self, edges: &[(Uuid, Uuid)]) -> bool {
        // Build adjacency list
        let mut graph: HashMap<Uuid, Vec<Uuid>> = HashMap::new();
        let mut all_nodes = std::collections::HashSet::new();

        for (from, to) in edges {
            graph.entry(*from).or_insert_with(Vec::new).push(*to);
            all_nodes.insert(*from);
            all_nodes.insert(*to);
        }

        let mut visited = std::collections::HashSet::new();
        let mut rec_stack = std::collections::HashSet::new();

        for node in all_nodes {
            if !visited.contains(&node) {
                if self.has_cycle_dfs(&node, &graph, &mut visited, &mut rec_stack) {
                    return true;
                }
            }
        }

        false
    }

    fn has_cycle_dfs(
        &self,
        node: &Uuid,
        graph: &HashMap<Uuid, Vec<Uuid>>,
        visited: &mut std::collections::HashSet<Uuid>,
        rec_stack: &mut std::collections::HashSet<Uuid>,
    ) -> bool {
        visited.insert(*node);
        rec_stack.insert(*node);

        if let Some(neighbors) = graph.get(node) {
            for neighbor in neighbors {
                if !visited.contains(neighbor) {
                    if self.has_cycle_dfs(neighbor, graph, visited, rec_stack) {
                        return true;
                    }
                } else if rec_stack.contains(neighbor) {
                    return true;
                }
            }
        }

        rec_stack.remove(node);
        false
    }

    pub fn cache_hit_ratio(&self) -> f64 {
        if self.total_queries == 0 {
            return 0.0;
        }
        self.cache_hits as f64 / self.total_queries as f64
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Instant;

    #[test]
    fn test_rebac_1000_solves_under_5ms() {
        let mut solver = ConstraintSolver::new(10);
        let key = ConstraintKey {
            entity_a: Uuid::new_v4(),
            entity_b: Uuid::new_v4(),
            constraint_type: "delegation".to_string(),
        };
        let edges = &[
            (Uuid::new_v4(), Uuid::new_v4()),
            (Uuid::new_v4(), Uuid::new_v4()),
        ];

        let start = Instant::now();
        for _ in 0..1000 {
            solver.solve(key.clone(), edges);
        }
        let elapsed = start.elapsed();

        assert!(
            elapsed.as_millis() < 5,
            "Expected < 5ms, got {}ms",
            elapsed.as_millis()
        );
    }

    #[test]
    fn test_circular_delegation_detection() {
        let solver = ConstraintSolver::new(10);
        let a = Uuid::new_v4();
        let b = Uuid::new_v4();
        let c = Uuid::new_v4();

        let edges = &[(a, b), (b, c), (c, a)];
        assert!(solver.detect_cycle(edges), "Expected cycle to be detected");
    }

    #[test]
    fn test_cache_hit_ratio_80pct() {
        let mut solver = ConstraintSolver::new(10);
        let key = ConstraintKey {
            entity_a: Uuid::new_v4(),
            entity_b: Uuid::new_v4(),
            constraint_type: "delegation".to_string(),
        };
        let edges = &[(Uuid::new_v4(), Uuid::new_v4())];

        for _ in 0..100 {
            solver.solve(key.clone(), edges);
        }

        let hit_ratio = solver.cache_hit_ratio();
        assert!(
            hit_ratio >= 0.8,
            "Expected cache hit ratio >= 0.8, got {}",
            hit_ratio
        );
    }
}
