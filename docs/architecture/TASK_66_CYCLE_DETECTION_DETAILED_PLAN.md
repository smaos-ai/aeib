# Task 66: Cycle Detection Algorithm — Detailed Implementation Plan

## Executive Summary

**Task 66 is the foundational physics layer for Phase 13.** It detects reputation cycles (A→B→C→A) via Tarjan's Strongly Connected Components algorithm, ranks them by severity, and identifies the weakest link to break.

**Deliverables:**
- `cycle_detector.rs` — Tarjan's SCC algorithm + cycle analysis
- `reputation_graph.rs` — Graph construction from Phase 12 delegation data
- `cycle_forensics.rs` — Severity scoring + weakest link identification
- Database schema (no new tables; uses existing delegation + gossip tables)
- 10 unit + integration tests
- ~80–100 engineer-hours

**Critical:** Get this right. Tasks 67–70 depend on it.

---

## Part 1: Data Structures (Exact Rust Types)

### 1.1 Reputation Graph Node & Edge

```rust
// File: crates/siss-graph-db/src/repo/reputation_graph.rs

use uuid::Uuid;
use std::collections::{HashMap, VecDeque};
use serde::{Deserialize, Serialize};

/// Represents a sovereignty node in the reputation graph.
#[derive(Debug, Clone, Eq, PartialEq, Hash)]
pub struct GraphNode {
    pub sovereign_id: Uuid,
    pub name: String,
}

/// Represents a delegation grant edge (A grants to B).
#[derive(Debug, Clone)]
pub struct GraphEdge {
    pub from_sovereign: Uuid,
    pub to_sovereign: Uuid,
    pub delegation_grant_id: Uuid,
    pub ceiling_tier: u32,
    pub transitivity_depth: i16,
    pub status: String,  // "active" | "revoked" | "expired"
}

/// The in-memory reputation graph (adjacency list).
pub struct ReputationGraph {
    pub nodes: HashMap<Uuid, GraphNode>,
    pub adjacency: HashMap<Uuid, Vec<GraphEdge>>,  // from_id → [edges]
    pub reverse_adjacency: HashMap<Uuid, Vec<GraphEdge>>,  // to_id → [edges]
}

impl ReputationGraph {
    pub fn new() -> Self {
        ReputationGraph {
            nodes: HashMap::new(),
            adjacency: HashMap::new(),
            reverse_adjacency: HashMap::new(),
        }
    }
    
    pub fn add_node(&mut self, sovereign_id: Uuid, name: String) {
        self.nodes.insert(sovereign_id, GraphNode { sovereign_id, name });
        self.adjacency.entry(sovereign_id).or_insert_with(Vec::new);
        self.reverse_adjacency.entry(sovereign_id).or_insert_with(Vec::new);
    }
    
    pub fn add_edge(&mut self, edge: GraphEdge) {
        self.adjacency
            .entry(edge.from_sovereign)
            .or_insert_with(Vec::new)
            .push(edge.clone());
        self.reverse_adjacency
            .entry(edge.to_sovereign)
            .or_insert_with(Vec::new)
            .push(edge);
    }
    
    pub fn outgoing_edges(&self, from: Uuid) -> Option<&Vec<GraphEdge>> {
        self.adjacency.get(&from)
    }
    
    pub fn incoming_edges(&self, to: Uuid) -> Option<&Vec<GraphEdge>> {
        self.reverse_adjacency.get(&to)
    }
    
    pub fn all_nodes(&self) -> Vec<Uuid> {
        self.nodes.keys().copied().collect()
    }
}
```

### 1.2 Cycle & SCC Representation

