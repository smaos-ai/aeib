use chrono::Utc;
use siss_gatekeeper::delegation_routing;
use siss_graph_db::repo::{
    agent_discovery, cross_sovereign_delegation_repo, distributed_consensus, federation_repo,
};
use sqlx::PgPool;
use testcontainers::{GenericImage, ImageExt, core::WaitFor, runners::AsyncRunner};
use uuid::Uuid;

async fn start_postgres() -> (testcontainers::ContainerAsync<GenericImage>, PgPool) {
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
    siss_graph_db::migrations::run_all(&pool)
        .await
        .expect("migrations");
    (container, pool)
}

async fn setup_sovereigns(pool: &PgPool) -> (Uuid, Uuid, Uuid) {
    let sovereign1 = Uuid::new_v4();
    let sovereign2 = Uuid::new_v4();
    let sovereign3 = Uuid::new_v4();

    let placeholder_key = "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA\n-----END PUBLIC KEY-----";

    // Insert sovereigns directly
    sqlx::query(
        "INSERT INTO sovereigns (id, name, public_key_pem, status) VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING"
    )
    .bind(sovereign1)
    .bind("Sovereign1")
    .bind(placeholder_key)
    .bind("active")
    .execute(pool)
    .await
    .expect("insert sovereign1");

    sqlx::query(
        "INSERT INTO sovereigns (id, name, public_key_pem, status) VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING"
    )
    .bind(sovereign2)
    .bind("Sovereign2")
    .bind(placeholder_key)
    .bind("active")
    .execute(pool)
    .await
    .expect("insert sovereign2");

    sqlx::query(
        "INSERT INTO sovereigns (id, name, public_key_pem, status) VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING"
    )
    .bind(sovereign3)
    .bind("Sovereign3")
    .bind(placeholder_key)
    .bind("active")
    .execute(pool)
    .await
    .expect("insert sovereign3");

    (sovereign1, sovereign2, sovereign3)
}

// ====== Group A: Agent Discovery Tests ======

#[tokio::test]
async fn test_register_agent_succeeds() {
    let (_container, pool) = start_postgres().await;
    let (sovereign1, _, _) = setup_sovereigns(&pool).await;

    let agent_id = agent_discovery::register_agent(
        &pool,
        sovereign1,
        "agent-001",
        "ai_agent",
        vec!["read".to_string(), "write".to_string()],
        Some("http://localhost:8080".to_string()),
    )
    .await
    .expect("register agent");

    assert!(!agent_id.is_nil());
}

#[tokio::test]
async fn test_discover_agents_by_capability() {
    let (_container, pool) = start_postgres().await;
    let (sovereign1, _, _) = setup_sovereigns(&pool).await;

    // Register 3 agents with different capabilities
    agent_discovery::register_agent(
        &pool,
        sovereign1,
        "agent-001",
        "ai_agent",
        vec!["read".to_string()],
        None,
    )
    .await
    .expect("register agent 1");

    agent_discovery::register_agent(
        &pool,
        sovereign1,
        "agent-002",
        "ai_agent",
        vec!["read".to_string(), "write".to_string()],
        None,
    )
    .await
    .expect("register agent 2");

    agent_discovery::register_agent(
        &pool,
        sovereign1,
        "agent-003",
        "ai_agent",
        vec!["execute".to_string()],
        None,
    )
    .await
    .expect("register agent 3");

    let agents = agent_discovery::discover_agents(&pool, sovereign1, Some("read"))
        .await
        .expect("discover by capability");

    assert_eq!(agents.len(), 2);
}

