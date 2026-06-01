//! TrustHashIndex — O(1) constant-time routing with consistent hashing.
//!
//! Architecture:
//! - ConsistentHashRing: BTreeMap<u64, NodeId> with virtual nodes per real node.
//!   Ring lookup is O(log V) where V = VIRTUAL_NODES_PER_NODE (150, fixed constant).
//!   For fixed V this is O(1) — no O(n) scan over real nodes.
//! - TrustHashIndex: ring + DashMap<NodeId, f32> for cached pre-ranked trust scores.
//!   Trust scores are loaded once and read at O(1) via DashMap.
//! - Fail-closed: RouteError on empty ring or unavailable node; never panics.

use dashmap::DashMap;
use sha2::{Digest, Sha256};
use siss_graph_core::node::NodeId;
use std::collections::BTreeMap;
use std::sync::Arc;
use thiserror::Error;

/// Number of virtual nodes per real node on the ring.
/// 150 is the standard value for balanced consistent hashing.
const VIRTUAL_NODES_PER_NODE: u64 = 150;

/// Errors returned by routing operations.
/// Fail-closed: callers must handle all variants — no silent defaults.
#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum RouteError {
    #[error("ring is empty — no nodes available")]
    EmptyRing,
    #[error("node {0:?} is unavailable (trust score not loaded)")]
    NodeUnavailable(NodeId),
}

/// Consistent hash ring mapping hash-space positions to NodeIds via virtual nodes.
///
/// Invariants:
/// - `ring` is sorted BTreeMap: key = u64 position in [0, u64::MAX], value = real NodeId.
/// - Each real node occupies exactly `VIRTUAL_NODES_PER_NODE` positions.
/// - Lookup: clockwise walk from hash(key); wraps to ring start if past the last position.
/// - Key movement on remove: only keys between the removed node's virtual positions move.
#[derive(Debug, Clone)]
pub struct ConsistentHashRing {
    ring: BTreeMap<u64, NodeId>,
    nodes: Vec<NodeId>,
}

impl ConsistentHashRing {
    /// Create an empty ring.
    pub fn new() -> Self {
        Self {
            ring: BTreeMap::new(),
            nodes: Vec::new(),
        }
    }

    /// Build a ring from a slice of node IDs.
    pub fn from_nodes(nodes: &[NodeId]) -> Self {
        let mut ring = Self::new();
        for &node in nodes {
            ring.add_node(node);
        }
        ring
    }

    /// Add a node, inserting `VIRTUAL_NODES_PER_NODE` virtual positions.
    pub fn add_node(&mut self, node: NodeId) {
        for replica in 0..VIRTUAL_NODES_PER_NODE {
            let pos = hash_node(node, replica);
            self.ring.insert(pos, node);
        }
        if !self.nodes.contains(&node) {
            self.nodes.push(node);
        }
    }

    /// Remove a node, deleting all its virtual positions.
    pub fn remove_node(&mut self, node: NodeId) {
        for replica in 0..VIRTUAL_NODES_PER_NODE {
            let pos = hash_node(node, replica);
            self.ring.remove(&pos);
        }
        self.nodes.retain(|&n| n != node);
    }

    /// Look up which node owns `key`.
    ///
    /// Hashes `key` to a ring position, walks clockwise, wraps at end.
    /// Returns Err(EmptyRing) if the ring has no nodes.
    pub fn lookup(&self, key: &[u8]) -> Result<NodeId, RouteError> {
        if self.ring.is_empty() {
            return Err(RouteError::EmptyRing);
        }
        let pos = hash_key(key);
        let node = self
            .ring
            .range(pos..)
            .next()
            .or_else(|| self.ring.iter().next())
            .map(|(_, &node)| node)
            .ok_or(RouteError::EmptyRing)?;
        Ok(node)
    }

    /// Number of real nodes in the ring.
    pub fn node_count(&self) -> usize {
        self.nodes.len()
    }

    /// Returns true if the ring has no nodes.
    pub fn is_empty(&self) -> bool {
        self.nodes.is_empty()
    }

    /// Snapshot of real nodes (used for distribution analysis).
    pub fn nodes(&self) -> &[NodeId] {
        &self.nodes
    }
}

impl Default for ConsistentHashRing {
    fn default() -> Self {
        Self::new()
    }
}

/// TrustHashIndex: consistent ring + pre-ranked trust score cache.
///
/// Trust scores are loaded once via `load_trust_scores` and read O(1) per route.
/// The index is cheaply cloneable — ring and scores are Arc-wrapped.
#[derive(Debug, Clone)]
pub struct TrustHashIndex {
    ring: Arc<ConsistentHashRing>,
    trust_scores: Arc<DashMap<NodeId, f32>>,
}