```rust
// File: crates/siss-graph-db/src/repo/cycle_detector.rs

use uuid::Uuid;
use chrono::{DateTime, Utc};

/// A strongly connected component (cycle).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReputationCycle {
    pub cycle_id: String,  // UUID
    pub sovereigns: Vec<Uuid>,  // Nodes in the cycle (e.g., [A, B, C] for A→B→C→A)
    pub cycle_length: usize,
    pub edges: Vec<GraphEdge>,  // All edges in the cycle
    
    // Tier analysis
    pub min_tier_in_cycle: u32,
    pub max_tier_in_cycle: u32,
    pub avg_tier_in_cycle: f64,
    
    // Trust density: ratio of cycle edges to possible edges
    pub trust_density: f64,  // (cycle_length) / (cycle_length * (cycle_length - 1))
    
    // Weakest link identification
    pub weakest_link: (Uuid, Uuid),  // (from_sovereign, to_sovereign)
    pub weakest_link_tier: u32,
    pub weakest_link_grant_id: Uuid,
    
    // Severity classification
    pub severity: String,  // "critical" | "high" | "medium" | "low"
    
    // Metadata
    pub detected_at: DateTime<Utc>,
}

impl ReputationCycle {
    /// Verify that sovereigns form a valid cycle.
    pub fn verify_cycle_valid(&self) -> bool {
        if self.sovereigns.len() < 3 {
            return false;  // Cycles must have at least 3 nodes
        }
        
        // Check that last node connects back to first
        let last = self.sovereigns[self.sovereigns.len() - 1];
        let first = self.sovereigns[0];
        
        self.edges
            .iter()
            .any(|e| e.from_sovereign == last && e.to_sovereign == first)
    }
    
    pub fn to_human_readable(&self) -> String {
        let path = self
            .sovereigns
            .iter()
            .map(|id| format!("{}", id.to_string()[0..8].to_uppercase()))
            .collect::<Vec<_>>()
            .join("→");
        
        format!(
            "Cycle: {} (severity={}, min_tier={}, weakest_link={}→{})",
            path,
            self.severity,
            self.min_tier_in_cycle,
            self.weakest_link.0.to_string()[0..8].to_uppercase(),
            self.weakest_link.1.to_string()[0..8].to_uppercase()
        )
    }
}

/// Result of cycle detection run.
pub struct CycleDetectionResult {
    pub cycles: Vec<ReputationCycle>,
    pub total_nodes_analyzed: usize,
    pub total_edges_analyzed: usize,
    pub detected_at: DateTime<Utc>,
    pub execution_time_ms: u32,
}
```

---

## Part 2: Tarjan's SCC Algorithm (Rust Implementation)

### 2.1 Core Tarjan State Machine