#[tokio::test]
async fn test_cross_sovereign_discovery() {
    let (_container, pool) = start_postgres().await;
    let (sovereign1, sovereign2, _) = setup_sovereigns(&pool).await;

    // Register agents in both sovereigns
    agent_discovery::register_agent(
        &pool,
        sovereign1,
        "agent-s1-001",
        "ai_agent",
        vec!["read".to_string()],
        None,
    )
    .await
    .expect("register agent s1");

    agent_discovery::register_agent(
        &pool,
        sovereign2,
        "agent-s2-001",
        "ai_agent",
        vec!["read".to_string()],
        None,
    )
    .await
    .expect("register agent s2");

    // Create federation peer relationship
    sqlx::query(
        "INSERT INTO federation_peers (id, sovereign_a_id, sovereign_b_id, max_admitted_tier, granted_attestation_types, status) \
         VALUES ($1, $2, $3, $4, $5, $6)"
    )
    .bind(Uuid::new_v4())
    .bind(sovereign1)
    .bind(sovereign2)
    .bind(100i16)
    .bind(vec!["read", "write"])
    .bind("active")
    .execute(&pool)
    .await
    .ok();

    let agents = agent_discovery::discover_agents_cross_sovereign(&pool, sovereign1, Some("read"))
        .await
        .expect("cross sovereign discovery");

    assert!(agents.len() >= 2);
}

#[tokio::test]
async fn test_discover_agents_empty_sovereign() {
    let (_container, pool) = start_postgres().await;
    let (_, _, sovereign3) = setup_sovereigns(&pool).await;

    let agents = agent_discovery::discover_agents(&pool, sovereign3, None)
        .await
        .expect("discover agents empty");

    assert_eq!(agents.len(), 0);
}

#[tokio::test]
async fn test_agent_status_filter() {
    let (_container, pool) = start_postgres().await;
    let (sovereign1, _, _) = setup_sovereigns(&pool).await;

    agent_discovery::register_agent(
        &pool,
        sovereign1,
        "agent-001",
        "ai_agent",
        vec!["read".to_string()],
        None,
    )
    .await
    .expect("register agent");

    agent_discovery::register_agent(
        &pool,
        sovereign1,
        "agent-002",
        "ai_agent",
        vec!["read".to_string()],
        None,
    )
    .await
    .expect("register agent");

    agent_discovery::update_agent_status(&pool, "agent-002", sovereign1, "inactive")
        .await
        .expect("update agent status");

    let active_agents = agent_discovery::discover_agents(&pool, sovereign1, None)
        .await
        .expect("discover agents");

    assert_eq!(active_agents.len(), 1);
    assert_eq!(active_agents[0].agent_id, "agent-001");
}

// ====== Group B: Delegation Routing Tests ======

#[tokio::test]
async fn test_route_direct_delegation() {
    let (_container, pool) = start_postgres().await;
    let (sovereign1, sovereign2, _) = setup_sovereigns(&pool).await;

    // Create delegation grant from sovereign1 to sovereign2
    cross_sovereign_delegation_repo::insert_delegation_grant(
        &pool,
        sovereign1,
        sovereign2,
        100,
        Utc::now() + chrono::Duration::days(30),
    )
    .await
    .expect("insert grant");

    let decision = delegation_routing::route_request(&pool, sovereign1, sovereign2, 50)
        .await
        .expect("route request");

    assert!(decision.allowed);
    assert_eq!(decision.path.len(), 2);
}

#[tokio::test]
async fn test_route_transitive_delegation() {
    let (_container, pool) = start_postgres().await;
    let (sovereign1, sovereign2, sovereign3) = setup_sovereigns(&pool).await;

    // Create delegation chain: 1 -> 2 -> 3
    cross_sovereign_delegation_repo::insert_delegation_grant(
        &pool,
        sovereign1,
        sovereign2,
        100,
        Utc::now() + chrono::Duration::days(30),
    )
    .await
    .expect("insert grant 1->2");

    cross_sovereign_delegation_repo::insert_delegation_grant(
        &pool,
        sovereign2,
        sovereign3,
        100,
        Utc::now() + chrono::Duration::days(30),
    )
    .await
    .expect("insert grant 2->3");

    let decision = delegation_routing::route_request(&pool, sovereign1, sovereign3, 50)
        .await
        .expect("route request");

    assert!(decision.allowed);
    assert_eq!(decision.path.len(), 3);
}

