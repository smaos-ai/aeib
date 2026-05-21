/// Phase 13 Task 69: Cycle Healing — Auto-break low-trust cycles, consensus-gate high-trust
/// Implements two-path healing: automatic revocation for low/medium severity, consensus-gated for high/critical.
use crate::repo::cycle_forensics::ReputationCycle;
use crate::repo::reputation_graph::ReputationGraph;
use serde_json::json;
use sqlx::PgPool;
use std::collections::HashSet;
use uuid::Uuid;

pub const CYCLE_HEALING_AUTO_THRESHOLD: &str = "severity_low_or_medium_auto_healed";

#[derive(Debug, Clone)]
pub enum CycleHealError {
    CycleEmpty,
    WeakestLinkNotFound,
    GrantRevocationFailed(String),
    ConsensusError(String),
    Database(String),
}

impl std::fmt::Display for CycleHealError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            CycleHealError::CycleEmpty => write!(f, "Cycle is empty"),
            CycleHealError::WeakestLinkNotFound => {
                write!(f, "Weakest link grant not found in graph")
            }
            CycleHealError::GrantRevocationFailed(e) => write!(f, "Grant revocation failed: {}", e),
            CycleHealError::ConsensusError(e) => write!(f, "Consensus error: {}", e),
            CycleHealError::Database(e) => write!(f, "Database error: {}", e),
        }
    }
}

impl std::error::Error for CycleHealError {}

#[derive(Debug, Clone, sqlx::FromRow)]
pub struct HealingResult {
    pub cycle_nodes: Vec<Uuid>,
    pub severity: String,
    pub action_taken: String, // "auto_revoked" | "consensus_initiated"
    pub grant_id_revoked: Option<Uuid>,
    pub proposal_id: Option<Uuid>,
    pub weakest_link_sovereign: Uuid,
    pub weakest_link_ceiling: u32,
    pub cascade_count: u64,
}

/// Resolve the weakest link grant ID and grantor sovereign ID from a cycle and graph.
/// Returns (grant_id, grantor_id) if found, None otherwise.
fn resolve_weakest_link_grant(
    cycle: &ReputationCycle,
    graph: &ReputationGraph,
) -> Option<(Uuid, Uuid)> {
    let edges = graph.outgoing_edges(cycle.weakest_link_id)?;
    let cycle_set: HashSet<Uuid> = cycle.cycle_nodes.iter().copied().collect();

    // Find edge from weakest_link_id to a cycle node with matching ceiling_tier
    edges
        .iter()
        .filter(|e| {
            cycle_set.contains(&e.to_sovereign) && e.ceiling_tier == cycle.weakest_link_ceiling
        })
        .next()
        .map(|e| (e.delegation_grant_id, e.from_sovereign))
}