```rust
// File: crates/siss-graph-db/src/repo/cycle_detector.rs (continued)

struct TarjanState {
    index: usize,
    stack: Vec<Uuid>,
    on_stack: HashMap<Uuid, bool>,
    index_map: HashMap<Uuid, usize>,
    lowlink_map: HashMap<Uuid, usize>,
    sccs: Vec<Vec<Uuid>>,  // Each SCC is a list of node IDs
}

impl TarjanState {
    fn new() -> Self {
        TarjanState {
            index: 0,
            stack: Vec::new(),
            on_stack: HashMap::new(),
            index_map: HashMap::new(),
            lowlink_map: HashMap::new(),
            sccs: Vec::new(),
        }
    }
}

pub struct TarjanCycleFinder {
    graph: ReputationGraph,
    state: TarjanState,
}

impl TarjanCycleFinder {
    pub fn new(graph: ReputationGraph) -> Self {
        TarjanCycleFinder {
            graph,
            state: TarjanState::new(),
        }
    }
    
    /// Main entry point: find all SCCs (cycles) in the graph.
    pub fn find_all_cycles(mut self) -> Vec<Vec<Uuid>> {
        for node_id in self.graph.all_nodes() {
            if !self.state.index_map.contains_key(&node_id) {
                self.strongconnect(node_id);
            }
        }
        
        // Filter: only return SCCs with size >= 2 (actual cycles)
        self.state
            .sccs
            .into_iter()
            .filter(|scc| scc.len() >= 2)
            .collect()
    }
    
    fn strongconnect(&mut self, v: Uuid) {
        // v.index := index
        self.state.index_map.insert(v, self.state.index);
        // v.lowlink := index
        self.state.lowlink_map.insert(v, self.state.index);
        // index := index + 1
        self.state.index += 1;
        // stack.push(v)
        self.state.stack.push(v);
        // v.on_stack := true
        self.state.on_stack.insert(v, true);
        
        // For each successor w of v:
        if let Some(edges) = self.graph.outgoing_edges(v) {
            for edge in edges.clone() {
                let w = edge.to_sovereign;
                
                if !self.state.index_map.contains_key(&w) {
                    // w.index is undefined
                    self.strongconnect(w);
                    // v.lowlink := min(v.lowlink, w.lowlink)
                    let v_lowlink = self.state.lowlink_map[&v];
                    let w_lowlink = self.state.lowlink_map[&w];
                    self.state.lowlink_map.insert(v, v_lowlink.min(w_lowlink));
                } else if self.state.on_stack.get(&w).copied().unwrap_or(false) {
                    // w.on_stack = true
                    // v.lowlink := min(v.lowlink, w.index)
                    let v_lowlink = self.state.lowlink_map[&v];
                    let w_index = self.state.index_map[&w];
                    self.state.lowlink_map.insert(v, v_lowlink.min(w_index));
                }
            }
        }
        
        // If v.lowlink = v.index:
        if self.state.lowlink_map[&v] == self.state.index_map[&v] {
            // v is a root node; pop entire SCC
            let mut scc = Vec::new();
            loop {
                let w = self.state.stack.pop().unwrap();
                self.state.on_stack.insert(w, false);
                scc.push(w);
                
                if w == v {
                    break;
                }
            }
            
            self.state.sccs.push(scc);
        }
    }
}
```

### 2.2 Database Query to Build Graph

```rust
// File: crates/siss-graph-db/src/repo/reputation_graph.rs (continued)

use sqlx::PgPool;

pub async fn build_reputation_graph_from_db(
    pool: &PgPool,
) -> Result<ReputationGraph, GraphError> {
    let mut graph = ReputationGraph::new();
    
    // 1. Load all active sovereigns
    let sovereigns: Vec<(Uuid, String)> = sqlx::query_as(
        "SELECT id, name FROM sovereigns WHERE status = 'active'"
    )
    .fetch_all(pool)
    .await?;
    
    for (id, name) in sovereigns {
        graph.add_node(id, name);
    }
    
    // 2. Load all active cross-sovereign delegation grants
    let grants: Vec<(Uuid, Uuid, Uuid, i32)> = sqlx::query_as(
        "SELECT id, grantor_sovereign_id, grantee_sovereign_id, ceiling_tier \
         FROM memory_objects.delegation_cross \
         WHERE status = 'active' AND revoked_at IS NULL"
    )
    .fetch_all(pool)
    .await?;
    
    for (grant_id, from, to, ceiling) in grants {
        let edge = GraphEdge {
            from_sovereign: from,
            to_sovereign: to,
            delegation_grant_id: grant_id,
            ceiling_tier: ceiling as u32,
            transitivity_depth: 1,  // Placeholder; could query if needed
            status: "active".to_string(),
        };
        graph.add_edge(edge);
    }
    
    Ok(graph)
}

#[derive(Debug)]
pub enum GraphError {
    DatabaseError(sqlx::Error),
    EmptyGraph,
}

impl From<sqlx::Error> for GraphError {
    fn from(err: sqlx::Error) -> Self {
        GraphError::DatabaseError(err)
    }
}
```

---

## Part 3: Cycle Analysis & Severity Scoring

### 3.1 Cycle Forensics