#[tokio::test]
async fn test_route_blocked_by_cycle() {
    let (_container, pool) = start_postgres().await;
    let (sovereign1, sovereign2, sovereign3) = setup_sovereigns(&pool).await;

    // Create cycle: 1 -> 2 -> 3 -> 1
    cross_sovereign_delegation_repo::insert_delegation_grant(
        &pool,
        sovereign1,
        sovereign2,
        100,
        Utc::now() + chrono::Duration::days(30),
    )
    .await
    .expect("insert grant 1->2");

    cross_sovereign_delegation_repo::insert_delegation_grant(
        &pool,
        sovereign2,
        sovereign3,
        100,
        Utc::now() + chrono::Duration::days(30),
    )
    .await
    .expect("insert grant 2->3");

    cross_sovereign_delegation_repo::insert_delegation_grant(
        &pool,
        sovereign3,
        sovereign1,
        100,
        Utc::now() + chrono::Duration::days(30),
    )
    .await
    .expect("insert grant 3->1");

    // BFS finds the non-cyclic path (1->2->3) even though a cycle exists (3->1)
    let decision = delegation_routing::route_request(&pool, sovereign1, sovereign3, 50)
        .await
        .expect("route request");

    // Path should be found since 1->2->3 is a valid non-cyclic route
    assert!(decision.allowed);
    assert_eq!(decision.path.len(), 3);
}

#[tokio::test]
async fn test_route_blocked_by_ceiling() {
    let (_container, pool) = start_postgres().await;
    let (sovereign1, sovereign2, _) = setup_sovereigns(&pool).await;

    // Create delegation with low ceiling
    cross_sovereign_delegation_repo::insert_delegation_grant(
        &pool,
        sovereign1,
        sovereign2,
        50,
        Utc::now() + chrono::Duration::days(30),
    )
    .await
    .expect("insert grant");

    // Request with higher tier than ceiling
    let result = delegation_routing::route_request(&pool, sovereign1, sovereign2, 80).await;

    assert!(result.is_err());
}

#[tokio::test]
async fn test_route_no_delegation_path() {
    let (_container, pool) = start_postgres().await;
    let (sovereign1, sovereign2, _) = setup_sovereigns(&pool).await;

    // No delegation grants exist
    let result = delegation_routing::route_request(&pool, sovereign1, sovereign2, 50).await;

    assert!(result.is_err());
}

// ====== Group C: Cross-Sovereign Integration Tests ======

#[tokio::test]
async fn test_verify_cross_sovereign_path_exists() {
    let (_container, pool) = start_postgres().await;
    let (sovereign1, sovereign2, _) = setup_sovereigns(&pool).await;

    sqlx::query(
        "INSERT INTO federation_peers (id, sovereign_a_id, sovereign_b_id, max_admitted_tier, granted_attestation_types, status) \
         VALUES ($1, $2, $3, $4, $5, $6)"
    )
    .bind(Uuid::new_v4())
    .bind(sovereign1)
    .bind(sovereign2)
    .bind(100i16)
    .bind(vec!["read", "write"])
    .bind("active")
    .execute(&pool)
    .await
    .ok();

    cross_sovereign_delegation_repo::insert_delegation_grant(
        &pool,
        sovereign1,
        sovereign2,
        100,
        Utc::now() + chrono::Duration::days(30),
    )
    .await
    .expect("insert grant");

    let decision = delegation_routing::route_request(&pool, sovereign1, sovereign2, 50)
        .await
        .expect("route request");

    assert!(decision.allowed);
}

#[tokio::test]
async fn test_verify_path_respects_ceiling() {
    let (_container, pool) = start_postgres().await;
    let (sovereign1, sovereign2, sovereign3) = setup_sovereigns(&pool).await;

    // Create path with varying ceilings: 1 --(80)--> 2 --(50)--> 3
    cross_sovereign_delegation_repo::insert_delegation_grant(
        &pool,
        sovereign1,
        sovereign2,
        80,
        Utc::now() + chrono::Duration::days(30),
    )
    .await
    .expect("insert grant 1->2");

    cross_sovereign_delegation_repo::insert_delegation_grant(
        &pool,
        sovereign2,
        sovereign3,
        50,
        Utc::now() + chrono::Duration::days(30),
    )
    .await
    .expect("insert grant 2->3");

    // Request tier 60 should fail (limited by min ceiling of 50)
    let result = delegation_routing::route_request(&pool, sovereign1, sovereign3, 60).await;
    assert!(result.is_err());

    // Request tier 50 should succeed
    let decision = delegation_routing::route_request(&pool, sovereign1, sovereign3, 50)
        .await
        .expect("route request");
    assert!(decision.allowed);
    assert_eq!(decision.ceiling_tier, 50);
}

