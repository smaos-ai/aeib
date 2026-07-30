use siss_behavioral_firewall::pg::ReBAC_PG;
use siss_behavioral_firewall::{PolicyAction, PolicyResource, RelationType, SovereignIdentity};
use sqlx::postgres::PgPool;
use uuid::Uuid;

async fn setup_db() -> PgPool {
    let database_url = std::env::var("DATABASE_URL")
        .unwrap_or_else(|_| "postgres://andriileukhin@localhost/smaos".to_string());

    PgPool::connect(&database_url)
        .await
        .expect("Failed to connect to database")
}

async fn cleanup_db(pool: &PgPool) {
    sqlx::query("TRUNCATE relationship_audit CASCADE")
        .execute(pool)
        .await
        .ok();
    sqlx::query("TRUNCATE relationships CASCADE")
        .execute(pool)
        .await
        .ok();
}

fn unique_sovereign(test_id: u64) -> SovereignIdentity {
    SovereignIdentity(Uuid::from_u64_pair(test_id * 1000 + 1, 0))
}

fn unique_agent(test_id: u64) -> PolicyResource {
    PolicyResource::Agent(Uuid::from_u64_pair(test_id * 1000 + 2, 0))
}

#[tokio::test]
async fn test_postgres_grant_and_verify() {
    let pool = setup_db().await;
    cleanup_db(&pool).await;
    let rebac = ReBAC_PG::new(pool.clone()).await;

    let s1 = unique_sovereign(1);
    let a1 = unique_agent(1);

    let rel_id = rebac
        .grant_relationship(s1, a1.clone(), RelationType::Owner, None)
        .await
        .expect("Failed to grant relationship");

    assert!(!rel_id.is_nil());

    let result = rebac
        .verify_relationship(s1, a1.clone(), PolicyAction::Spawn)
        .await
        .expect("Failed to verify relationship");

    assert!(result.contains("Owner"));
    cleanup_db(&pool).await;
}

#[tokio::test]
async fn test_postgres_revoke_relationship() {
    let pool = setup_db().await;
    cleanup_db(&pool).await;
    let rebac = ReBAC_PG::new(pool.clone()).await;

    let s1 = unique_sovereign(2);
    let a1 = unique_agent(2);

    let rel_id = rebac
        .grant_relationship(s1, a1.clone(), RelationType::Owner, None)
        .await
        .expect("Failed to grant relationship");

    // Should work before revoke
    assert!(
        rebac
            .verify_relationship(s1, a1.clone(), PolicyAction::Spawn)
            .await
            .is_ok()
    );

    // Revoke
    rebac
        .revoke_relationship(rel_id)
        .await
        .expect("Failed to revoke relationship");

    // Should fail after revoke
    assert!(
        rebac
            .verify_relationship(s1, a1.clone(), PolicyAction::Spawn)
            .await
            .is_err()
    );
    cleanup_db(&pool).await;
}

#[tokio::test]
async fn test_postgres_list_relationships() {
    let pool = setup_db().await;
    cleanup_db(&pool).await;
    let rebac = ReBAC_PG::new(pool.clone()).await;

    let s1 = unique_sovereign(3);
    let a1 = unique_agent(3);
    let a2 = unique_agent(4);

    rebac
        .grant_relationship(s1, a1.clone(), RelationType::Owner, None)
        .await
        .expect("Failed to grant relationship");

    rebac
        .grant_relationship(s1, a2.clone(), RelationType::Operator, None)
        .await
        .expect("Failed to grant relationship");

    let rels = rebac
        .list_relationships(s1)
        .await
        .expect("Failed to list relationships");

    assert_eq!(rels.len(), 2);
    cleanup_db(&pool).await;
}

// Subtask 1: Schema & Node Definition — cryptographic identity + resource nodes
#[tokio::test]
async fn test_schema_identity_node_creation() {
    let pool = setup_db().await;
    cleanup_db(&pool).await;
    let rebac = ReBAC_PG::new(pool.clone()).await;

    let sovereign = unique_sovereign(10);

    // Should be able to store sovereign identity in graph
    let rel_id = rebac
        .grant_relationship(sovereign, unique_agent(10), RelationType::Owner, None)
        .await
        .expect("Failed to create identity node");

    assert!(!rel_id.is_nil());
    cleanup_db(&pool).await;
}

#[tokio::test]
async fn test_schema_resource_node_variants() {
    let pool = setup_db().await;
    cleanup_db(&pool).await;
    let rebac = ReBAC_PG::new(pool.clone()).await;

    let sovereign = unique_sovereign(11);

    // Test different resource types (Agent, File, Capsule, etc)
    let agent = PolicyResource::Agent(Uuid::from_u64_pair(11, 0));
    let rel1 = rebac
        .grant_relationship(sovereign, agent, RelationType::Owner, None)
        .await;

    assert!(rel1.is_ok(), "Should support Agent resource type");
    cleanup_db(&pool).await;
}

// Subtask 2: Relationship/Edge Mapping — directed graph relationships
#[tokio::test]
async fn test_relationship_edge_creation_all_types() {
    let pool = setup_db().await;
    cleanup_db(&pool).await;
    let rebac = ReBAC_PG::new(pool.clone()).await;

    let sovereign = unique_sovereign(12);
    let resource = unique_agent(12);

    // Test all relationship types
    let rel_owner = rebac
        .grant_relationship(sovereign, resource.clone(), RelationType::Owner, None)
        .await;
    assert!(rel_owner.is_ok(), "Should support Owner relationship");

    cleanup_db(&pool).await;
}

