/// Federation peer and settlement ledger operations (Phase 9)
/// All DB operations for cross-sovereign coordination

use sqlx::PgPool;
use uuid::Uuid;

/// Lookup the active bilateral agreement from sovereign_a to sovereign_b.
/// Returns (max_admitted_tier, granted_attestation_types, foreign_agent_budget_cap).
pub async fn lookup_federation_peer(
    pool: &PgPool,
    sovereign_a: Uuid,
    sovereign_b: Uuid,
) -> Result<Option<(i16, Vec<String>, i64)>, sqlx::Error> {
    sqlx::query_as::<_, (i16, Vec<String>, i64)>(
        "SELECT max_admitted_tier, granted_attestation_types, foreign_agent_budget_cap \
         FROM federation_peers \
         WHERE sovereign_a_id = $1 AND sovereign_b_id = $2 AND status = 'active' \
         AND (expires_at IS NULL OR expires_at > NOW()) \
         ORDER BY granted_at DESC \
         LIMIT 1"
    )
    .bind(sovereign_a)
    .bind(sovereign_b)
    .fetch_optional(pool)
    .await
}

/// Lookup the public key for a sovereign.
pub async fn lookup_sovereign_public_key(
    pool: &PgPool,
    sovereign_id: Uuid,
) -> Result<Option<String>, sqlx::Error> {
    sqlx::query_scalar::<_, String>(
        "SELECT public_key_pem FROM sovereigns WHERE id = $1"
    )
    .bind(sovereign_id)
    .fetch_optional(pool)
    .await
}

/// Check if a revocation certificate exists for an agent.
/// Returns true if revoked (any certificate found), false otherwise.
pub async fn check_revocation_certificate(
    pool: &PgPool,
    agent_id: &str,
    source_sovereign_id: Uuid,
) -> Result<bool, sqlx::Error> {
    let count: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM revocation_certificates \
         WHERE agent_id = $1 AND source_sovereign_id = $2"
    )
    .bind(agent_id)
    .bind(source_sovereign_id)
    .fetch_one(pool)
    .await?;
    Ok(count > 0)
}

/// Insert a credit entry for inter-sovereign settlement.
/// Append-only: records tokens consumed by a foreign agent.
pub async fn insert_sovereign_credit_entry(
    pool: &PgPool,
    creditor_sovereign_id: Uuid,
    debtor_sovereign_id: Uuid,
    session_id: Uuid,
    tokens_consumed: i64,
) -> Result<Uuid, sqlx::Error> {
    let id = Uuid::new_v4();
    sqlx::query(
        "INSERT INTO sovereign_credit_entries (id, creditor_sovereign_id, debtor_sovereign_id, session_id, tokens_consumed, cost_breakdown) \
         VALUES ($1, $2, $3, $4, $5, '{}'::jsonb)"
    )
    .bind(id)
    .bind(creditor_sovereign_id)
    .bind(debtor_sovereign_id)
    .bind(session_id)
    .bind(tokens_consumed)
    .execute(pool)
    .await?;
    Ok(id)
}

#[cfg(test)]
mod tests {
    use super::*;
    use testcontainers::{core::WaitFor, runners::AsyncRunner, GenericImage, ImageExt};

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
    async fn test_lookup_federation_peer_found() {
        let (_container, pool) = setup_postgres().await;

        let sovereign_a = Uuid::new_v4();
        let sovereign_b = Uuid::new_v4();

        // Insert sovereigns
        sqlx::query("INSERT INTO sovereigns (id, name, public_key_pem) VALUES ($1, $2, $3)")
            .bind(sovereign_a)
            .bind("Sovereign A")
            .bind("dummy-key-a")
            .execute(&pool)
            .await
            .unwrap();

        sqlx::query("INSERT INTO sovereigns (id, name, public_key_pem) VALUES ($1, $2, $3)")
            .bind(sovereign_b)
            .bind("Sovereign B")
            .bind("dummy-key-b")
            .execute(&pool)
            .await
            .unwrap();

        // Insert federation peer
        sqlx::query(
            "INSERT INTO federation_peers (sovereign_a_id, sovereign_b_id, max_admitted_tier, granted_attestation_types, foreign_agent_budget_cap) \
             VALUES ($1, $2, $3, $4, $5)"
        )
        .bind(sovereign_a)
        .bind(sovereign_b)
        .bind(3i16)
        .bind(vec!["SovereignOrigin", "HardwareEnclave"])
        .bind(500000i64)
        .execute(&pool)
        .await
        .unwrap();

        let result = lookup_federation_peer(&pool, sovereign_a, sovereign_b).await.unwrap();
        assert!(result.is_some());
        let (tier, _types, cap) = result.unwrap();
        assert_eq!(tier, 3);
        assert_eq!(cap, 500000);
    }