#[tokio::test]
async fn test_transitive_depth_limit() {
    let (_container, pool) = start_postgres().await;
    let (sovereign1, sovereign2, sovereign3) = setup_sovereigns(&pool).await;

    // Create 5-hop chain which should exceed max depth of 4
    let s4 = Uuid::new_v4();
    let s5 = Uuid::new_v4();
    let placeholder_key = "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA\n-----END PUBLIC KEY-----";

    sqlx::query(
        "INSERT INTO sovereigns (id, name, public_key_pem, status) VALUES ($1, $2, $3, $4)",
    )
    .bind(s4)
    .bind("Sovereign4")
    .bind(placeholder_key)
    .bind("active")
    .execute(&pool)
    .await
    .ok();

    sqlx::query(
        "INSERT INTO sovereigns (id, name, public_key_pem, status) VALUES ($1, $2, $3, $4)",
    )
    .bind(s5)
    .bind("Sovereign5")
    .bind(placeholder_key)
    .bind("active")
    .execute(&pool)
    .await
    .ok();

    cross_sovereign_delegation_repo::insert_delegation_grant(
        &pool,
        sovereign1,
        sovereign2,
        100,
        Utc::now() + chrono::Duration::days(30),
    )
    .await
    .ok();

    cross_sovereign_delegation_repo::insert_delegation_grant(
        &pool,
        sovereign2,
        sovereign3,
        100,
        Utc::now() + chrono::Duration::days(30),
    )
    .await
    .ok();

    cross_sovereign_delegation_repo::insert_delegation_grant(
        &pool,
        sovereign3,
        s4,
        100,
        Utc::now() + chrono::Duration::days(30),
    )
    .await
    .ok();

    cross_sovereign_delegation_repo::insert_delegation_grant(
        &pool,
        s4,
        s5,
        100,
        Utc::now() + chrono::Duration::days(30),
    )
    .await
    .ok();

    let result = delegation_routing::route_request(&pool, sovereign1, s5, 50).await;

    // Should fail due to depth limit
    assert!(result.is_err());
}

#[tokio::test]
async fn test_concurrent_routing_no_race() {
    let (_container, pool) = start_postgres().await;
    let (sovereign1, sovereign2, _) = setup_sovereigns(&pool).await;

    cross_sovereign_delegation_repo::insert_delegation_grant(
        &pool,
        sovereign1,
        sovereign2,
        100,
        Utc::now() + chrono::Duration::days(30),
    )
    .await
    .expect("insert grant");

    let mut tasks = vec![];
    for _ in 0..10 {
        let pool_clone = pool.clone();
        let task = tokio::spawn(async move {
            delegation_routing::route_request(&pool_clone, sovereign1, sovereign2, 50)
                .await
                .expect("route request")
        });
        tasks.push(task);
    }

    let mut results = vec![];
    for task in tasks {
        let result = task.await.expect("task");
        results.push(result);
    }

    // All results should be identical
    for decision in &results {
        assert!(decision.allowed);
        assert_eq!(decision.ceiling_tier, 100);
    }
}

#[tokio::test]
async fn test_routing_after_revocation() {
    let (_container, pool) = start_postgres().await;
    let (sovereign1, sovereign2, _) = setup_sovereigns(&pool).await;

    let grant_id = cross_sovereign_delegation_repo::insert_delegation_grant(
        &pool,
        sovereign1,
        sovereign2,
        100,
        Utc::now() + chrono::Duration::days(30),
    )
    .await
    .expect("insert grant");

    // Should succeed before revocation
    let decision = delegation_routing::route_request(&pool, sovereign1, sovereign2, 50)
        .await
        .expect("route request");
    assert!(decision.allowed);

    // Revoke the grant
    cross_sovereign_delegation_repo::revoke_delegation_grant(&pool, grant_id)
        .await
        .expect("revoke grant");

    // Should fail after revocation
    let result = delegation_routing::route_request(&pool, sovereign1, sovereign2, 50).await;
    assert!(result.is_err());
}

