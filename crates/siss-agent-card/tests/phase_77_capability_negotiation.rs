use siss_graph_db::repo::{
    capability_negotiation, transitive_delegation_repo, capability_grant_ledger, ceiling_enforcement,
};
use sqlx::PgPool;
use testcontainers::{GenericImage, ImageExt, core::{WaitFor, ContainerPort}, runners::AsyncRunner};
use uuid::Uuid;
use chrono::Utc;

async fn start_postgres() -> (testcontainers::ContainerAsync<GenericImage>, PgPool) {
    let container = GenericImage::new("postgres", "16")
        .with_exposed_port(ContainerPort::Tcp(5432))
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

async fn setup_sovereigns(pool: &PgPool, count: usize) -> Vec<Uuid> {
    let placeholder_key = "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA\n-----END PUBLIC KEY-----";
    let mut sovereigns = Vec::new();

    for i in 0..count {
        let sovereign_id = Uuid::new_v4();
        sqlx::query(
            "INSERT INTO sovereigns (id, name, public_key_pem, status) VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING"
        )
        .bind(sovereign_id)
        .bind(format!("Sovereign{}", i))
        .bind(placeholder_key)
        .bind("active")
        .execute(pool)
        .await
        .expect("insert sovereign");
        sovereigns.push(sovereign_id);
    }

    sovereigns
}

// ====== Group A: Capability Request Lifecycle (5 tests) ======

#[tokio::test]
async fn test_submit_capability_request_stores_in_db() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 1).await;
    let requester_id = Uuid::new_v4();

    let request_id = capability_negotiation::submit_capability_request(
        &pool,
        requester_id,
        sovereigns[0],
        "resource-1".to_string(),
        "read".to_string(),
        "TIER_2".to_string(),
    )
    .await
    .expect("submit request");

    let count: (i64,) = sqlx::query_as(
        "SELECT COUNT(*) FROM capability_requests WHERE id = $1"
    )
    .bind(request_id)
    .fetch_one(&pool)
    .await
    .expect("count request");

    assert_eq!(count.0, 1);
}

#[tokio::test]
async fn test_get_request_status_returns_pending_after_submit() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 1).await;
    let requester_id = Uuid::new_v4();

    let request_id = capability_negotiation::submit_capability_request(
        &pool,
        requester_id,
        sovereigns[0],
        "resource-1".to_string(),
        "read".to_string(),
        "TIER_2".to_string(),
    )
    .await
    .expect("submit request");

    let status = capability_negotiation::get_request_status(&pool, request_id)
        .await
        .expect("get status");

    assert_eq!(status, capability_negotiation::CapabilityRequestStatus::Pending);
}

#[tokio::test]
async fn test_propose_grant_transitions_to_proposed() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 1).await;
    let requester_id = Uuid::new_v4();

    let request_id = capability_negotiation::submit_capability_request(
        &pool,
        requester_id,
        sovereigns[0],
        "resource-1".to_string(),
        "read".to_string(),
        "TIER_2".to_string(),
    )
    .await
    .expect("submit request");

    capability_negotiation::propose_grant(
        &pool,
        request_id,
        "read".to_string(),
        "TIER_2".to_string(),
        Utc::now() + chrono::Duration::days(1),
        sovereigns[0],
    )
    .await
    .expect("propose grant");

    let status = capability_negotiation::get_request_status(&pool, request_id)
        .await
        .expect("get status");

    assert_eq!(status, capability_negotiation::CapabilityRequestStatus::Proposed);
}

#[tokio::test]
async fn test_accept_grant_returns_capability_grant() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 1).await;
    let requester_id = Uuid::new_v4();

    let request_id = capability_negotiation::submit_capability_request(
        &pool,
        requester_id,
        sovereigns[0],
        "resource-1".to_string(),
        "read".to_string(),
        "TIER_2".to_string(),
    )
    .await
    .expect("submit request");

    let expires_at = Utc::now() + chrono::Duration::days(1);
    capability_negotiation::propose_grant(
        &pool,
        request_id,
        "read".to_string(),
        "TIER_2".to_string(),
        expires_at,
        sovereigns[0],
    )
    .await
    .expect("propose grant");

    let grant = capability_negotiation::accept_grant(&pool, request_id, requester_id)
        .await
        .expect("accept grant");

    assert_eq!(grant.granted_capability, "read");
    assert_eq!(grant.ceiling_tier, "TIER_2");
    assert!(!grant.id.is_nil());
}

#[tokio::test]
async fn test_get_request_status_returns_accepted_after_acceptance() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 1).await;
    let requester_id = Uuid::new_v4();

    let request_id = capability_negotiation::submit_capability_request(
        &pool,
        requester_id,
        sovereigns[0],
        "resource-1".to_string(),
        "read".to_string(),
        "TIER_2".to_string(),
    )
    .await
    .expect("submit request");

    capability_negotiation::propose_grant(
        &pool,
        request_id,
        "read".to_string(),
        "TIER_2".to_string(),
        Utc::now() + chrono::Duration::days(1),
        sovereigns[0],
    )
    .await
    .expect("propose grant");

    capability_negotiation::accept_grant(&pool, request_id, requester_id)
        .await
        .expect("accept grant");

    let status = capability_negotiation::get_request_status(&pool, request_id)
        .await
        .expect("get status");

    assert_eq!(status, capability_negotiation::CapabilityRequestStatus::Accepted);
}