    #[tokio::test]
    async fn test_lookup_federation_peer_not_found() {
        let (_container, pool) = setup_postgres().await;
        let a = Uuid::new_v4();
        let b = Uuid::new_v4();

        let result = lookup_federation_peer(&pool, a, b).await.unwrap();
        assert!(result.is_none());
    }

    #[tokio::test]
    async fn test_check_revocation_certificate_found() {
        let (_container, pool) = setup_postgres().await;

        let sovereign_id = Uuid::new_v4();
        sqlx::query("INSERT INTO sovereigns (id, name, public_key_pem) VALUES ($1, $2, $3)")
            .bind(sovereign_id)
            .bind("Sovereign")
            .bind("key")
            .execute(&pool)
            .await
            .unwrap();

        // Insert revocation cert
        sqlx::query(
            "INSERT INTO revocation_certificates (agent_id, source_sovereign_id, revoked_at, signature) \
             VALUES ($1, $2, NOW(), $3)"
        )
        .bind("alice")
        .bind(sovereign_id)
        .bind("sig-bytes")
        .execute(&pool)
        .await
        .unwrap();

        let revoked = check_revocation_certificate(&pool, "alice", sovereign_id).await.unwrap();
        assert!(revoked);
    }

    #[tokio::test]
    async fn test_check_revocation_certificate_not_found() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();