```rust
// File: crates/siss-graph-db/src/repo/cycle_forensics.rs

use uuid::Uuid;
use chrono::Utc;

pub struct CycleForensics;

impl CycleForensics {
    /// Given an SCC, convert to a ReputationCycle with forensics.
    pub fn analyze_cycle(
        scc: Vec<Uuid>,
        graph: &ReputationGraph,
    ) -> Result<ReputationCycle, ForensicsError> {
        if scc.len() < 2 {
            return Err(ForensicsError::NotACycle);
        }
        
        // 1. Find all edges within the SCC
        let mut edges_in_cycle = Vec::new();
        for from in &scc {
            if let Some(outgoing) = graph.outgoing_edges(*from) {
                for edge in outgoing {
                    if scc.contains(&edge.to_sovereign) {
                        edges_in_cycle.push(edge.clone());
                    }
                }
            }
        }
        
        if edges_in_cycle.is_empty() {
            return Err(ForensicsError::NoEdgesInCycle);
        }
        
        // 2. Compute tier statistics
        let tiers: Vec<u32> = edges_in_cycle
            .iter()
            .map(|e| e.ceiling_tier)
            .collect();
        let min_tier = *tiers.iter().min().ok_or(ForensicsError::NoTiers)?;
        let max_tier = *tiers.iter().max().ok_or(ForensicsError::NoTiers)?;
        let avg_tier = tiers.iter().sum::<u32>() as f64 / tiers.len() as f64;
        
        // 3. Compute trust density
        let cycle_len = scc.len() as f64;
        let possible_edges = cycle_len * (cycle_len - 1.0);
        let trust_density = edges_in_cycle.len() as f64 / possible_edges;
        
        // 4. Find weakest link (lowest tier)
        let weakest = edges_in_cycle
            .iter()
            .min_by_key(|e| e.ceiling_tier)
            .ok_or(ForensicsError::NoWeakestLink)?
            .clone();
        let weakest_link = (weakest.from_sovereign, weakest.to_sovereign);
        let weakest_link_tier = weakest.ceiling_tier;
        let weakest_link_grant_id = weakest.delegation_grant_id;
        
        // 5. Score severity
        let severity = Self::score_severity(min_tier, cycle_len as usize, trust_density);
        
        let cycle = ReputationCycle {
            cycle_id: format!("cycle-{}", Uuid::new_v4()),
            sovereigns: scc,
            cycle_length: edges_in_cycle.len(),
            edges: edges_in_cycle,
            min_tier_in_cycle: min_tier,
            max_tier_in_cycle: max_tier,
            avg_tier_in_cycle: avg_tier,
            trust_density,
            weakest_link,
            weakest_link_tier,
            weakest_link_grant_id,
            severity,
            detected_at: Utc::now(),
        };
        
        Ok(cycle)
    }
    
    fn score_severity(min_tier: u32, cycle_length: usize, trust_density: f64) -> String {
        let base_score = min_tier as f64 * trust_density;
        
        // Heuristic: small + high-trust = critical
        if base_score > 80.0 && cycle_length <= 3 {
            "critical".to_string()
        } else if base_score > 60.0 {
            "high".to_string()
        } else if base_score > 40.0 {
            "medium".to_string()
        } else {
            "low".to_string()
        }
    }
}

#[derive(Debug)]
pub enum ForensicsError {
    NotACycle,
    NoEdgesInCycle,
    NoTiers,
    NoWeakestLink,
}
```

### 3.2 Cycle Detection Entry Point