// ====== Group B: Transitive Delegation Chains (4 tests) ======

#[tokio::test]
async fn test_verify_transitive_chain_passes_for_valid_two_hop() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 3).await;

    // Create delegation relationships: S0 -> S1 -> S2
    sqlx::query(
        "INSERT INTO delegation_relationships (delegator, delegatee, ceiling_tier) VALUES ($1, $2, $3)"
    )
    .bind(sovereigns[0])
    .bind(sovereigns[1])
    .bind("TIER_2")
    .execute(&pool)
    .await
    .expect("insert delegation 0->1");

    sqlx::query(
        "INSERT INTO delegation_relationships (delegator, delegatee, ceiling_tier) VALUES ($1, $2, $3)"
    )
    .bind(sovereigns[1])
    .bind(sovereigns[2])
    .bind("TIER_2")
    .execute(&pool)
    .await
    .expect("insert delegation 1->2");

    let chain = transitive_delegation_repo::DelegationChain {
        sovereigns: vec![sovereigns[0], sovereigns[1], sovereigns[2]],
        ceiling_tiers: vec!["TIER_2".to_string(), "TIER_2".to_string()],
    };

    let is_valid = transitive_delegation_repo::verify_transitive_chain(&pool, &chain)
        .await
        .expect("verify chain");

    assert!(is_valid);
}

#[tokio::test]
async fn test_verify_chain_detects_cycle_with_repeated_sovereign() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 2).await;

    let chain = transitive_delegation_repo::DelegationChain {
        sovereigns: vec![sovereigns[0], sovereigns[1], sovereigns[0]],
        ceiling_tiers: vec!["TIER_2".to_string(), "TIER_2".to_string()],
    };

    let result = transitive_delegation_repo::verify_transitive_chain(&pool, &chain).await;

    // Should detect cycle or return false
    assert!(result.is_err() || result.unwrap() == false);
}

#[tokio::test]
async fn test_extend_chain_enforces_lowest_ceiling() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 3).await;

    let initial_chain = transitive_delegation_repo::DelegationChain {
        sovereigns: vec![sovereigns[0], sovereigns[1]],
        ceiling_tiers: vec!["TIER_2".to_string()],
    };

    let extended = transitive_delegation_repo::extend_chain(
        &pool,
        &initial_chain,
        sovereigns[2],
        "TIER_1",
    )
    .await
    .expect("extend chain");

    // Lowest tier is TIER_1 (most restrictive)
    assert_eq!(extended.ceiling_tiers[0], "TIER_1");
    assert!(extended.sovereigns.contains(&sovereigns[2]));
}

#[tokio::test]
async fn test_get_shortest_path_returns_direct_hop() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 2).await;

    sqlx::query(
        "INSERT INTO delegation_relationships (delegator, delegatee, ceiling_tier) VALUES ($1, $2, $3)"
    )
    .bind(sovereigns[0])
    .bind(sovereigns[1])
    .bind("TIER_2")
    .execute(&pool)
    .await
    .expect("insert delegation");

    let path = transitive_delegation_repo::get_shortest_path(&pool, sovereigns[0], sovereigns[1])
        .await
        .expect("get path");

    assert!(path.is_some());
    let chain = path.unwrap();
    assert_eq!(chain.sovereigns.len(), 2);
    assert_eq!(chain.sovereigns[0], sovereigns[0]);
    assert_eq!(chain.sovereigns[1], sovereigns[1]);
}

// ====== Group C: Ceiling Enforcement (4 tests) ======

#[tokio::test]
async fn test_ceiling_compliance_passes_within_bound() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 1).await;
    let requester_id = Uuid::new_v4();

    let request = capability_negotiation::CapabilityRequest {
        id: Uuid::new_v4(),
        requester_id,
        requester_sovereign: sovereigns[0],
        target_resource: "resource-1".to_string(),
        requested_capability: "read".to_string(),
        ceiling_tier_limit: "TIER_1".to_string(),
        created_at: Utc::now(),
    };

    let chain = transitive_delegation_repo::DelegationChain {
        sovereigns: vec![sovereigns[0]],
        ceiling_tiers: vec!["TIER_2".to_string()],
    };

    let compliant = ceiling_enforcement::validate_ceiling_compliance(&pool, &request, &chain)
        .await
        .expect("validate compliance");

    assert!(compliant);
}

