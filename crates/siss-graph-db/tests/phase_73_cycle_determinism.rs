/// Phase 73 Integration Tests: Cycle Healing Determinism
/// Verify that analyze_cycle() and heal_cycle() produce deterministic results
/// when the same input is run multiple times or in different orders.

use siss_graph_db::repo::{cycle_healing_repo, cross_sovereign_delegation_repo};
use sqlx::postgres::PgPoolOptions;
use testcontainers::core::WaitFor;
use testcontainers::runners::AsyncRunner;
use testcontainers::{GenericImage, ImageExt};
use uuid::Uuid;

async fn setup_postgres() -> (
    testcontainers::ContainerAsync<GenericImage>,
    sqlx::PgPool,
) {
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
    let pool = PgPoolOptions::new()
        .max_connections(5)
        .connect(&url)
        .await
        .expect("pool connect");

    siss_graph_db::migrations::run_all(&pool)
        .await
        .expect("migrations");

    (container, pool)
}

async fn insert_sovereign(pool: &sqlx::PgPool, id: Uuid, name: &str) {
    sqlx::query(
        "INSERT INTO sovereigns (id, name, public_key_pem, status, endpoint_url) VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING",
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

async fn insert_federation_peer(pool: &sqlx::PgPool, a: Uuid, b: Uuid) -> Uuid {
    let peer_id = Uuid::new_v4();
    sqlx::query(
        "INSERT INTO federation_peers (id, sovereign_a_id, sovereign_b_id, max_admitted_tier, granted_attestation_types, foreign_agent_budget_cap, status) \
         VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT DO NOTHING",
    )
    .bind(peer_id)
    .bind(a)
    .bind(b)
    .bind(100i16)
    .bind(vec!["agent_identity"])
    .bind(1000000i64)
    .bind("active")
    .execute(pool)
    .await
    .expect("insert federation_peer");
    peer_id
}

async fn insert_grant(
    pool: &sqlx::PgPool,
    grantor: Uuid,
    grantee: Uuid,
    peer_id: Uuid,
    ceiling_tier: i16,
) -> Uuid {
    cross_sovereign_delegation_repo::insert_cross_sovereign_grant(
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

async fn setup_cycle_determinism(
    pool: &sqlx::PgPool,
) -> (Uuid, Uuid, Uuid) {
    // Create 3-node cycle: A→B→C→A
    let a = Uuid::new_v4();
    let b = Uuid::new_v4();
    let c = Uuid::new_v4();

    insert_sovereign(pool, a, "sovereign_a").await;
    insert_sovereign(pool, b, "sovereign_b").await;
    insert_sovereign(pool, c, "sovereign_c").await;

    // All edges same ceiling_tier to force tiebreaker usage
    let peer_ab = insert_federation_peer(pool, a, b).await;
    let peer_bc = insert_federation_peer(pool, b, c).await;
    let peer_ca = insert_federation_peer(pool, c, a).await;

    let _ = insert_grant(pool, a, b, peer_ab, 50).await;
    let _ = insert_grant(pool, b, c, peer_bc, 50).await;
    let _ = insert_grant(pool, c, a, peer_ca, 50).await;

    (a, b, c)
}

#[tokio::test]
async fn test_heal_cycle_deterministic_revocation() {
    let (_container, pool) = setup_postgres().await;
    let (a, _b, _c) = setup_cycle_determinism(&pool).await;

    let graph = siss_graph_db::repo::reputation_graph::build_reputation_graph_from_db(&pool)
        .await
        .expect("build graph");

    // Detect cycles
    let all_cycles = siss_graph_db::repo::cycle_detector::TarjanCycleFinder::new(graph.clone())
        .find_all_cycles();
    assert!(!all_cycles.is_empty());

    // Analyze first cycle
    let cycle = siss_graph_db::repo::cycle_forensics::ReputationCycle::analyze_cycle(
        all_cycles[0].clone(),
        &graph,
    )
    .expect("analyze cycle");

    // Run heal_cycle 3 times; all should revoke the same grant
    let mut revoked_grants = Vec::new();

    for _ in 0..3 {
        let result = cycle_healing_repo::heal_cycle(&pool, &cycle, &graph, a)
            .await
            .expect("heal cycle");

        revoked_grants.push(result.grant_id_revoked);
    }

    // All 3 runs should have revoked the same grant
    for grant_id in &revoked_grants[1..] {
        assert_eq!(
            grant_id, &revoked_grants[0],
            "All heal_cycle runs should revoke identical grant"
        );
    }
}

#[tokio::test]
async fn test_determinism_with_shuffled_node_order() {
    let (_container, pool) = setup_postgres().await;
    let (a, b, c) = setup_cycle_determinism(&pool).await;

    let graph = siss_graph_db::repo::reputation_graph::build_reputation_graph_from_db(&pool)
        .await
        .expect("build graph");

    // Test 3 different orderings of the same cycle
    let orderings = vec![
        vec![a, b, c],
        vec![b, c, a],
        vec![c, a, b],
    ];

    let mut results = Vec::new();
    for cycle_nodes in orderings {
        let result = siss_graph_db::repo::cycle_forensics::ReputationCycle::analyze_cycle(
            cycle_nodes,
            &graph,
        )
        .expect("analyze cycle");
        results.push(result);
    }

    // All orderings should produce the same weakest_link_id
    for result in &results[1..] {
        assert_eq!(
            result.weakest_link_id, results[0].weakest_link_id,
            "Different cycle_nodes orderings should find same weakest link"
        );
        assert_eq!(
            result.weakest_link_ceiling, results[0].weakest_link_ceiling,
            "Ceiling should be identical"
        );
    }
}

#[tokio::test]
async fn test_2_node_cycle_tiebreaker_db() {
    let (_container, pool) = setup_postgres().await;

    let a = Uuid::new_v4();
    let b = Uuid::new_v4();

    insert_sovereign(&pool, a, "a").await;
    insert_sovereign(&pool, b, "b").await;

    // A↔B both tier 100 (identical ceiling)
    let peer_ab = insert_federation_peer(&pool, a, b).await;
    let peer_ba = insert_federation_peer(&pool, b, a).await;

    let _ = insert_grant(&pool, a, b, peer_ab, 100).await;
    let _ = insert_grant(&pool, b, a, peer_ba, 100).await;

    let graph = siss_graph_db::repo::reputation_graph::build_reputation_graph_from_db(&pool)
        .await
        .expect("build graph");

    let cycle = siss_graph_db::repo::cycle_forensics::ReputationCycle::analyze_cycle(
        vec![a, b],
        &graph,
    )
    .expect("analyze cycle");

    assert_eq!(cycle.weakest_link_ceiling, 100);

    // Run 3 more times to verify determinism
    for _ in 0..3 {
        let cycle_repeat = siss_graph_db::repo::cycle_forensics::ReputationCycle::analyze_cycle(
            vec![a, b],
            &graph,
        )
        .expect("analyze cycle");

        assert_eq!(
            cycle_repeat.weakest_link_id, cycle.weakest_link_id,
            "Weakest link should be deterministic"
        );
    }
}

#[tokio::test]
async fn test_fully_tied_10_node_cycle() {
    let (_container, pool) = setup_postgres().await;

    let nodes: Vec<Uuid> = (0..10).map(|_| Uuid::new_v4()).collect();

    for (idx, node) in nodes.iter().enumerate() {
        insert_sovereign(&pool, *node, &format!("node_{idx}")).await;
    }

    // Create chain: 0→1→2→...→9→0, all ceiling_tier=75
    for i in 0..10 {
        let from = nodes[i];
        let to = nodes[(i + 1) % 10];
        let peer = insert_federation_peer(&pool, from, to).await;
        let _ = insert_grant(&pool, from, to, peer, 75).await;
    }

    let graph = siss_graph_db::repo::reputation_graph::build_reputation_graph_from_db(&pool)
        .await
        .expect("build graph");

    // All edges same ceiling; tiebreaker determines winner
    let cycle = siss_graph_db::repo::cycle_forensics::ReputationCycle::analyze_cycle(
        nodes.clone(),
        &graph,
    )
    .expect("analyze cycle");

    assert_eq!(cycle.weakest_link_ceiling, 75);

    // Verify determinism
    for _ in 0..3 {
        let cycle_repeat =
            siss_graph_db::repo::cycle_forensics::ReputationCycle::analyze_cycle(
                nodes.clone(),
                &graph,
            )
            .expect("analyze cycle");

        assert_eq!(
            cycle_repeat.weakest_link_id, cycle.weakest_link_id,
            "10-node tied cycle should always pick same weakest link"
        );
    }
}

#[tokio::test]
async fn test_tiebreaker_stability_under_shuffled_insert_order() {
    let (_container, pool) = setup_postgres().await;

    let a = Uuid::new_v4();
    let b = Uuid::new_v4();
    let c = Uuid::new_v4();

    insert_sovereign(&pool, a, "a").await;
    insert_sovereign(&pool, b, "b").await;
    insert_sovereign(&pool, c, "c").await;

    // Create cycle in reverse order: C→B, B→A, A→C with all tier=50
    let peer_cb = insert_federation_peer(&pool, c, b).await;
    let peer_ba = insert_federation_peer(&pool, b, a).await;
    let peer_ac = insert_federation_peer(&pool, a, c).await;

    let _ = insert_grant(&pool, c, b, peer_cb, 50).await;
    let _ = insert_grant(&pool, b, a, peer_ba, 50).await;
    let _ = insert_grant(&pool, a, c, peer_ac, 50).await;

    let graph1 = siss_graph_db::repo::reputation_graph::build_reputation_graph_from_db(&pool)
        .await
        .expect("build graph 1");

    let cycle1 = siss_graph_db::repo::cycle_forensics::ReputationCycle::analyze_cycle(
        vec![a, b, c],
        &graph1,
    )
    .expect("analyze cycle 1");

    // Analyze again with same data
    let graph2 = siss_graph_db::repo::reputation_graph::build_reputation_graph_from_db(&pool)
        .await
        .expect("build graph 2");

    let cycle2 = siss_graph_db::repo::cycle_forensics::ReputationCycle::analyze_cycle(
        vec![a, b, c],
        &graph2,
    )
    .expect("analyze cycle 2");

    assert_eq!(
        cycle1.weakest_link_id, cycle2.weakest_link_id,
        "Multiple graph loads should pick same weakest link"
    );
}

#[tokio::test]
async fn test_concurrent_analysis_10_parallel() {
    let (_container, pool) = setup_postgres().await;
    let (a, b, c) = setup_cycle_determinism(&pool).await;

    let graph = siss_graph_db::repo::reputation_graph::build_reputation_graph_from_db(&pool)
        .await
        .expect("build graph");

    // Spawn 10 concurrent tasks all analyzing the same cycle
    let mut handles = vec![];

    for _ in 0..10 {
        let graph_clone = graph.clone();
        let cycle_nodes = vec![a, b, c];

        let handle = tokio::spawn(async move {
            siss_graph_db::repo::cycle_forensics::ReputationCycle::analyze_cycle(
                cycle_nodes,
                &graph_clone,
            )
            .expect("analyze cycle")
        });

        handles.push(handle);
    }

    // Collect results
    let mut results = vec![];
    for handle in handles {
        let result = handle.await.expect("join");
        results.push(result);
    }

    // All 10 parallel results should be identical
    for result in &results[1..] {
        assert_eq!(
            result.weakest_link_id, results[0].weakest_link_id,
            "Concurrent analysis should be deterministic"
        );
        assert_eq!(
            result.weakest_link_ceiling, results[0].weakest_link_ceiling,
            "Ceiling should be identical"
        );
        assert_eq!(result.severity, results[0].severity, "Severity should be identical");
    }
}