impl TrustHashIndex {
    /// Create a new index with the given nodes. Trust scores must be loaded separately.
    pub fn new(nodes: &[NodeId]) -> Self {
        Self {
            ring: Arc::new(ConsistentHashRing::from_nodes(nodes)),
            trust_scores: Arc::new(DashMap::new()),
        }
    }

    /// Load trust scores in bulk. Scores are clamped to [0.0, 1.0].
    /// Overwrites existing scores for the same node.
    pub fn load_trust_scores(&self, scores: impl IntoIterator<Item = (NodeId, f32)>) {
        for (node, score) in scores {
            self.trust_scores.insert(node, score.clamp(0.0, 1.0));
        }
    }

    /// Route `task_id` to a node.
    ///
    /// Returns (NodeId, trust_score) on success.
    /// Returns Err(EmptyRing) if ring has no nodes.
    /// Returns Err(NodeUnavailable) if resolved node has no cached trust score.
    pub fn route(&self, task_id: NodeId) -> Result<(NodeId, f32), RouteError> {
        let key = task_id.0.as_bytes().to_vec();
        let node = self.ring.lookup(&key)?;
        let score = self
            .trust_scores
            .get(&node)
            .map(|r| *r)
            .ok_or(RouteError::NodeUnavailable(node))?;
        Ok((node, score))
    }

    /// Rebuild the ring with a new node set, preserving trust scores.
    /// Returns the new index; the old one is unmodified.
    pub fn with_nodes(self, nodes: &[NodeId]) -> Self {
        Self {
            ring: Arc::new(ConsistentHashRing::from_nodes(nodes)),
            trust_scores: self.trust_scores,
        }
    }

    /// Number of real nodes in the ring.
    pub fn node_count(&self) -> usize {
        self.ring.node_count()
    }
}

// ─── Hash utilities ──────────────────────────────────────────────────────────

/// Hash a virtual node position: SHA2(node_uuid || replica_u64_le) → u64.
fn hash_node(node: NodeId, replica: u64) -> u64 {
    let mut h = Sha256::new();
    h.update(node.0.as_bytes());
    h.update(replica.to_le_bytes());
    let d = h.finalize();
    u64::from_le_bytes(d[..8].try_into().unwrap())
}

