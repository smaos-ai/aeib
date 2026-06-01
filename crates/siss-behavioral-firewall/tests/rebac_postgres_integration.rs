use siss_behavioral_firewall::pg::ReBAC_PG;
use siss_behavioral_firewall::{SovereignIdentity, PolicyResource, RelationType, PolicyAction};
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

    let rel_id = rebac.grant_relationship(s1, a1.clone(), RelationType::Owner, None)
        .await
        .expect("Failed to grant relationship");

    assert!(!rel_id.is_nil());

    let result = rebac.verify_relationship(s1, a1.clone(), PolicyAction::Spawn)
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

    let rel_id = rebac.grant_relationship(s1, a1.clone(), RelationType::Owner, None)
        .await
        .expect("Failed to grant relationship");

    // Should work before revoke
    assert!(rebac.verify_relationship(s1, a1.clone(), PolicyAction::Spawn)
        .await
        .is_ok());

    // Revoke
    rebac.revoke_relationship(rel_id)
        .await
        .expect("Failed to revoke relationship");

    // Should fail after revoke
    assert!(rebac.verify_relationship(s1, a1.clone(), PolicyAction::Spawn)
        .await
        .is_err());
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

    rebac.grant_relationship(s1, a1.clone(), RelationType::Owner, None)
        .await
        .expect("Failed to grant relationship");

    rebac.grant_relationship(s1, a2.clone(), RelationType::Operator, None)
        .await
        .expect("Failed to grant relationship");

    let rels = rebac.list_relationships(s1)
        .await
        .expect("Failed to list relationships");

    assert_eq!(rels.len(), 2);
    cleanup_db(&pool).await;
}