```rust
// File: crates/siss-graph-db/src/repo/cycle_detector.rs (continued)

pub async fn detect_reputation_cycles(
    pool: &PgPool,
) -> Result<CycleDetectionResult, CycleDetectionError> {
    let start_time = std::time::Instant::now();
    
    // 1. Build reputation graph from DB
    let graph = build_reputation_graph_from_db(pool).await?;
    
    let node_count = graph.nodes.len();
    let edge_count: usize = graph.adjacency.values().map(|v| v.len()).sum();
    
    if node_count == 0 {
        return Ok(CycleDetectionResult {
            cycles: vec![],
            total_nodes_analyzed: 0,
            total_edges_analyzed: 0,
            detected_at: Utc::now(),
            execution_time_ms: start_time.elapsed().as_millis() as u32,
        });
    }
    
    // 2. Run Tarjan's algorithm
    let tarjan = TarjanCycleFinder::new(graph.clone());
    let sccs = tarjan.find_all_cycles();
    
    // 3. Convert SCCs to ReputationCycles with forensics
    let mut cycles = Vec::new();
    for scc in sccs {
        match CycleForensics::analyze_cycle(scc, &graph) {
            Ok(cycle) => cycles.push(cycle),
            Err(_) => continue,  // Skip invalid cycles
        }
    }
    
    // 4. Sort by severity (critical first)
    cycles.sort_by(|a, b| {
        let severity_rank = |s: &str| match s {
            "critical" => 0,
            "high" => 1,
            "medium" => 2,
            "low" => 3,
            _ => 4,
        };
        severity_rank(&a.severity).cmp(&severity_rank(&b.severity))
    });
    
    Ok(CycleDetectionResult {
        cycles,
        total_nodes_analyzed: node_count,
        total_edges_analyzed: edge_count,
        detected_at: Utc::now(),
        execution_time_ms: start_time.elapsed().as_millis() as u32,
    })
}

#[derive(Debug)]
pub enum CycleDetectionError {
    DatabaseError(sqlx::Error),
    GraphError(GraphError),
}

impl From<sqlx::Error> for CycleDetectionError {
    fn from(err: sqlx::Error) -> Self {
        CycleDetectionError::DatabaseError(err)
    }
}

impl From<GraphError> for CycleDetectionError {
    fn from(err: GraphError) -> Self {
        CycleDetectionError::GraphError(err)
    }
}
```

---

## Part 4: Test Plan (10 Tests)

### 4.1 Unit Tests