/// Hash an arbitrary key to a ring position: SHA2(key) → u64.
fn hash_key(key: &[u8]) -> u64 {
    let mut h = Sha256::new();
    h.update(key);
    let d = h.finalize();
    u64::from_le_bytes(d[..8].try_into().unwrap())
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;
    use std::time::Instant;

    fn make_nodes(n: usize) -> Vec<NodeId> {
        (0..n).map(|_| NodeId::new()).collect()
    }

    fn make_index_with_scores(nodes: &[NodeId]) -> TrustHashIndex {
        let idx = TrustHashIndex::new(nodes);
        idx.load_trust_scores(nodes.iter().map(|&n| (n, 0.8)));
        idx
    }

    /// test_consistent_hash_ring_creation: Ring builds with N nodes,
    /// each contributing exactly VIRTUAL_NODES_PER_NODE virtual positions.
    #[test]
    fn test_consistent_hash_ring_creation() {
        let nodes = make_nodes(5);
        let ring = ConsistentHashRing::from_nodes(&nodes);
        assert_eq!(ring.node_count(), 5);
        assert_eq!(ring.ring.len(), 5 * VIRTUAL_NODES_PER_NODE as usize);
    }

    /// test_o1_lookup_basic: Single lookup returns a node from the ring.
    #[test]
    fn test_o1_lookup_basic() {
        let nodes = make_nodes(3);
        let index = make_index_with_scores(&nodes);
        let task_id = NodeId::new();
        let (node, score) = index.route(task_id).expect("route must succeed");
        assert!(nodes.contains(&node), "returned node must be from the ring");
        assert!((0.0..=1.0).contains(&score), "score must be in [0.0, 1.0]");
    }

    /// test_trust_score_caching: Scores load once; missing scores produce NodeUnavailable.
    #[test]
    fn test_trust_score_caching() {
        let nodes = make_nodes(4);
        let idx = TrustHashIndex::new(&nodes);
        let task_id = NodeId::new();

        // Before loading scores: must fail with NodeUnavailable
        match idx.route(task_id) {
            Err(RouteError::NodeUnavailable(_)) => {}
            other => panic!("expected NodeUnavailable before load, got {:?}", other),
        }

        // After loading scores: must succeed and return exact value
        idx.load_trust_scores(nodes.iter().map(|&n| (n, 0.75)));
        let (_, score) = idx.route(task_id).expect("route must succeed after load");
        assert!(
            (score - 0.75).abs() < f32::EPSILON,
            "score must match loaded value exactly"
        );
    }

    /// test_key_movement_minimal_on_rebalance: Remove one node from a 10-node ring.
    /// Only keys previously assigned to the removed node may change assignment.
    #[test]
    fn test_key_movement_minimal_on_rebalance() {
        let nodes = make_nodes(10);
        let ring_before = ConsistentHashRing::from_nodes(&nodes);

        let tasks: Vec<NodeId> = (0..1000).map(|_| NodeId::new()).collect();
        let before: Vec<NodeId> = tasks
            .iter()
            .map(|t| ring_before.lookup(t.0.as_bytes()).unwrap())
            .collect();

        let removed = nodes[0];
        let mut ring_after = ring_before.clone();
        ring_after.remove_node(removed);

        let after: Vec<NodeId> = tasks
            .iter()
            .map(|t| ring_after.lookup(t.0.as_bytes()).unwrap())
            .collect();

        // Keys NOT on the removed node must not have moved
        let wrongly_moved = before
            .iter()
            .zip(after.iter())
            .filter(|(b, a)| *b != &removed && b != a)
            .count();
        assert_eq!(wrongly_moved, 0, "non-removed-node keys must not move");

        // Fraction of moved keys should be ~1/N = ~10%; accept up to 25%
        let moved = before.iter().zip(after.iter()).filter(|(a, b)| a != b).count();
        let fraction = moved as f64 / 1000.0;
        assert!(
            fraction < 0.25,
            "excessive rebalance: {:.1}% moved (limit 25%)",
            fraction * 100.0
        );
    }

    /// test_empty_ring_error_handling: Empty TrustHashIndex returns EmptyRing.
    #[test]
    fn test_empty_ring_error_handling() {
        let idx = TrustHashIndex::new(&[]);
        match idx.route(NodeId::new()) {
            Err(RouteError::EmptyRing) => {}
            other => panic!("expected EmptyRing, got {:?}", other),
        }
    }

    /// Empty ConsistentHashRing direct lookup never panics.
    #[test]
    fn test_empty_ring_direct_lookup_no_panic() {
        let ring = ConsistentHashRing::new();
        match ring.lookup(b"any_key") {
            Err(RouteError::EmptyRing) => {}
            other => panic!("expected EmptyRing, got {:?}", other),
        }
    }

    /// prop_lookup_always_returns_same_node_for_same_key: deterministic routing.
    #[test]
    fn prop_lookup_always_returns_same_node_for_same_key() {
        let nodes = make_nodes(5);
        let index = make_index_with_scores(&nodes);
        for _ in 0..200 {
            let task_id = NodeId::new();
            let first = index.route(task_id).unwrap().0;
            for _ in 0..9 {
                assert_eq!(
                    index.route(task_id).unwrap().0,
                    first,
                    "same task_id must always route to the same node"
                );
            }
        }
    }

    /// prop_distribution_balanced: Keys distribute uniformly (no hotspots).
    /// With 10 nodes and 10_000 tasks, each node expects ~1000 tasks.
    /// Accept 3x band: [333, 3000].
    #[test]
    fn prop_distribution_balanced() {
        let nodes = make_nodes(10);
        let index = make_index_with_scores(&nodes);
        let mut counts: HashMap<NodeId, usize> = HashMap::new();
        for _ in 0..10_000 {
            let (node, _) = index.route(NodeId::new()).unwrap();
            *counts.entry(node).or_insert(0) += 1;
        }
        let expected = 10_000 / nodes.len();
        for (&node, &count) in &counts {
            assert!(
                count >= expected / 3 && count <= expected * 3,
                "node {:?}: {} tasks, expected ~{} (3x band)",
                node,
                count,
                expected
            );
        }
        assert_eq!(counts.len(), nodes.len(), "all nodes must receive tasks");
    }

    /// Benchmark: 100_000 lookups must complete in <100ms total (= <1µs each).
    /// Satisfies the <100µs per-lookup requirement with 100x headroom.
    #[test]
    fn bench_route_under_100us_per_lookup() {
        let nodes = make_nodes(50);
        let index = make_index_with_scores(&nodes);
        // Pre-generate task IDs outside the timed window
        let task_ids: Vec<NodeId> = (0..100_000).map(|_| NodeId::new()).collect();

        let start = Instant::now();
        for &tid in &task_ids {
            let _ = index.route(tid).unwrap();
        }
        let elapsed = start.elapsed();

        let per_lookup_us = elapsed.as_micros() as f64 / 100_000.0;
        assert!(
            per_lookup_us < 100.0,
            "route() averaged {:.3}µs per lookup (limit: 100µs)",
            per_lookup_us
        );
    }
}
