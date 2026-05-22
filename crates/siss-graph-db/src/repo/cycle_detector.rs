use crate::repo::cycle_forensics::ReputationCycle;
/// Phase 13: Cycle Detection via Tarjan's Strongly Connected Components
/// Detects reputation cycles (A→B→C→A) and ranks by severity.
use crate::repo::reputation_graph::ReputationGraph;
use chrono::{DateTime, Utc};
use sqlx::PgPool;
use std::collections::HashMap;
use uuid::Uuid;

/// Tarjan's algorithm state machine for finding strongly connected components.
struct TarjanState {
    index: usize,
    stack: Vec<Uuid>,
    on_stack: HashMap<Uuid, bool>,
    index_map: HashMap<Uuid, usize>,
    lowlink_map: HashMap<Uuid, usize>,
    sccs: Vec<Vec<Uuid>>, // Each SCC is a list of node IDs
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

/// Tarjan's SCC algorithm finder.
pub struct TarjanCycleFinder {
    graph: ReputationGraph,
    state: TarjanState,
}

impl TarjanCycleFinder {
    /// Create a new Tarjan finder with the given graph.
    pub fn new(graph: ReputationGraph) -> Self {
        TarjanCycleFinder {
            graph,
            state: TarjanState::new(),
        }
    }

    /// Main entry point: find all strongly connected components (cycles) in the graph.
    /// Returns list of SCCs with size >= 2 (actual cycles, not single nodes).
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

    /// Tarjan's strongconnect algorithm (recursive depth-first search).
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
                    // w.index is undefined → recurse
                    self.strongconnect(w);
                    // v.lowlink := min(v.lowlink, w.lowlink)
                    let v_lowlink = self.state.lowlink_map[&v];
                    let w_lowlink = self.state.lowlink_map[&w];
                    self.state.lowlink_map.insert(v, v_lowlink.min(w_lowlink));
                } else if self.state.on_stack.get(&w).copied().unwrap_or(false) {
                    // w.on_stack = true → back edge
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
                let w = self.state.stack.pop().expect("stack non-empty");
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

/// Result of a cycle detection run.
#[derive(Debug, Clone)]
pub struct CycleDetectionResult {
    pub cycles: Vec<ReputationCycle>,
    pub total_nodes_analyzed: usize,
    pub total_edges_analyzed: usize,
    pub detected_at: DateTime<Utc>,
    pub execution_time_ms: u32,
}

/// Errors that can occur during cycle detection.
#[derive(Debug)]
pub enum CycleDetectionError {
    DatabaseError(sqlx::Error),
    GraphError(crate::repo::reputation_graph::GraphError),
    ForensicsError(String),
}

impl std::fmt::Display for CycleDetectionError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            CycleDetectionError::DatabaseError(e) => write!(f, "Database error: {}", e),
            CycleDetectionError::GraphError(e) => write!(f, "Graph error: {}", e),
            CycleDetectionError::ForensicsError(e) => write!(f, "Forensics error: {}", e),
        }
    }
}

impl std::error::Error for CycleDetectionError {}

impl From<sqlx::Error> for CycleDetectionError {
    fn from(err: sqlx::Error) -> Self {
        CycleDetectionError::DatabaseError(err)
    }
}

impl From<crate::repo::reputation_graph::GraphError> for CycleDetectionError {
    fn from(err: crate::repo::reputation_graph::GraphError) -> Self {
        CycleDetectionError::GraphError(err)
    }
}