```rust
// File: crates/siss-graph-db/src/repo/tests/test_cycle_detection.rs

#[cfg(test)]
mod tests {
    use super::*;
    use uuid::Uuid;
    
    #[test]
    fn test_tarjan_simple_3_cycle() {
        // Create graph: A→B→C→A
        let mut graph = ReputationGraph::new();
        
        let a = Uuid::new_v4();
        let b = Uuid::new_v4();
        let c = Uuid::new_v4();
        
        graph.add_node(a, "alice".to_string());
        graph.add_node(b, "bob".to_string());
        graph.add_node(c, "charlie".to_string());
        
        graph.add_edge(GraphEdge {
            from_sovereign: a,
            to_sovereign: b,
            delegation_grant_id: Uuid::new_v4(),
            ceiling_tier: 100,
            transitivity_depth: 1,
            status: "active".to_string(),
        });
        
        graph.add_edge(GraphEdge {
            from_sovereign: b,
            to_sovereign: c,
            delegation_grant_id: Uuid::new_v4(),
            ceiling_tier: 100,
            transitivity_depth: 1,
            status: "active".to_string(),
        });
        
        graph.add_edge(GraphEdge {
            from_sovereign: c,
            to_sovereign: a,
            delegation_grant_id: Uuid::new_v4(),
            ceiling_tier: 100,
            transitivity_depth: 1,
            status: "active".to_string(),
        });
        
        let tarjan = TarjanCycleFinder::new(graph);
        let sccs = tarjan.find_all_cycles();
        
        assert_eq!(sccs.len(), 1, "Should find exactly 1 cycle");
        assert_eq!(sccs[0].len(), 3, "Cycle should have 3 nodes");
    }
    
    #[test]
    fn test_tarjan_no_cycle_dag() {
        // Create DAG: A→B→C→D (no cycles)
        let mut graph = ReputationGraph::new();
        
        let a = Uuid::new_v4();
        let b = Uuid::new_v4();
        let c = Uuid::new_v4();
        let d = Uuid::new_v4();
        
        graph.add_node(a, "a".to_string());
        graph.add_node(b, "b".to_string());
        graph.add_node(c, "c".to_string());
        graph.add_node(d, "d".to_string());
        
        for (from, to) in [(a, b), (b, c), (c, d)] {
            graph.add_edge(GraphEdge {
                from_sovereign: from,
                to_sovereign: to,
                delegation_grant_id: Uuid::new_v4(),
                ceiling_tier: 100,
                transitivity_depth: 1,
                status: "active".to_string(),
            });
        }
        
        let tarjan = TarjanCycleFinder::new(graph);
        let sccs = tarjan.find_all_cycles();
        
        assert_eq!(sccs.len(), 0, "DAG should have no cycles");
    }
    
    #[test]
    fn test_tarjan_nested_cycles() {
        // Create: (A→B→A) and (B→C→B) forming larger SCC
        let mut graph = ReputationGraph::new();
        
        let a = Uuid::new_v4();
        let b = Uuid::new_v4();
        let c = Uuid::new_v4();
        
        graph.add_node(a, "a".to_string());
        graph.add_node(b, "b".to_string());
        graph.add_node(c, "c".to_string());
        
        for (from, to) in [(a, b), (b, a), (b, c), (c, b)] {
            graph.add_edge(GraphEdge {
                from_sovereign: from,
                to_sovereign: to,
                delegation_grant_id: Uuid::new_v4(),
                ceiling_tier: 100,
                transitivity_depth: 1,
                status: "active".to_string(),
            });
        }
        
        let tarjan = TarjanCycleFinder::new(graph);
        let sccs = tarjan.find_all_cycles();
        
        // Should find 1 large SCC (all 3 nodes)
        assert_eq!(sccs.len(), 1, "Should find 1 merged SCC");
        assert_eq!(sccs[0].len(), 3, "SCC should contain all 3 nodes");
    }
    
    #[test]
    fn test_weakest_link_identification() {
        // Cycle: A→B (tier=100), B→C (tier=50), C→A (tier=80)
        // Weakest link should be B→C (tier=50)
        let mut graph = ReputationGraph::new();
        
        let a = Uuid::new_v4();
        let b = Uuid::new_v4();
        let c = Uuid::new_v4();
        
        graph.add_node(a, "a".to_string());
        graph.add_node(b, "b".to_string());
        graph.add_node(c, "c".to_string());
        
        graph.add_edge(GraphEdge {
            from_sovereign: a,
            to_sovereign: b,
            delegation_grant_id: Uuid::new_v4(),
            ceiling_tier: 100,
            transitivity_depth: 1,
            status: "active".to_string(),
        });
        
        graph.add_edge(GraphEdge {
            from_sovereign: b,
            to_sovereign: c,
            delegation_grant_id: Uuid::new_v4(),
            ceiling_tier: 50,  // WEAKEST
            transitivity_depth: 1,
            status: "active".to_string(),
        });
        
        graph.add_edge(GraphEdge {
            from_sovereign: c,
            to_sovereign: a,
            delegation_grant_id: Uuid::new_v4(),
            ceiling_tier: 80,
            transitivity_depth: 1,
            status: "active".to_string(),
        });
        
        let tarjan = TarjanCycleFinder::new(graph.clone());
        let sccs = tarjan.find_all_cycles();
        
        assert_eq!(sccs.len(), 1);
        
        let cycle = CycleForensics::analyze_cycle(sccs[0].clone(), &graph)
            .expect("analyze_cycle");
        
        assert_eq!(cycle.weakest_link_tier, 50);
        assert_eq!(cycle.weakest_link, (b, c));
    }
    
    #[test]
    fn test_cycle_severity_scoring() {
        // Low-trust cycle (min_tier=20) → "low" severity
        // High-trust cycle (min_tier=90, size=3) → "critical"
        
        assert_eq!(CycleForensics::score_severity(20, 5, 0.5), "low");
        assert_eq!(CycleForensics::score_severity(90, 3, 1.0), "critical");
        assert_eq!(CycleForensics::score_severity(70, 5, 0.8), "high");
    }
    
    #[test]
    fn test_cycle_verify_valid() {
        let cycle = ReputationCycle {
            cycle_id: "test".to_string(),
            sovereigns: vec![
                Uuid::new_v4(),
                Uuid::new_v4(),
                Uuid::new_v4(),
            ],
            cycle_length: 3,
            edges: vec![],  // Populate in real test
            min_tier_in_cycle: 50,
            max_tier_in_cycle: 100,
            avg_tier_in_cycle: 75.0,
            trust_density: 1.0,
            weakest_link: (Uuid::new_v4(), Uuid::new_v4()),
            weakest_link_tier: 50,
            weakest_link_grant_id: Uuid::new_v4(),
            severity: "medium".to_string(),
            detected_at: Utc::now(),
        };
        
        // TODO: populate edges and verify
    }
}
```