        let revoked = check_revocation_certificate(&pool, "alice", sovereign_id).await.unwrap();
        assert!(!revoked);
    }

    #[tokio::test]
    async fn test_insert_credit_entry_returns_uuid() {
        let (_container, pool) = setup_postgres().await;

        let creditor = Uuid::new_v4();
        let debtor = Uuid::new_v4();
        let session = Uuid::new_v4();

        // Insert sovereigns and session (prerequisites)
        sqlx::query("INSERT INTO sovereigns (id, name, public_key_pem) VALUES ($1, $2, $3)")
            .bind(creditor)
            .bind("Creditor Sovereign")
            .bind("key-creditor")
            .execute(&pool)
            .await
            .unwrap();

        sqlx::query("INSERT INTO sovereigns (id, name, public_key_pem) VALUES ($1, $2, $3)")
            .bind(debtor)
            .bind("Debtor Sovereign")
            .bind("key-debtor")
            .execute(&pool)
            .await
            .unwrap();

        // Insert a minimal tenant and session
        let tenant_id = Uuid::new_v4();
        sqlx::query("INSERT INTO tenants (id, tenant_id, name) VALUES ($1, $1, $2)")
            .bind(tenant_id)
            .bind("Test Tenant")
            .execute(&pool)
            .await
            .unwrap();

        sqlx::query(
            "INSERT INTO sessions (id, tenant_id, token_budget, active_persona_id, visible_field_snapshot, status) \
             VALUES ($1, $2, $3, $4, 'null'::jsonb, 'active'::session_status)"
        )
        .bind(session)
        .bind(tenant_id)
        .bind(1000i64)
        .bind(Uuid::new_v4())
        .execute(&pool)
        .await
        .unwrap();

        // Insert credit entry
        let entry_id = insert_sovereign_credit_entry(&pool, creditor, debtor, session, 500i64)
            .await
            .unwrap();

        // Verify it's a valid UUID
        assert_ne!(entry_id, Uuid::nil());
    }

    #[tokio::test]
    async fn test_credit_entries_unsettled_by_default() {
        let (_container, pool) = setup_postgres().await;

        let creditor = Uuid::new_v4();
        let debtor = Uuid::new_v4();
        let session = Uuid::new_v4();

        // Setup sovereigns and session
        sqlx::query("INSERT INTO sovereigns (id, name, public_key_pem) VALUES ($1, $2, $3)")
            .bind(creditor)
            .bind("Creditor")
            .bind("key")
            .execute(&pool)
            .await
            .unwrap();

        sqlx::query("INSERT INTO sovereigns (id, name, public_key_pem) VALUES ($1, $2, $3)")
            .bind(debtor)
            .bind("Debtor")
            .bind("key")
            .execute(&pool)
            .await
            .unwrap();

        let tenant_id = Uuid::new_v4();
        sqlx::query("INSERT INTO tenants (id, tenant_id, name) VALUES ($1, $1, $2)")
            .bind(tenant_id)
            .bind("Test")
            .execute(&pool)
            .await
            .unwrap();

        sqlx::query(
            "INSERT INTO sessions (id, tenant_id, token_budget, active_persona_id, visible_field_snapshot, status) \
             VALUES ($1, $2, $3, $4, 'null'::jsonb, 'active'::session_status)"
        )
        .bind(session)
        .bind(tenant_id)
        .bind(1000i64)
        .bind(Uuid::new_v4())
        .execute(&pool)
        .await
        .unwrap();

        // Insert credit entry
        insert_sovereign_credit_entry(&pool, creditor, debtor, session, 500i64)
            .await
            .unwrap();

        // Query to check settled_at is NULL
        let row: (Option<String>,) = sqlx::query_as(
            "SELECT settled_at FROM sovereign_credit_entries \
             WHERE creditor_sovereign_id = $1 AND debtor_sovereign_id = $2 LIMIT 1"
        )
        .bind(creditor)
        .bind(debtor)
        .fetch_one(&pool)
        .await
        .unwrap();

        assert!(row.0.is_none(), "settled_at should be NULL by default");
    }

    #[tokio::test]
    async fn test_credit_entry_append_only() {
        let (_container, pool) = setup_postgres().await;

        let creditor = Uuid::new_v4();
        let debtor = Uuid::new_v4();
        let session1 = Uuid::new_v4();
        let session2 = Uuid::new_v4();

        // Setup
        sqlx::query("INSERT INTO sovereigns (id, name, public_key_pem) VALUES ($1, $2, $3)")
            .bind(creditor)
            .bind("Creditor")
            .bind("key")
            .execute(&pool)
            .await
            .unwrap();

        sqlx::query("INSERT INTO sovereigns (id, name, public_key_pem) VALUES ($1, $2, $3)")
            .bind(debtor)
            .bind("Debtor")
            .bind("key")
            .execute(&pool)
            .await
            .unwrap();

        let tenant_id = Uuid::new_v4();
        sqlx::query("INSERT INTO tenants (id, tenant_id, name) VALUES ($1, $1, $2)")
            .bind(tenant_id)
            .bind("Test")
            .execute(&pool)
            .await
            .unwrap();

        sqlx::query(
            "INSERT INTO sessions (id, tenant_id, token_budget, active_persona_id, visible_field_snapshot, status) \
             VALUES ($1, $2, $3, $4, 'null'::jsonb, 'active'::session_status)"
        )
        .bind(session1)
        .bind(tenant_id)
        .bind(1000i64)
        .bind(Uuid::new_v4())
        .execute(&pool)
        .await
        .unwrap();

        sqlx::query(
            "INSERT INTO sessions (id, tenant_id, token_budget, active_persona_id, visible_field_snapshot, status) \
             VALUES ($1, $2, $3, $4, 'null'::jsonb, 'active'::session_status)"
        )
        .bind(session2)
        .bind(tenant_id)
        .bind(2000i64)
        .bind(Uuid::new_v4())
        .execute(&pool)
        .await
        .unwrap();

        // Insert two credit entries (append-only)
        insert_sovereign_credit_entry(&pool, creditor, debtor, session1, 500i64)
            .await
            .unwrap();

        insert_sovereign_credit_entry(&pool, creditor, debtor, session2, 750i64)
            .await
            .unwrap();

        // Count total entries
        let count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM sovereign_credit_entries \
             WHERE creditor_sovereign_id = $1 AND debtor_sovereign_id = $2"
        )
        .bind(creditor)
        .bind(debtor)
        .fetch_one(&pool)
        .await
        .unwrap();

        assert_eq!(count.0, 2, "Both credit entries should be preserved (append-only)");

        // Verify sum of tokens
        let total: (i64,) = sqlx::query_as(
            "SELECT SUM(tokens_consumed) FROM sovereign_credit_entries \
             WHERE creditor_sovereign_id = $1 AND debtor_sovereign_id = $2"
        )
        .bind(creditor)
        .bind(debtor)
        .fetch_one(&pool)
        .await
        .unwrap();

        assert_eq!(total.0, 1250, "Total tokens should be 500 + 750 = 1250");
    }
}