/// Detect all reputation cycles in the database.
///
/// High-level entry point for cycle detection. Orchestrates:
/// 1. Graph construction from Phase 12 delegation data
/// 2. Tarjan's SCC algorithm (O(V+E))
/// 3. Cycle forensics (severity, weakest link)
/// 4. Sorting by severity (critical first)
pub async fn detect_reputation_cycles(
    pool: &PgPool,
) -> Result<CycleDetectionResult, CycleDetectionError> {
    let start_time = std::time::Instant::now();

    // 1. Build reputation graph from DB
    let graph = crate::repo::reputation_graph::build_reputation_graph_from_db(pool).await?;

    let node_count = graph.node_count();
    let edge_count = graph.edge_count();

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
        match ReputationCycle::analyze_cycle(scc, &graph) {
            Ok(cycle) => cycles.push(cycle),
            Err(e) => {
                eprintln!("Warning: Failed to analyze cycle: {}", e);
                continue;
            }
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::repo::reputation_graph::GraphEdge;

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
        // Create: (A↔B) and (B↔C) forming larger SCC
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

    // ============================================================================
    // Integration Tests (requires Docker/Postgres)
    // ============================================================================

    #[cfg(test)]
    mod integration_tests {
        use super::*;
        use testcontainers::{GenericImage, ImageExt, core::WaitFor, runners::AsyncRunner};

        async fn setup_postgres() -> (testcontainers::ContainerAsync<GenericImage>, PgPool) {
            let container = GenericImage::new("postgres", "16")
                .with_wait_for(WaitFor::message_on_stderr(
                    "database system is ready to accept connections",
                ))
                .with_env_var("POSTGRES_PASSWORD", "postgres")
                .with_env_var("POSTGRES_DB", "siss_test")
                .start()
                .await
                .expect("postgres started");

            let port = container.get_host_port_ipv4(5432).await.unwrap();
            let url = format!("postgres://postgres:postgres@127.0.0.1:{port}/siss_test");
            let pool = PgPool::connect(&url).await.expect("pool connect");
            crate::migrations::run_all(&pool).await.expect("migrations");
            (container, pool)
        }

        #[tokio::test]
        async fn test_cycle_detection_from_actual_delegation_table() {
            let (_container, pool) = setup_postgres().await;

            // Create 3 sovereigns
            let a = Uuid::new_v4();
            let b = Uuid::new_v4();
            let c = Uuid::new_v4();

            let pkey = "-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAI...\n-----END PUBLIC KEY-----";

            sqlx::query(
                "INSERT INTO sovereigns (id, name, public_key_pem, status, endpoint_url) VALUES ($1, $2, $3, $4, $5)",
            )
            .bind(a)
            .bind("alice")
            .bind(pkey)
            .bind("active")
            .bind("http://alice.local")
            .execute(&pool)
            .await
            .expect("insert alice");

            sqlx::query(
                "INSERT INTO sovereigns (id, name, public_key_pem, status, endpoint_url) VALUES ($1, $2, $3, $4, $5)",
            )
            .bind(b)
            .bind("bob")
            .bind(pkey)
            .bind("active")
            .bind("http://bob.local")
            .execute(&pool)
            .await
            .expect("insert bob");

            sqlx::query(
                "INSERT INTO sovereigns (id, name, public_key_pem, status, endpoint_url) VALUES ($1, $2, $3, $4, $5)",
            )
            .bind(c)
            .bind("charlie")
            .bind(pkey)
            .bind("active")
            .bind("http://charlie.local")
            .execute(&pool)
            .await
            .expect("insert charlie");

            // Insert federation peers for each directed pair
            let peer_ab = Uuid::new_v4();
            sqlx::query(
                "INSERT INTO federation_peers (id, sovereign_a_id, sovereign_b_id, max_admitted_tier, granted_attestation_types) VALUES ($1, $2, $3, $4, $5)"
            )
            .bind(peer_ab).bind(a).bind(b).bind(100i16).bind(vec!["test"])
            .execute(&pool).await.expect("insert peer a-b");

            let peer_bc = Uuid::new_v4();
            sqlx::query(
                "INSERT INTO federation_peers (id, sovereign_a_id, sovereign_b_id, max_admitted_tier, granted_attestation_types) VALUES ($1, $2, $3, $4, $5)"
            )
            .bind(peer_bc).bind(b).bind(c).bind(100i16).bind(vec!["test"])
            .execute(&pool).await.expect("insert peer b-c");

            let peer_ca = Uuid::new_v4();
            sqlx::query(
                "INSERT INTO federation_peers (id, sovereign_a_id, sovereign_b_id, max_admitted_tier, granted_attestation_types) VALUES ($1, $2, $3, $4, $5)"
            )
            .bind(peer_ca).bind(c).bind(a).bind(100i16).bind(vec!["test"])
            .execute(&pool).await.expect("insert peer c-a");

            // Create cross-sovereign delegation cycle: A→B→C→A
            let grant_ab = Uuid::new_v4();
            let grant_bc = Uuid::new_v4();
            let grant_ca = Uuid::new_v4();

            sqlx::query(
                "INSERT INTO cross_sovereign_delegation_grants (id, grantor_sovereign_id, grantee_sovereign_id, grantor_agent_id, grantee_agent_id, federation_peer_id, ceiling_tier, ceiling_attestation_types, transitivity_depth, status, grant_signature) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)"
            )
            .bind(grant_ab)
            .bind(a)
            .bind(b)
            .bind("agent_a")
            .bind("agent_b")
            .bind(peer_ab)
            .bind(100i16)
            .bind(vec!["test"])
            .bind(1i16)
            .bind("active")
            .bind("sig1")
            .execute(&pool)
            .await
            .expect("insert grant A→B");

            sqlx::query(
                "INSERT INTO cross_sovereign_delegation_grants (id, grantor_sovereign_id, grantee_sovereign_id, grantor_agent_id, grantee_agent_id, federation_peer_id, ceiling_tier, ceiling_attestation_types, transitivity_depth, status, grant_signature) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)"
            )
            .bind(grant_bc)
            .bind(b)
            .bind(c)
            .bind("agent_b")
            .bind("agent_c")
            .bind(peer_bc)
            .bind(100i16)
            .bind(vec!["test"])
            .bind(1i16)
            .bind("active")
            .bind("sig2")
            .execute(&pool)
            .await
            .expect("insert grant B→C");

            sqlx::query(
                "INSERT INTO cross_sovereign_delegation_grants (id, grantor_sovereign_id, grantee_sovereign_id, grantor_agent_id, grantee_agent_id, federation_peer_id, ceiling_tier, ceiling_attestation_types, transitivity_depth, status, grant_signature) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)"
            )
            .bind(grant_ca)
            .bind(c)
            .bind(a)
            .bind("agent_c")
            .bind("agent_a")
            .bind(peer_ca)
            .bind(100i16)
            .bind(vec!["test"])
            .bind(1i16)
            .bind("active")
            .bind("sig3")
            .execute(&pool)
            .await
            .expect("insert grant C→A");

            // Run cycle detection
            let result = detect_reputation_cycles(&pool)
                .await
                .expect("detect cycles");

            assert_eq!(result.cycles.len(), 1, "Should detect exactly 1 cycle");
            assert_eq!(result.total_nodes_analyzed, 3, "Should analyze 3 nodes");
            assert_eq!(result.total_edges_analyzed, 3, "Should analyze 3 edges");
            assert!(
                result.execution_time_ms < 500,
                "Execution should complete in <500ms"
            );
        }

        #[tokio::test]
        async fn test_cycle_detection_empty_graph() {
            let (_container, pool) = setup_postgres().await;

            // No sovereigns inserted, so graph is empty
            let result = detect_reputation_cycles(&pool)
                .await
                .expect("detect cycles on empty graph");

            assert_eq!(result.cycles.len(), 0, "Empty graph should have no cycles");
            assert_eq!(result.total_nodes_analyzed, 0, "No nodes analyzed");
            assert_eq!(result.total_edges_analyzed, 0, "No edges analyzed");
        }

        #[tokio::test]
        async fn test_cycle_detection_no_false_positives_dag() {
            let (_container, pool) = setup_postgres().await;

            // Create 5 sovereigns in a DAG (no cycles): A→B→C→D→E
            let sovereigns: Vec<Uuid> = (0..5).map(|_| Uuid::new_v4()).collect();
            let pkey = "-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAI...\n-----END PUBLIC KEY-----";

            for (i, sid) in sovereigns.iter().enumerate() {
                sqlx::query(
                    "INSERT INTO sovereigns (id, name, public_key_pem, status, endpoint_url) VALUES ($1, $2, $3, $4, $5)"
                )
                .bind(sid)
                .bind(format!("s{}", i))
                .bind(pkey)
                .bind("active")
                .bind(format!("http://s{}.local", i))
                .execute(&pool)
                .await
                .expect("insert sovereign");
            }

            // Create federation peers for chain 0→1→2→3→4
            let mut peer_ids: Vec<Uuid> = Vec::new();
            for i in 0..4 {
                let peer_id = Uuid::new_v4();
                sqlx::query(
                    "INSERT INTO federation_peers (id, sovereign_a_id, sovereign_b_id, max_admitted_tier, granted_attestation_types) VALUES ($1, $2, $3, $4, $5)"
                )
                .bind(peer_id)
                .bind(sovereigns[i])
                .bind(sovereigns[i + 1])
                .bind(100i16)
                .bind(vec!["test"])
                .execute(&pool).await.expect("insert peer");
                peer_ids.push(peer_id);
            }

            // Create chain: 0→1→2→3→4 (no cycles)
            for i in 0..4 {
                sqlx::query(
                    "INSERT INTO cross_sovereign_delegation_grants (id, grantor_sovereign_id, grantee_sovereign_id, grantor_agent_id, grantee_agent_id, federation_peer_id, ceiling_tier, ceiling_attestation_types, transitivity_depth, status, grant_signature) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)"
                )
                .bind(Uuid::new_v4())
                .bind(sovereigns[i])
                .bind(sovereigns[i + 1])
                .bind(format!("agent_{}", i))
                .bind(format!("agent_{}", i + 1))
                .bind(peer_ids[i])
                .bind(100i16)
                .bind(vec!["test"])
                .bind(1i16)
                .bind("active")
                .bind("sig")
                .execute(&pool)
                .await
                .expect("insert edge");
            }

            let result = detect_reputation_cycles(&pool)
                .await
                .expect("detect cycles in DAG");

            assert_eq!(result.cycles.len(), 0, "DAG should have no cycles");
            assert_eq!(result.total_nodes_analyzed, 5, "Should analyze all 5 nodes");
            assert_eq!(result.total_edges_analyzed, 4, "Should analyze all 4 edges");
        }

        #[tokio::test]
        async fn test_cycle_detection_performance_many_nodes() {
            let (_container, pool) = setup_postgres().await;

            let node_count = 50; // Large enough to test performance, small enough for test speed

            // Create many sovereigns
            let sovereigns: Vec<Uuid> = (0..node_count)
                .map(|i| {
                    let id = Uuid::new_v4();
                    // Insert synchronously in a loop (simplified)
                    id
                })
                .collect();

            let pkey = "-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAI...\n-----END PUBLIC KEY-----";

            // Insert sovereigns
            for (i, sid) in sovereigns.iter().enumerate() {
                sqlx::query(
                    "INSERT INTO sovereigns (id, name, public_key_pem, status, endpoint_url) VALUES ($1, $2, $3, $4, $5)"
                )
                .bind(sid)
                .bind(format!("s{}", i))
                .bind(pkey)
                .bind("active")
                .bind(format!("http://s{}.local", i))
                .execute(&pool)
                .await
                .expect("insert sovereign");
            }

            // Create federation peers for the cycle
            let peer_01 = Uuid::new_v4();
            sqlx::query(
                "INSERT INTO federation_peers (id, sovereign_a_id, sovereign_b_id, max_admitted_tier, granted_attestation_types) VALUES ($1, $2, $3, $4, $5)"
            )
            .bind(peer_01).bind(sovereigns[0]).bind(sovereigns[1]).bind(100i16).bind(vec!["test"])
            .execute(&pool).await.expect("insert peer 0-1");

            let peer_12 = Uuid::new_v4();
            sqlx::query(
                "INSERT INTO federation_peers (id, sovereign_a_id, sovereign_b_id, max_admitted_tier, granted_attestation_types) VALUES ($1, $2, $3, $4, $5)"
            )
            .bind(peer_12).bind(sovereigns[1]).bind(sovereigns[2]).bind(100i16).bind(vec!["test"])
            .execute(&pool).await.expect("insert peer 1-2");

            let peer_20 = Uuid::new_v4();
            sqlx::query(
                "INSERT INTO federation_peers (id, sovereign_a_id, sovereign_b_id, max_admitted_tier, granted_attestation_types) VALUES ($1, $2, $3, $4, $5)"
            )
            .bind(peer_20).bind(sovereigns[2]).bind(sovereigns[0]).bind(100i16).bind(vec!["test"])
            .execute(&pool).await.expect("insert peer 2-0");

            // Create a simple cycle among 3 nodes, rest are disconnected
            let grant1 = Uuid::new_v4();
            let grant2 = Uuid::new_v4();
            let grant3 = Uuid::new_v4();

            sqlx::query(
                "INSERT INTO cross_sovereign_delegation_grants (id, grantor_sovereign_id, grantee_sovereign_id, grantor_agent_id, grantee_agent_id, federation_peer_id, ceiling_tier, ceiling_attestation_types, transitivity_depth, status, grant_signature) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)"
            )
            .bind(grant1)
            .bind(sovereigns[0])
            .bind(sovereigns[1])
            .bind("agent_0")
            .bind("agent_1")
            .bind(peer_01)
            .bind(100i16)
            .bind(vec!["test"])
            .bind(1i16)
            .bind("active")
            .bind("sig1")
            .execute(&pool)
            .await
            .expect("insert grant");

            sqlx::query(
                "INSERT INTO cross_sovereign_delegation_grants (id, grantor_sovereign_id, grantee_sovereign_id, grantor_agent_id, grantee_agent_id, federation_peer_id, ceiling_tier, ceiling_attestation_types, transitivity_depth, status, grant_signature) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)"
            )
            .bind(grant2)
            .bind(sovereigns[1])
            .bind(sovereigns[2])
            .bind("agent_1")
            .bind("agent_2")
            .bind(peer_12)
            .bind(100i16)
            .bind(vec!["test"])
            .bind(1i16)
            .bind("active")
            .bind("sig2")
            .execute(&pool)
            .await
            .expect("insert grant");

            sqlx::query(
                "INSERT INTO cross_sovereign_delegation_grants (id, grantor_sovereign_id, grantee_sovereign_id, grantor_agent_id, grantee_agent_id, federation_peer_id, ceiling_tier, ceiling_attestation_types, transitivity_depth, status, grant_signature) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)"
            )
            .bind(grant3)
            .bind(sovereigns[2])
            .bind(sovereigns[0])
            .bind("agent_2")
            .bind("agent_0")
            .bind(peer_20)
            .bind(100i16)
            .bind(vec!["test"])
            .bind(1i16)
            .bind("active")
            .bind("sig3")
            .execute(&pool)
            .await
            .expect("insert grant");

            let start = std::time::Instant::now();
            let result = detect_reputation_cycles(&pool)
                .await
                .expect("detect cycles");
            let elapsed = start.elapsed().as_millis();

            assert_eq!(result.cycles.len(), 1, "Should detect 1 cycle");
            assert_eq!(
                result.total_nodes_analyzed, node_count,
                "Should analyze all nodes"
            );
            assert!(
                elapsed < 2000,
                "Should complete in <2 seconds for 50 nodes (was {}ms)",
                elapsed
            );
        }
    }
}