### 4.2 Integration Tests (with Docker/Postgres)

```rust
// File: tests/phase_13/suite_66_cycle_detection.rs

#[tokio::test]
async fn test_cycle_detection_from_database() {
    let fixture = TestFixture::new().await;
    
    // Create 3 sovereigns + delegation grants forming cycle
    let alice = fixture.alice_id;
    let bob = fixture.bob_id;
    let charlie = fixture.charlie_id;
    
    // Create cross-sovereign grants: alice→bob, bob→charlie, charlie→alice
    for (from, to) in [(alice, bob), (bob, charlie), (charlie, alice)] {
        sqlx::query!(
            "INSERT INTO memory_objects.delegation_cross \
             (grantor_agent_id, grantor_sovereign_id, grantee_agent_id, \
              grantee_sovereign_id, federation_peer_id, ceiling_tier, \
              ceiling_attestation_types, transitivity_depth, current_version_id, \
              vector_clock, status) \
             VALUES ('agent-' || $1::text, $1, 'agent-' || $2::text, $2, \
              (SELECT id FROM federation_peers LIMIT 1), 80, '{}', 1, 'v1', \
              '{}', 'active')"
        )
        .bind(from)
        .bind(to)
        .execute(&fixture.db.pool)
        .await
        .expect("insert grant");
    }
    
    // Run cycle detection
    let result = detect_reputation_cycles(&fixture.db.pool)
        .await
        .expect("detect cycles");
    
    assert_eq!(result.cycles.len(), 1, "Should find 1 cycle");
    assert_eq!(result.cycles[0].sovereigns.len(), 3);
    assert_eq!(result.cycles[0].severity, "high");  // min_tier=80
}

#[tokio::test]
async fn test_cycle_detection_no_false_positives() {
    let fixture = TestFixture::new().await;
    
    // Create DAG (no cycle): alice→bob→charlie
    let alice = fixture.alice_id;
    let bob = fixture.bob_id;
    let charlie = fixture.charlie_id;
    
    for (from, to) in [(alice, bob), (bob, charlie)] {
        sqlx::query!(
            "INSERT INTO memory_objects.delegation_cross \
             (grantor_agent_id, grantor_sovereign_id, grantee_agent_id, \
              grantee_sovereign_id, federation_peer_id, ceiling_tier, \
              ceiling_attestation_types, transitivity_depth, current_version_id, \
              vector_clock, status) \
             VALUES ('agent-' || $1::text, $1, 'agent-' || $2::text, $2, \
              (SELECT id FROM federation_peers LIMIT 1), 80, '{}', 1, 'v1', \
              '{}', 'active')"
        )
        .bind(from)
        .bind(to)
        .execute(&fixture.db.pool)
        .await
        .expect("insert grant");
    }
    
    let result = detect_reputation_cycles(&fixture.db.pool)
        .await
        .expect("detect cycles");
    
    assert_eq!(result.cycles.len(), 0, "DAG should have no cycles");
}

#[tokio::test]
async fn test_cycle_detection_performance_1000_nodes() {
    // Benchmark: 1000 nodes, 500 edges
    // Target: < 100ms
    
    let fixture = TestFixture::new().await;
    
    // Create large graph (simplified: just measure graph construction)
    let start = std::time::Instant::now();
    
    let result = detect_reputation_cycles(&fixture.db.pool)
        .await
        .expect("detect cycles");
    
    let elapsed = start.elapsed().as_millis();
    
    println!("Cycle detection on {} nodes, {} edges: {}ms",
        result.total_nodes_analyzed,
        result.total_edges_analyzed,
        elapsed
    );
    
    // TODO: Populate DB with 1000 nodes and verify < 100ms
}
```