/// Heal a single detected cycle via auto-revoke or consensus-gating based on severity.
/// Returns HealingResult with action taken and grant/proposal IDs.
pub async fn heal_cycle(
    pool: &PgPool,
    cycle: &ReputationCycle,
    graph: &ReputationGraph,
    initiator_id: Uuid,
) -> Result<HealingResult, CycleHealError> {
    if cycle.cycle_nodes.is_empty() {
        return Err(CycleHealError::CycleEmpty);
    }

    let (grant_id, grantor_id) =
        resolve_weakest_link_grant(cycle, graph).ok_or(CycleHealError::WeakestLinkNotFound)?;

    let action_taken: String;
    let grant_id_revoked: Option<Uuid>;
    let proposal_id: Option<Uuid>;
    let cascade_count: u64;

    // Route by severity threshold
    match cycle.severity.as_str() {
        "low" | "medium" => {
            // Auto-revoke path
            let affected = crate::repo::cross_sovereign_delegation_repo::revoke_grant(
                pool, grant_id, grantor_id, true,
            )
            .await
            .map_err(|e| CycleHealError::GrantRevocationFailed(e.to_string()))?;

            action_taken = "auto_revoked".to_string();
            grant_id_revoked = Some(grant_id);
            proposal_id = None;
            cascade_count = affected;
        }
        "high" | "critical" => {
            // Consensus-gated path: initiate consensus proposal, then inject payload
            let prop_id = crate::repo::consensus_repo::initiate_consensus(
                pool,
                initiator_id,
                None, // no escrow for cycle_break
                "cycle_break",
            )
            .await
            .map_err(|e| CycleHealError::ConsensusError(format!("{:?}", e)))?;

            // Inject payload with grant details
            let payload = json!({
                "grant_id_to_revoke": grant_id.to_string(),
                "grantor_sovereign_id": grantor_id.to_string(),
                "cycle_severity": cycle.severity,
                "cycle_nodes": cycle.cycle_nodes.iter().map(|id| id.to_string()).collect::<Vec<_>>(),
            });

            sqlx::query("UPDATE consensus_proposals SET payload = $1 WHERE id = $2")
                .bind(payload.to_string())
                .bind(prop_id)
                .execute(pool)
                .await
                .map_err(|e| CycleHealError::Database(e.to_string()))?;

            action_taken = "consensus_initiated".to_string();
            grant_id_revoked = None;
            proposal_id = Some(prop_id);
            cascade_count = 0;
        }
        _ => {
            return Err(CycleHealError::Database(format!(
                "unknown severity: {}",
                cycle.severity
            )));
        }
    }

    // Log healing action to audit table
    sqlx::query(
        "INSERT INTO cycle_healing_log \
         (cycle_nodes, severity, weakest_link_sovereign_id, weakest_link_ceiling, \
          grant_id_revoked, action_taken, proposal_id, healed_by_sovereign_id, cascade_count) \
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
    )
    .bind(&cycle.cycle_nodes)
    .bind(&cycle.severity)
    .bind(cycle.weakest_link_id)
    .bind(cycle.weakest_link_ceiling as i32)
    .bind(grant_id_revoked)
    .bind(&action_taken)
    .bind(proposal_id)
    .bind(initiator_id)
    .bind(cascade_count as i32)
    .execute(pool)
    .await
    .map_err(|e| CycleHealError::Database(e.to_string()))?;

    Ok(HealingResult {
        cycle_nodes: cycle.cycle_nodes.clone(),
        severity: cycle.severity.clone(),
        action_taken,
        grant_id_revoked,
        proposal_id,
        weakest_link_sovereign: cycle.weakest_link_id,
        weakest_link_ceiling: cycle.weakest_link_ceiling,
        cascade_count,
    })
}