#[tokio::test]
async fn test_ceiling_compliance_fails_exceeding_bound() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 1).await;
    let requester_id = Uuid::new_v4();

    let request = capability_negotiation::CapabilityRequest {
        id: Uuid::new_v4(),
        requester_id,
        requester_sovereign: sovereigns[0],
        target_resource: "resource-1".to_string(),
        requested_capability: "write".to_string(),
        ceiling_tier_limit: "TIER_3".to_string(),
        created_at: Utc::now(),
    };

    let chain = transitive_delegation_repo::DelegationChain {
        sovereigns: vec![sovereigns[0]],
        ceiling_tiers: vec!["TIER_1".to_string()],
    };

    let compliant = ceiling_enforcement::validate_ceiling_compliance(&pool, &request, &chain)
        .await
        .expect("validate compliance");

    assert!(!compliant);
}

#[tokio::test]
async fn test_compute_effective_ceiling_returns_lowest() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 1).await;

    let chain = transitive_delegation_repo::DelegationChain {
        sovereigns: vec![sovereigns[0]],
        ceiling_tiers: vec!["TIER_2".to_string(), "TIER_1".to_string()],
    };

    let effective = ceiling_enforcement::compute_effective_ceiling(&pool, &chain)
        .await
        .expect("compute ceiling");

    assert_eq!(effective, "TIER_1");
}

#[tokio::test]
async fn test_enforce_ceiling_on_grant_fails_for_escalation() {
    let (_container, pool) = start_postgres().await;
    let _sovereigns = setup_sovereigns(&pool, 1).await;

    let result = ceiling_enforcement::enforce_ceiling_on_grant(
        &pool,
        Uuid::new_v4(),
        "TIER_3",
        "TIER_1",
    )
    .await;

    assert!(result.is_err());
}

// ====== Group D: Grant Ledger (3 tests) ======

#[tokio::test]
async fn test_record_grant_returns_hash_and_is_in_ledger() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 1).await;
    let requester_id = Uuid::new_v4();

    let request_id = capability_negotiation::submit_capability_request(
        &pool,
        requester_id,
        sovereigns[0],
        "resource-1".to_string(),
        "read".to_string(),
        "TIER_2".to_string(),
    )
    .await
    .expect("submit request");

    capability_negotiation::propose_grant(
        &pool,
        request_id,
        "read".to_string(),
        "TIER_2".to_string(),
        Utc::now() + chrono::Duration::days(1),
        sovereigns[0],
    )
    .await
    .expect("propose grant");

    let grant = capability_negotiation::accept_grant(&pool, request_id, requester_id)
        .await
        .expect("accept grant");

    let hash = capability_grant_ledger::record_grant(&pool, &grant, &"proof".to_string())
        .await
        .expect("record grant");

    assert!(hash.starts_with("grant_"));

    let count: (i64,) = sqlx::query_as(
        "SELECT COUNT(*) FROM grant_ledger WHERE grant_id = $1"
    )
    .bind(grant.id)
    .fetch_one(&pool)
    .await
    .expect("count ledger");

    assert_eq!(count.0, 1);
}

#[tokio::test]
async fn test_verify_grant_active_returns_true_then_false_after_revoke() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 1).await;
    let requester_id = Uuid::new_v4();

    let request_id = capability_negotiation::submit_capability_request(
        &pool,
        requester_id,
        sovereigns[0],
        "resource-1".to_string(),
        "read".to_string(),
        "TIER_2".to_string(),
    )
    .await
    .expect("submit request");

    capability_negotiation::propose_grant(
        &pool,
        request_id,
        "read".to_string(),
        "TIER_2".to_string(),
        Utc::now() + chrono::Duration::days(1),
        sovereigns[0],
    )
    .await
    .expect("propose grant");

    let grant = capability_negotiation::accept_grant(&pool, request_id, requester_id)
        .await
        .expect("accept grant");

    capability_grant_ledger::record_grant(&pool, &grant, &"proof".to_string())
        .await
        .expect("record grant");

    let active_before = capability_grant_ledger::verify_grant_active(&pool, grant.id)
        .await
        .expect("verify active before");
    assert!(active_before);

    capability_grant_ledger::revoke_grant(&pool, grant.id, "test revocation")
        .await
        .expect("revoke grant");

    let active_after = capability_grant_ledger::verify_grant_active(&pool, grant.id)
        .await
        .expect("verify active after");
    assert!(!active_after);
}

#[tokio::test]
async fn test_get_grant_history_returns_all_grants_for_requester() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 1).await;
    let requester_id = Uuid::new_v4();

    for i in 0..3 {
        let request_id = capability_negotiation::submit_capability_request(
            &pool,
            requester_id,
            sovereigns[0],
            format!("resource-{}", i),
            "read".to_string(),
            "TIER_2".to_string(),
        )
        .await
        .expect("submit request");

        capability_negotiation::propose_grant(
            &pool,
            request_id,
            "read".to_string(),
            "TIER_2".to_string(),
            Utc::now() + chrono::Duration::days(1),
            sovereigns[0],
        )
        .await
        .expect("propose grant");

        let _grant = capability_negotiation::accept_grant(&pool, request_id, requester_id)
            .await
            .expect("accept grant");
    }

    let history = capability_grant_ledger::get_grant_history(&pool, requester_id, 10)
        .await
        .expect("get history");

    assert_eq!(history.len(), 3);
}