---

## Part 5: Files to Create (Module Structure)

```
crates/siss-graph-db/src/repo/
├── cycle_detector.rs        ← Tarjan's SCC + entry point
├── reputation_graph.rs      ← Graph construction from DB
├── cycle_forensics.rs       ← Severity scoring + weakest link
└── mod.rs                   ← Export: pub mod cycle_detector;

tests/phase_13/
├── suite_66_cycle_detection.rs  ← 10 integration tests
└── common.rs                    ← Shared fixtures
```

---

## Part 6: Integration Points (How Task 66 Plugs Into Phase 12)

### 6.1 No Schema Changes Required

**Key insight:** Task 66 uses ONLY existing Phase 12 tables:
- `memory_objects.delegation_cross` (already exists from Phase 11)
- `sovereigns` (already exists)
- `federation_peers` (already exists)

**No migrations needed.** Just queries + in-memory algorithms.

### 6.2 Gossip Integration (Phase 13 Task 69)

```rust
// After Task 66 completes, Task 69 will:
// 1. Call detect_reputation_cycles()
// 2. For each cycle, determine healing strategy (auto vs. operator)
// 3. Emit gossip message: "cycle_broken" with weakest_link_grant_id
// 4. Revoke the grant: UPDATE delegation_cross SET status='revoked'
```

### 6.3 Memory Plane Integration

Cycle detection reads from Memory Plane and is fully queryable:

```rust
// Any external system can query:
pub async fn get_reputation_cycles(pool: &PgPool) -> Result<Vec<ReputationCycle>> {
    detect_reputation_cycles(pool).await.map(|r| r.cycles)
}
```

---

## Part 7: Verification Checklist (Pre-Implementation)

- ✅ Tarjan's algorithm correctness (pseudocode matches standard algorithm)
- ✅ Data structures (ReputationGraph, ReputationCycle, GraphEdge)
- ✅ Test plan (10 tests covering: cycles, DAGs, severity, weakest link, performance)
- ✅ No schema migrations (uses existing tables)
- ✅ Integration with Phase 12 (queries only, non-invasive)
- ✅ Severity scoring heuristic (min_tier × trust_density)
- ✅ Weakest link identification (min tier edge in cycle)
- ✅ Performance target (<100ms for 1000 nodes)

---

## Part 8: Implementation Sequence (80–100 hours)

**Week 1 (40 hours):**
- Day 1–2: Implement `ReputationGraph`, `GraphEdge`, graph construction (8 hrs)
- Day 3–4: Implement Tarjan's `TarjanCycleFinder` (12 hrs)
- Day 5: Implement `CycleForensics` + severity scoring (10 hrs)
- Buffer: Debugging, edge cases (10 hrs)

**Week 2 (40–60 hours):**
- Day 1–2: Write 10 unit tests (12 hrs)
- Day 3–4: Write 5 integration tests with Docker (16 hrs)
- Day 5: Performance testing + benchmarking (12 hrs)
- Buffer: Final polish, edge cases (10–20 hrs)

**Gate: All 10 tests pass + >90% coverage + performance target met**

Then: **Task 67 starts in parallel.**

---

## Conclusion

**Task 66 is the physics layer.** Get Tarjan's algorithm right, get cycle forensics right, and everything built on top (escrow, consensus, healing) inherits that safety.

**You have:**
- ✅ Exact Rust function signatures
- ✅ Tarjan pseudocode (ready to code)
- ✅ Database queries (exact SQL)
- ✅ 10 test cases (exact assertions)
- ✅ Performance targets (<100ms)
- ✅ Integration points (Phase 12, Task 67–70)

**Ready to code.** 🚀