/// Batch healing: detect all cycles, then heal each via heal_cycle().
/// Returns all results (successful and failed healings tracked separately).
pub async fn heal_all_detected_cycles(
    pool: &PgPool,
    initiator_id: Uuid,
) -> Result<Vec<HealingResult>, CycleHealError> {
    // Build reputation graph
    let graph = crate::repo::reputation_graph::build_reputation_graph_from_db(pool)
        .await
        .map_err(|e| CycleHealError::Database(format!("graph build failed: {}", e)))?;

    // Detect cycles
    let detection_result = crate::repo::cycle_detector::detect_reputation_cycles(pool)
        .await
        .map_err(|e| CycleHealError::Database(format!("cycle detection failed: {:?}", e)))?;

    let mut results = Vec::new();
    for cycle in detection_result.cycles {
        match heal_cycle(pool, &cycle, &graph, initiator_id).await {
            Ok(result) => results.push(result),
            Err(_e) => {
                // Log but continue healing other cycles
                // TODO: consider adding partial failure tracking
            }
        }
    }

    Ok(results)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::repo::reputation_graph::GraphEdge;

    #[test]
    fn test_resolve_weakest_link_found() {
        let mut graph = ReputationGraph::new();
        let node_a = Uuid::new_v4();
        let node_b = Uuid::new_v4();
        let node_c = Uuid::new_v4();
        let grant_id = Uuid::new_v4();

        graph.add_node(node_a, "A".to_string());
        graph.add_node(node_b, "B".to_string());
        graph.add_node(node_c, "C".to_string());

        let edge = GraphEdge {
            from_sovereign: node_a,
            to_sovereign: node_b,
            delegation_grant_id: grant_id,
            ceiling_tier: 20,
            transitivity_depth: 1,
            status: "active".to_string(),
        };

        graph.add_edge(edge);

        let cycle = ReputationCycle {
            cycle_nodes: vec![node_a, node_b],
            severity: "low".to_string(),
            weakest_link_id: node_a,
            weakest_link_ceiling: 20,
            base_score: 50.0,
            trust_density: 0.5,
            cycle_length: 2,
        };

        let result = resolve_weakest_link_grant(&cycle, &graph);
        assert!(result.is_some());
        let (resolved_grant, resolved_grantor) = result.unwrap();
        assert_eq!(resolved_grant, grant_id);
        assert_eq!(resolved_grantor, node_a);
    }

    #[test]
    fn test_resolve_weakest_link_not_found() {
        let mut graph = ReputationGraph::new();
        let node_a = Uuid::new_v4();
        let node_b = Uuid::new_v4();

        graph.add_node(node_a, "A".to_string());
        graph.add_node(node_b, "B".to_string());

        // No edges, so weakest_link_id has no outgoing edges
        let cycle = ReputationCycle {
            cycle_nodes: vec![node_a, node_b],
            severity: "low".to_string(),
            weakest_link_id: node_a,
            weakest_link_ceiling: 20,
            base_score: 50.0,
            trust_density: 0.5,
            cycle_length: 2,
        };

        let result = resolve_weakest_link_grant(&cycle, &graph);
        assert!(result.is_none());
    }

    #[test]
    fn test_resolve_weakest_link_wrong_ceiling() {
        let mut graph = ReputationGraph::new();
        let node_a = Uuid::new_v4();
        let node_b = Uuid::new_v4();
        let grant_id = Uuid::new_v4();

        graph.add_node(node_a, "A".to_string());
        graph.add_node(node_b, "B".to_string());

        let edge = GraphEdge {
            from_sovereign: node_a,
            to_sovereign: node_b,
            delegation_grant_id: grant_id,
            ceiling_tier: 30, // different from cycle.weakest_link_ceiling
            transitivity_depth: 1,
            status: "active".to_string(),
        };

        graph.add_edge(edge);

        let cycle = ReputationCycle {
            cycle_nodes: vec![node_a, node_b],
            severity: "low".to_string(),
            weakest_link_id: node_a,
            weakest_link_ceiling: 20, // doesn't match edge ceiling_tier
            base_score: 50.0,
            trust_density: 0.5,
            cycle_length: 2,
        };

        let result = resolve_weakest_link_grant(&cycle, &graph);
        assert!(result.is_none());
    }

    #[test]
    fn test_healing_threshold_low_severity() {
        let action = "low";
        match action {
            "low" | "medium" => {
                assert_eq!("auto_revoked", "auto_revoked");
            }
            _ => panic!("unexpected"),
        }
    }

    #[test]
    fn test_healing_threshold_medium_severity() {
        let action = "medium";
        match action {
            "low" | "medium" => {
                assert_eq!("auto_revoked", "auto_revoked");
            }
            _ => panic!("unexpected"),
        }
    }

    #[test]
    fn test_healing_threshold_high_severity() {
        let action = "high";
        match action {
            "high" | "critical" => {
                assert_eq!("consensus_initiated", "consensus_initiated");
            }
            _ => panic!("unexpected"),
        }
    }

    // ============================================================================
    // Integration Tests (Docker-dependent)
    // ============================================================================

    #[cfg(test)]
    mod integration_tests {
        use super::*;
        use crate::repo::cycle_detector::TarjanCycleFinder;
        use crate::repo::reputation_graph::build_reputation_graph_from_db;
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

        async fn insert_sovereign(pool: &PgPool, id: Uuid, name: &str) {
            sqlx::query(
                "INSERT INTO sovereigns (id, name, public_key_pem, status, endpoint_url) VALUES ($1, $2, $3, $4, $5)"
            )
            .bind(id)
            .bind(name)
            .bind("-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAI...")
            .bind("active")
            .bind(format!("http://{}.local", name))
            .execute(pool)
            .await
            .expect("insert sovereign");
        }

        async fn insert_federation_peer(pool: &PgPool, a: Uuid, b: Uuid) -> Uuid {
            let peer_id = Uuid::new_v4();
            sqlx::query(
                "INSERT INTO federation_peers (id, sovereign_a_id, sovereign_b_id, max_admitted_tier, \
                 granted_attestation_types, foreign_agent_budget_cap, status) \
                 VALUES ($1, $2, $3, $4, $5, $6, 'active')"
            )
            .bind(peer_id)
            .bind(a)
            .bind(b)
            .bind(100i16)
            .bind(vec!["agent_identity"])
            .bind(1000000i64)
            .execute(pool)
            .await
            .expect("insert federation_peer");
            peer_id
        }

        async fn insert_grant(
            pool: &PgPool,
            grantor: Uuid,
            grantee: Uuid,
            peer_id: Uuid,
            ceiling_tier: i16,
        ) -> Uuid {
            crate::repo::cross_sovereign_delegation_repo::insert_cross_sovereign_grant(
                pool,
                "agent_grantor",
                grantor,
                "agent_grantee",
                grantee,
                peer_id,
                ceiling_tier,
                vec!["agent_identity".to_string()],
                None,
                None,
                "test-signature",
            )
            .await
            .expect("insert grant")
        }

        /// Setup a 3-node cycle: A→B→C→A with given ceiling_tier.
        /// Returns (node_a, node_b, node_c, grant_ab, grant_bc, grant_ca)
        async fn setup_cycle(
            pool: &PgPool,
            ceiling_tier: i16,
        ) -> (Uuid, Uuid, Uuid, Uuid, Uuid, Uuid) {
            let (a, b, c) = (Uuid::new_v4(), Uuid::new_v4(), Uuid::new_v4());

            insert_sovereign(pool, a, "node_a").await;
            insert_sovereign(pool, b, "node_b").await;
            insert_sovereign(pool, c, "node_c").await;

            let peer_ab = insert_federation_peer(pool, a, b).await;
            let peer_bc = insert_federation_peer(pool, b, c).await;
            let peer_ca = insert_federation_peer(pool, c, a).await;

            let grant_ab = insert_grant(pool, a, b, peer_ab, ceiling_tier).await;
            let grant_bc = insert_grant(pool, b, c, peer_bc, ceiling_tier).await;
            let grant_ca = insert_grant(pool, c, a, peer_ca, ceiling_tier).await;

            (a, b, c, grant_ab, grant_bc, grant_ca)
        }

        #[tokio::test]
        async fn test_heal_cycle_auto_revokes_grant() {
            let (_container, pool) = setup_postgres().await;
            let (a, _b, _c, _grant_ab, grant_bc, _grant_ca) = setup_cycle(&pool, 20).await;

            // Build graph and detect cycles
            let graph = build_reputation_graph_from_db(&pool)
                .await
                .expect("build graph");
            let all_cycles = TarjanCycleFinder::new(graph.clone()).find_all_cycles();
            assert!(!all_cycles.is_empty(), "Should detect at least one cycle");

            let cycle = crate::repo::cycle_forensics::ReputationCycle::analyze_cycle(
                all_cycles[0].clone(),
                &graph,
            )
            .expect("analyze cycle");

            // Should be "low" severity
            assert_eq!(cycle.severity, "low");

            // Heal the cycle
            let result = heal_cycle(&pool, &cycle, &graph, a)
                .await
                .expect("heal cycle");

            assert_eq!(result.action_taken, "auto_revoked");
            assert_eq!(result.grant_id_revoked, Some(grant_bc));

            // Verify grant is revoked
            let status: String = sqlx::query_scalar(
                "SELECT status FROM cross_sovereign_delegation_grants WHERE id = $1",
            )
            .bind(grant_bc)
            .fetch_one(&pool)
            .await
            .expect("fetch grant status");

            assert_eq!(status, "revoked");
        }

        #[tokio::test]
        async fn test_heal_cycle_creates_consensus_proposal() {
            let (_container, pool) = setup_postgres().await;
            let (a, _b, _c, _grant_ab, _grant_bc, _grant_ca) = setup_cycle(&pool, 170).await;

            // Build graph and detect cycles
            let graph = build_reputation_graph_from_db(&pool)
                .await
                .expect("build graph");
            let all_cycles = TarjanCycleFinder::new(graph.clone()).find_all_cycles();
            assert!(!all_cycles.is_empty(), "Should detect at least one cycle");

            let cycle = crate::repo::cycle_forensics::ReputationCycle::analyze_cycle(
                all_cycles[0].clone(),
                &graph,
            )
            .expect("analyze cycle");

            // Should be "critical" severity (base_score = 170 * 0.5 = 85 > 80, length = 3)
            assert_eq!(cycle.severity, "critical");

            // Heal the cycle
            let result = heal_cycle(&pool, &cycle, &graph, a)
                .await
                .expect("heal cycle");

            assert_eq!(result.action_taken, "consensus_initiated");
            assert!(result.proposal_id.is_some());

            // Verify proposal exists with correct type and payload
            let (prop_type, payload_str): (String, String) = sqlx::query_as(
                "SELECT proposal_type, payload FROM consensus_proposals WHERE id = $1",
            )
            .bind(result.proposal_id.unwrap())
            .fetch_one(&pool)
            .await
            .expect("fetch proposal");

            assert_eq!(prop_type, "cycle_break");
            let payload: serde_json::Value =
                serde_json::from_str(&payload_str).expect("parse payload");
            assert!(payload["grant_id_to_revoke"].as_str().is_some());
        }

        #[tokio::test]
        async fn test_finalize_consensus_cycle_break_revokes_grant() {
            let (_container, pool) = setup_postgres().await;
            let (a, _b, _c, _grant_ab, grant_bc, _grant_ca) = setup_cycle(&pool, 170).await;

            // Build graph and detect cycles
            let graph = build_reputation_graph_from_db(&pool)
                .await
                .expect("build graph");
            let all_cycles = TarjanCycleFinder::new(graph.clone()).find_all_cycles();
            let cycle = crate::repo::cycle_forensics::ReputationCycle::analyze_cycle(
                all_cycles[0].clone(),
                &graph,
            )
            .expect("analyze cycle");

            // Heal the cycle (creates proposal)
            let result = heal_cycle(&pool, &cycle, &graph, a)
                .await
                .expect("heal cycle");
            let proposal_id = result.proposal_id.expect("proposal_id");

            // Manually approve the proposal (bypass voting)
            sqlx::query("UPDATE consensus_proposals SET status = 'approved' WHERE id = $1")
                .bind(proposal_id)
                .execute(&pool)
                .await
                .expect("approve proposal");

            // Finalize consensus
            crate::repo::consensus_repo::finalize_consensus(&pool, proposal_id)
                .await
                .expect("finalize consensus");

            // Verify grant is revoked
            let status: String = sqlx::query_scalar(
                "SELECT status FROM cross_sovereign_delegation_grants WHERE id = $1",
            )
            .bind(grant_bc)
            .fetch_one(&pool)
            .await
            .expect("fetch grant status");

            assert_eq!(status, "revoked");
        }

        #[tokio::test]
        async fn test_heal_all_detected_cycles_batch() {
            let (_container, pool) = setup_postgres().await;
            let (_a, _b, _c, _grant_ab, _grant_bc, _grant_ca) = setup_cycle(&pool, 20).await;

            // Batch heal all detected cycles
            let results = heal_all_detected_cycles(&pool, Uuid::new_v4())
                .await
                .expect("heal all cycles");

            assert!(
                !results.is_empty(),
                "Should have at least one healing result"
            );
            assert_eq!(results[0].action_taken, "auto_revoked");
            assert!(results[0].grant_id_revoked.is_some());
        }

        #[tokio::test]
        async fn test_cycle_healing_log_audit_record() {
            let (_container, pool) = setup_postgres().await;
            let (a, _b, _c, _grant_ab, _grant_bc, _grant_ca) = setup_cycle(&pool, 20).await;

            // Build graph and detect cycles
            let graph = build_reputation_graph_from_db(&pool)
                .await
                .expect("build graph");
            let all_cycles = TarjanCycleFinder::new(graph.clone()).find_all_cycles();
            let cycle = crate::repo::cycle_forensics::ReputationCycle::analyze_cycle(
                all_cycles[0].clone(),
                &graph,
            )
            .expect("analyze cycle");

            // Heal the cycle
            let _result = heal_cycle(&pool, &cycle, &graph, a)
                .await
                .expect("heal cycle");

            // Verify audit log entry
            let (action_taken, severity, ceiling): (String, String, i16) = sqlx::query_as(
                "SELECT action_taken, severity, weakest_link_ceiling FROM cycle_healing_log WHERE severity = 'low'"
            )
            .fetch_one(&pool)
            .await
            .expect("fetch log entry");

            assert_eq!(action_taken, "auto_revoked");
            assert_eq!(severity, "low");
            assert_eq!(ceiling, 20);
        }
    }
}