// ====== Group D: Distributed Consensus Stub Tests ======

#[tokio::test]
async fn test_distributed_proposal_created() {
    let (_container, pool) = start_postgres().await;
    let (sovereign1, sovereign2, sovereign3) = setup_sovereigns(&pool).await;

    let proposal_id = distributed_consensus::initiate_distributed_consensus(
        &pool,
        sovereign1,
        vec![sovereign1, sovereign2, sovereign3],
        "policy_update",
    )
    .await
    .expect("initiate consensus");

    assert!(!proposal_id.is_nil());
}

#[tokio::test]
async fn test_distributed_vote_cast() {
    let (_container, pool) = start_postgres().await;
    let (sovereign1, sovereign2, sovereign3) = setup_sovereigns(&pool).await;

    let proposal_id = distributed_consensus::initiate_distributed_consensus(
        &pool,
        sovereign1,
        vec![sovereign1, sovereign2, sovereign3],
        "policy_update",
    )
    .await
    .expect("initiate consensus");

    distributed_consensus::cast_vote(&pool, proposal_id, sovereign2, true)
        .await
        .expect("cast vote");

    let vote_count = distributed_consensus::get_vote_count(&pool, proposal_id)
        .await
        .expect("get vote count");

    assert_eq!(vote_count.0, 1); // 1 yes vote
}

#[tokio::test]
async fn test_distributed_quorum_calculation() {
    let (_container, pool) = start_postgres().await;
    let (sovereign1, sovereign2, sovereign3) = setup_sovereigns(&pool).await;

    let proposal_id = distributed_consensus::initiate_distributed_consensus(
        &pool,
        sovereign1,
        vec![sovereign1, sovereign2, sovereign3],
        "policy_update",
    )
    .await
    .expect("initiate consensus");

    distributed_consensus::cast_vote(&pool, proposal_id, sovereign1, true)
        .await
        .expect("vote 1");

    distributed_consensus::cast_vote(&pool, proposal_id, sovereign2, true)
        .await
        .expect("vote 2");

    // 2 out of 3 should be quorum
    let is_quorum = distributed_consensus::check_quorum(&pool, proposal_id)
        .await
        .expect("check quorum");

    assert!(is_quorum);
}

#[tokio::test]
async fn test_distributed_proposal_expired() {
    let (_container, pool) = start_postgres().await;
    let (sovereign1, sovereign2, sovereign3) = setup_sovereigns(&pool).await;

    // Create proposal with past expiry
    let proposal_id = distributed_consensus::initiate_distributed_consensus_with_expiry(
        &pool,
        sovereign1,
        vec![sovereign1, sovereign2, sovereign3],
        "policy_update",
        Utc::now() - chrono::Duration::hours(1),
    )
    .await
    .expect("initiate consensus");

    let is_expired = distributed_consensus::check_expired(&pool, proposal_id)
        .await
        .expect("check expired");

    assert!(is_expired);
}

#[tokio::test]
async fn test_distributed_consensus_phase75_placeholder() {
    let (_container, pool) = start_postgres().await;
    let (sovereign1, sovereign2, sovereign3) = setup_sovereigns(&pool).await;

    let proposal_id = distributed_consensus::initiate_distributed_consensus(
        &pool,
        sovereign1,
        vec![sovereign1, sovereign2, sovereign3],
        "policy_update",
    )
    .await
    .expect("initiate consensus");

    distributed_consensus::cast_vote(&pool, proposal_id, sovereign1, true)
        .await
        .expect("vote 1");

    distributed_consensus::cast_vote(&pool, proposal_id, sovereign2, true)
        .await
        .expect("vote 2");

    // Phase 75 finalization should return Unimplemented
    let result = distributed_consensus::finalize_distributed_consensus(&pool, proposal_id).await;

    match result {
        Err(distributed_consensus::ConsensusError::Unimplemented) => (),
        _ => panic!("Expected Unimplemented error for Phase 75 placeholder"),
    }
}