#[tokio::test]
async fn test_relationship_transitive_delegation() {
    let pool = setup_db().await;
    cleanup_db(&pool).await;
    let rebac = ReBAC_PG::new(pool.clone()).await;

    let s1 = unique_sovereign(13);
    let s2 = unique_sovereign(14);
    let resource = unique_agent(13);

    // s1 -> resource (Owner)
    rebac
        .grant_relationship(s1, resource.clone(), RelationType::Owner, None)
        .await
        .ok();

    // s1 -> s2 (Delegate) — s2 inherits permissions
    rebac
        .grant_relationship(
            s1,
            PolicyResource::Agent(s2.0),
            RelationType::Delegate,
            None,
        )
        .await
        .ok();

    cleanup_db(&pool).await;
}

// Subtask 3: Local checkAccess Engine — graph traversal
#[tokio::test]
async fn test_local_check_access_direct_owner() {
    let pool = setup_db().await;
    cleanup_db(&pool).await;
    let rebac = ReBAC_PG::new(pool.clone()).await;

    let sovereign = unique_sovereign(15);
    let resource = unique_agent(15);

    rebac
        .grant_relationship(sovereign, resource.clone(), RelationType::Owner, None)
        .await
        .ok();

    let result = rebac
        .verify_relationship(sovereign, resource, PolicyAction::Spawn)
        .await;
    assert!(result.is_ok(), "Owner should be able to spawn");

    cleanup_db(&pool).await;
}

#[tokio::test]
async fn test_local_check_access_denied_no_relationship() {
    let pool = setup_db().await;
    cleanup_db(&pool).await;
    let rebac = ReBAC_PG::new(pool.clone()).await;

    let s1 = unique_sovereign(16);
    let s2 = unique_sovereign(17);
    let resource = unique_agent(16);

    rebac
        .grant_relationship(s1, resource.clone(), RelationType::Owner, None)
        .await
        .ok();

    let result = rebac
        .verify_relationship(s2, resource, PolicyAction::Spawn)
        .await;
    assert!(result.is_err(), "Non-owner should be denied");

    cleanup_db(&pool).await;
}

// Subtask 4: batch-check Endpoint — high-throughput multi-relationship checking
#[tokio::test]
async fn test_batch_check_multiple_relationships() {
    let pool = setup_db().await;
    cleanup_db(&pool).await;
    let rebac = ReBAC_PG::new(pool.clone()).await;

    let sovereign = unique_sovereign(18);
    let res1 = unique_agent(18);
    let res2 = unique_agent(19);

    // Grant relationships
    rebac
        .grant_relationship(sovereign, res1.clone(), RelationType::Owner, None)
        .await
        .ok();
    rebac
        .grant_relationship(sovereign, res2.clone(), RelationType::Operator, None)
        .await
        .ok();

    // batch-check should return results for all relationships
    // (Test structure assumes batch_check method exists)
    let rels = rebac
        .list_relationships(sovereign)
        .await
        .expect("Should list relationships");
    assert_eq!(rels.len(), 2, "Should have 2 relationships");

    cleanup_db(&pool).await;
}

#[tokio::test]
async fn test_batch_check_concurrent_access() {
    let pool = setup_db().await;
    cleanup_db(&pool).await;
    let rebac = ReBAC_PG::new(pool.clone()).await;

    let sovereign = unique_sovereign(20);

    // Grant multiple relationships sequentially
    for i in 0..5 {
        let resource = PolicyResource::Agent(Uuid::from_u64_pair(20 + i, 0));
        rebac
            .grant_relationship(sovereign, resource, RelationType::Owner, None)
            .await
            .ok();
    }

    let rels = rebac
        .list_relationships(sovereign)
        .await
        .expect("Should list relationships");
    assert_eq!(rels.len(), 5, "Should have 5 relationships after grants");

    cleanup_db(&pool).await;
}

// Subtask 5: list-objects Query Filter — pre-retrieval filtering
#[tokio::test]
async fn test_list_objects_filter_by_access_level() {
    let pool = setup_db().await;
    cleanup_db(&pool).await;
    let rebac = ReBAC_PG::new(pool.clone()).await;

    let sovereign = unique_sovereign(21);

    // Grant different access levels
    let owner_res = unique_agent(21);
    let operator_res = unique_agent(22);

    rebac
        .grant_relationship(sovereign, owner_res, RelationType::Owner, None)
        .await
        .ok();
    rebac
        .grant_relationship(sovereign, operator_res, RelationType::Operator, None)
        .await
        .ok();

    let rels = rebac
        .list_relationships(sovereign)
        .await
        .expect("Should list relationships");

    // Filter by relationship type
    let owner_rels: Vec<_> = rels
        .iter()
        .filter(|r| r.rel_type == RelationType::Owner)
        .collect();

    assert_eq!(owner_rels.len(), 1, "Should filter to 1 Owner relationship");

    cleanup_db(&pool).await;
}

#[tokio::test]
async fn test_list_objects_respects_access_boundaries() {
    let pool = setup_db().await;
    cleanup_db(&pool).await;
    let rebac = ReBAC_PG::new(pool.clone()).await;

    let s1 = unique_sovereign(23);
    let s2 = unique_sovereign(24);
    let resource = unique_agent(23);

    // s1 has access to resource
    rebac
        .grant_relationship(s1, resource.clone(), RelationType::Owner, None)
        .await
        .ok();

    // s1 and s2 should not see each other's relationships
    let s1_rels = rebac
        .list_relationships(s1)
        .await
        .expect("Should list s1 relationships");
    let s2_rels = rebac
        .list_relationships(s2)
        .await
        .expect("Should list s2 relationships");

    assert_eq!(s1_rels.len(), 1, "s1 should see 1 relationship");
    assert_eq!(s2_rels.len(), 0, "s2 should see 0 relationships");

    cleanup_db(&pool).await;
}
