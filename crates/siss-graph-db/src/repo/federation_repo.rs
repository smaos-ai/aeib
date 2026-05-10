/// Federation peer and settlement ledger operations (Phase 9 & 10)
/// All DB operations for cross-sovereign coordination

use chrono::{DateTime, Utc};
use sha2::{Sha256, Digest};
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

/// Renegotiate a bilateral federation agreement (Phase 10).
/// Atomically supersedes the old active agreement and inserts a new one.
/// Active sessions using the old cap unaffected; new cap takes effect on next refresh.
pub async fn renegotiate_federation_agreement(
    pool: &PgPool,
    sovereign_a: Uuid,
    sovereign_b: Uuid,
    new_max_admitted_tier: i16,
    new_granted_attestation_types: Vec<String>,
    new_foreign_agent_budget_cap: i64,
    new_expires_at: Option<DateTime<Utc>>,
    agreement_signature: &str,
) -> Result<Uuid, sqlx::Error> {
    let mut tx = pool.begin().await?;

    // Step 1: Mark old active agreement as superseded
    sqlx::query(
        "UPDATE federation_peers SET status = 'superseded' \
         WHERE sovereign_a_id = $1 AND sovereign_b_id = $2 AND status = 'active'"
    )
    .bind(sovereign_a)
    .bind(sovereign_b)
    .execute(&mut *tx)
    .await?;

    // Step 2: Insert new active agreement
    let new_agreement_id = Uuid::new_v4();
    sqlx::query(
        "INSERT INTO federation_peers \
         (id, sovereign_a_id, sovereign_b_id, max_admitted_tier, granted_attestation_types, \
          foreign_agent_budget_cap, expires_at, status, agreement_signature) \
         VALUES ($1, $2, $3, $4, $5, $6, $7, 'active', $8)"
    )
    .bind(new_agreement_id)
    .bind(sovereign_a)
    .bind(sovereign_b)
    .bind(new_max_admitted_tier)
    .bind(new_granted_attestation_types)
    .bind(new_foreign_agent_budget_cap)
    .bind(new_expires_at)
    .bind(agreement_signature)
    .execute(&mut *tx)
    .await?;

    tx.commit().await?;
    Ok(new_agreement_id)
}

/// Generate a settlement invoice from unpaid credit entries (Phase 10).
/// Aggregates tokens and entry count from sovereign_credit_entries WHERE invoice_id IS NULL
/// for the given period. Links all matching entries to the new invoice via invoice_id.
/// Returns (invoice_id, total_tokens, entry_count).
pub async fn generate_settlement_invoice(
    pool: &PgPool,
    creditor_sovereign_id: Uuid,
    debtor_sovereign_id: Uuid,
    period_start: DateTime<Utc>,
    period_end: DateTime<Utc>,
    canonical_invoice_payload: &str,
    invoice_signature: &str,
) -> Result<(Uuid, i64, i32), sqlx::Error> {
    let mut tx = pool.begin().await?;

    // Step 1: Aggregate unpaid entries for the period
    let (total_tokens, entry_count): (Option<i64>, Option<i64>) = sqlx::query_as(
        "SELECT SUM(tokens_consumed), COUNT(*) FROM sovereign_credit_entries \
         WHERE creditor_sovereign_id = $1 AND debtor_sovereign_id = $2 \
         AND invoice_id IS NULL \
         AND created_at >= $3 AND created_at <= $4"
    )
    .bind(creditor_sovereign_id)
    .bind(debtor_sovereign_id)
    .bind(period_start)
    .bind(period_end)
    .fetch_one(&mut *tx)
    .await?;

    let total_tokens = total_tokens.unwrap_or(0);
    let entry_count = entry_count.unwrap_or(0) as i32;

    // Step 2: Compute invoice_hash = SHA256 hex of canonical payload
    let mut hasher = Sha256::new();
    hasher.update(canonical_invoice_payload);
    let hash_bytes = hasher.finalize();
    let invoice_hash = hex::encode(hash_bytes);

    // Step 3: Insert settlement invoice
    let invoice_id = Uuid::new_v4();
    sqlx::query(
        "INSERT INTO settlement_invoices \
         (id, creditor_sovereign_id, debtor_sovereign_id, period_start, period_end, \
          total_tokens, entry_count, invoice_hash, invoice_signature, status) \
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'pending')"
    )
    .bind(invoice_id)
    .bind(creditor_sovereign_id)
    .bind(debtor_sovereign_id)
    .bind(period_start)
    .bind(period_end)
    .bind(total_tokens)
    .bind(entry_count)
    .bind(&invoice_hash)
    .bind(invoice_signature)
    .execute(&mut *tx)
    .await?;

    // Step 4: Link all matching entries to the new invoice (append-only: only invoice_id changes)
    sqlx::query(
        "UPDATE sovereign_credit_entries SET invoice_id = $1 \
         WHERE creditor_sovereign_id = $2 AND debtor_sovereign_id = $3 \
         AND invoice_id IS NULL \
         AND created_at >= $4 AND created_at <= $5"
    )
    .bind(invoice_id)
    .bind(creditor_sovereign_id)
    .bind(debtor_sovereign_id)
    .bind(period_start)
    .bind(period_end)
    .execute(&mut *tx)
    .await?;

    tx.commit().await?;
    Ok((invoice_id, total_tokens, entry_count))
}

/// Mark an invoice as settled by the debtor (Phase 10).
/// Idempotent: second call on already-settled invoice returns false.
/// Only debtor can settle their own invoices.
pub async fn mark_invoice_settled(
    pool: &PgPool,
    invoice_id: Uuid,
    debtor_sovereign_id: Uuid,
) -> Result<bool, sqlx::Error> {
    let rows_affected = sqlx::query(
        "UPDATE settlement_invoices SET status = 'settled', settled_at = NOW() \
         WHERE id = $1 AND debtor_sovereign_id = $2 AND status = 'pending'"
    )
    .bind(invoice_id)
    .bind(debtor_sovereign_id)
    .execute(pool)
    .await?
    .rows_affected();

    Ok(rows_affected > 0)
}

/// Insert a revocation certificate from gossip message (Phase 10).
/// Idempotent via unique constraint on (agent_id, source_sovereign_id).
/// Returns Ok(uuid) with the inserted or existing revocation ID.
pub async fn insert_revocation_from_gossip(
    pool: &PgPool,
    agent_id: &str,
    source_sovereign_id: Uuid,
    revoked_at: DateTime<Utc>,
    signature: &str,
) -> Result<Uuid, sqlx::Error> {
    let id = Uuid::new_v4();
    // Try to insert; if conflict, fetch the existing one
    let inserted = sqlx::query_scalar::<_, Uuid>(
        "INSERT INTO revocation_certificates (id, agent_id, source_sovereign_id, revoked_at, signature) \
         VALUES ($1, $2, $3, $4, $5) \
         ON CONFLICT (agent_id, source_sovereign_id) DO NOTHING \
         RETURNING id"
    )
    .bind(id)
    .bind(agent_id)
    .bind(source_sovereign_id)
    .bind(revoked_at)
    .bind(signature)
    .fetch_optional(pool)
    .await?;

    // If inserted, return the new ID; otherwise fetch the existing one
    if let Some(uuid) = inserted {
        Ok(uuid)
    } else {
        // Fetch the existing revocation
        sqlx::query_scalar::<_, Uuid>(
            "SELECT id FROM revocation_certificates WHERE agent_id = $1 AND source_sovereign_id = $2 LIMIT 1"
        )
        .bind(agent_id)
        .bind(source_sovereign_id)
        .fetch_one(pool)
        .await
    }
}

/// List active bilateral peers with endpoint URLs for gossip broadcast (Phase 10).
/// Returns (peer_sovereign_id, endpoint_url) for all active agreements with non-NULL endpoint.
pub async fn list_active_peer_endpoints(
    pool: &PgPool,
    home_sovereign_id: Uuid,
) -> Result<Vec<(Uuid, String)>, sqlx::Error> {
    sqlx::query_as::<_, (Uuid, String)>(
        "SELECT fp.sovereign_b_id, s.endpoint_url \
         FROM federation_peers fp \
         JOIN sovereigns s ON s.id = fp.sovereign_b_id \
         WHERE fp.sovereign_a_id = $1 AND fp.status = 'active' \
         AND (fp.expires_at IS NULL OR fp.expires_at > NOW()) \
         AND s.endpoint_url IS NOT NULL"
    )
    .bind(home_sovereign_id)
    .fetch_all(pool)
    .await
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

    #[tokio::test]
    async fn test_renegotiate_supersedes_old_agreement() {
        let (_container, pool) = setup_postgres().await;

        let sovereign_a = Uuid::new_v4();
        let sovereign_b = Uuid::new_v4();

        // Setup sovereigns
        sqlx::query("INSERT INTO sovereigns (id, name, public_key_pem) VALUES ($1, $2, $3)")
            .bind(sovereign_a)
            .bind("Sovereign A")
            .bind("key-a")
            .execute(&pool)
            .await
            .unwrap();

        sqlx::query("INSERT INTO sovereigns (id, name, public_key_pem) VALUES ($1, $2, $3)")
            .bind(sovereign_b)
            .bind("Sovereign B")
            .bind("key-b")
            .execute(&pool)
            .await
            .unwrap();

        // Insert initial agreement
        sqlx::query(
            "INSERT INTO federation_peers (sovereign_a_id, sovereign_b_id, max_admitted_tier, granted_attestation_types, foreign_agent_budget_cap) \
             VALUES ($1, $2, $3, $4, $5)"
        )
        .bind(sovereign_a)
        .bind(sovereign_b)
        .bind(3i16)
        .bind(vec!["SovereignOrigin"])
        .bind(500000i64)
        .execute(&pool)
        .await
        .unwrap();

        // Verify old agreement is active
        let old_status: String = sqlx::query_scalar(
            "SELECT status FROM federation_peers WHERE sovereign_a_id = $1 AND sovereign_b_id = $2"
        )
        .bind(sovereign_a)
        .bind(sovereign_b)
        .fetch_one(&pool)
        .await
        .unwrap();
        assert_eq!(old_status, "active");

        // Renegotiate with new tier
        let new_agreement_id = renegotiate_federation_agreement(
            &pool,
            sovereign_a,
            sovereign_b,
            5i16,
            vec!["SovereignOrigin".to_string(), "HardwareEnclave".to_string()],
            750000i64,
            None,
            "new-sig-bytes",
        )
        .await
        .unwrap();

        // Verify old agreement is now superseded
        let old_status_after: String = sqlx::query_scalar(
            "SELECT status FROM federation_peers WHERE sovereign_a_id = $1 AND sovereign_b_id = $2 AND status = 'superseded'"
        )
        .bind(sovereign_a)
        .bind(sovereign_b)
        .fetch_one(&pool)
        .await
        .unwrap();
        assert_eq!(old_status_after, "superseded");

        // Verify new agreement is active with new tier
        let new_tier: i16 = sqlx::query_scalar(
            "SELECT max_admitted_tier FROM federation_peers WHERE id = $1"
        )
        .bind(new_agreement_id)
        .fetch_one(&pool)
        .await
        .unwrap();
        assert_eq!(new_tier, 5);

        // Verify signature is stored
        let sig: String = sqlx::query_scalar(
            "SELECT agreement_signature FROM federation_peers WHERE id = $1"
        )
        .bind(new_agreement_id)
        .fetch_one(&pool)
        .await
        .unwrap();
        assert_eq!(sig, "new-sig-bytes");
    }

    #[tokio::test]
    async fn test_renegotiate_lookup_returns_new_tier() {
        let (_container, pool) = setup_postgres().await;

        let sovereign_a = Uuid::new_v4();
        let sovereign_b = Uuid::new_v4();

        // Setup sovereigns
        sqlx::query("INSERT INTO sovereigns (id, name, public_key_pem) VALUES ($1, $2, $3)")
            .bind(sovereign_a)
            .bind("Sovereign A")
            .bind("key-a")
            .execute(&pool)
            .await
            .unwrap();

        sqlx::query("INSERT INTO sovereigns (id, name, public_key_pem) VALUES ($1, $2, $3)")
            .bind(sovereign_b)
            .bind("Sovereign B")
            .bind("key-b")
            .execute(&pool)
            .await
            .unwrap();

        // Insert initial agreement with tier 3
        sqlx::query(
            "INSERT INTO federation_peers (sovereign_a_id, sovereign_b_id, max_admitted_tier, granted_attestation_types, foreign_agent_budget_cap) \
             VALUES ($1, $2, $3, $4, $5)"
        )
        .bind(sovereign_a)
        .bind(sovereign_b)
        .bind(3i16)
        .bind(vec!["SovereignOrigin"])
        .bind(500000i64)
        .execute(&pool)
        .await
        .unwrap();

        // Lookup should return tier 3
        let (tier, _types, _cap) = lookup_federation_peer(&pool, sovereign_a, sovereign_b)
            .await
            .unwrap()
            .unwrap();
        assert_eq!(tier, 3);

        // Renegotiate to tier 7
        renegotiate_federation_agreement(
            &pool,
            sovereign_a,
            sovereign_b,
            7i16,
            vec!["SovereignOrigin".to_string()],
            750000i64,
            None,
            "sig",
        )
        .await
        .unwrap();

        // Lookup should now return tier 7
        let (new_tier, _types, _cap) = lookup_federation_peer(&pool, sovereign_a, sovereign_b)
            .await
            .unwrap()
            .unwrap();
        assert_eq!(new_tier, 7);
    }

    #[tokio::test]
    async fn test_generate_settlement_invoice_aggregates_tokens() {
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

        // Insert two credit entries: 500 + 750 = 1250 total
        insert_sovereign_credit_entry(&pool, creditor, debtor, session1, 500i64)
            .await
            .unwrap();

        insert_sovereign_credit_entry(&pool, creditor, debtor, session2, 750i64)
            .await
            .unwrap();

        // Generate invoice
        let now = Utc::now();
        let (invoice_id, total_tokens, entry_count) = generate_settlement_invoice(
            &pool,
            creditor,
            debtor,
            now - chrono::Duration::hours(1),
            now + chrono::Duration::hours(1),
            "canonical_payload_123",
            "sig-bytes",
        )
        .await
        .unwrap();

        assert_ne!(invoice_id, Uuid::nil());
        assert_eq!(total_tokens, 1250);
        assert_eq!(entry_count, 2);

        // Verify invoice exists
        let status: String = sqlx::query_scalar(
            "SELECT status FROM settlement_invoices WHERE id = $1"
        )
        .bind(invoice_id)
        .fetch_one(&pool)
        .await
        .unwrap();
        assert_eq!(status, "pending");
    }

    #[tokio::test]
    async fn test_generate_invoice_links_entries_to_invoice_id() {
        let (_container, pool) = setup_postgres().await;

        let creditor = Uuid::new_v4();
        let debtor = Uuid::new_v4();
        let session = Uuid::new_v4();

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

        // Verify invoice_id is NULL before generation
        let invoice_id_before: Option<String> = sqlx::query_scalar(
            "SELECT invoice_id::text FROM sovereign_credit_entries \
             WHERE creditor_sovereign_id = $1 AND debtor_sovereign_id = $2 LIMIT 1"
        )
        .bind(creditor)
        .bind(debtor)
        .fetch_one(&pool)
        .await
        .unwrap();
        assert!(invoice_id_before.is_none());

        // Generate invoice
        let now = Utc::now();
        let (invoice_id, _, _) = generate_settlement_invoice(
            &pool,
            creditor,
            debtor,
            now - chrono::Duration::hours(1),
            now + chrono::Duration::hours(1),
            "payload",
            "sig",
        )
        .await
        .unwrap();

        // Verify entry now links to invoice
        let linked_invoice_id: Option<String> = sqlx::query_scalar(
            "SELECT invoice_id::text FROM sovereign_credit_entries \
             WHERE creditor_sovereign_id = $1 AND debtor_sovereign_id = $2 LIMIT 1"
        )
        .bind(creditor)
        .bind(debtor)
        .fetch_one(&pool)
        .await
        .unwrap();
        assert_eq!(linked_invoice_id, Some(invoice_id.to_string()));
    }

    #[tokio::test]
    async fn test_mark_invoice_settled() {
        let (_container, pool) = setup_postgres().await;

        let creditor = Uuid::new_v4();
        let debtor = Uuid::new_v4();

        // Setup sovereigns
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

        // Insert invoice directly
        let invoice_id = Uuid::new_v4();
        let now = Utc::now();
        sqlx::query(
            "INSERT INTO settlement_invoices \
             (id, creditor_sovereign_id, debtor_sovereign_id, period_start, period_end, \
              total_tokens, entry_count, invoice_hash, invoice_signature, status) \
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'pending')"
        )
        .bind(invoice_id)
        .bind(creditor)
        .bind(debtor)
        .bind(now)
        .bind(now)
        .bind(1000i64)
        .bind(1i32)
        .bind("hash")
        .bind("sig")
        .execute(&pool)
        .await
        .unwrap();

        // Mark as settled
        let result = mark_invoice_settled(&pool, invoice_id, debtor).await.unwrap();
        assert!(result, "First settle should succeed");

        // Verify status changed
        let status: String = sqlx::query_scalar(
            "SELECT status FROM settlement_invoices WHERE id = $1"
        )
        .bind(invoice_id)
        .fetch_one(&pool)
        .await
        .unwrap();
        assert_eq!(status, "settled");

        // Verify settled_at is set
        let settled_at: Option<String> = sqlx::query_scalar(
            "SELECT settled_at::text FROM settlement_invoices WHERE id = $1"
        )
        .bind(invoice_id)
        .fetch_one(&pool)
        .await
        .unwrap();
        assert!(settled_at.is_some());

        // Second settle should be idempotent (return false)
        let result2 = mark_invoice_settled(&pool, invoice_id, debtor).await.unwrap();
        assert!(!result2, "Second settle should return false (already settled)");
    }

    #[tokio::test]
    async fn test_mark_invoice_settled_wrong_debtor() {
        let (_container, pool) = setup_postgres().await;

        let creditor = Uuid::new_v4();
        let debtor = Uuid::new_v4();
        let wrong_debtor = Uuid::new_v4();

        // Setup sovereigns
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

        sqlx::query("INSERT INTO sovereigns (id, name, public_key_pem) VALUES ($1, $2, $3)")
            .bind(wrong_debtor)
            .bind("Wrong Debtor")
            .bind("key")
            .execute(&pool)
            .await
            .unwrap();

        // Insert invoice
        let invoice_id = Uuid::new_v4();
        let now = Utc::now();
        sqlx::query(
            "INSERT INTO settlement_invoices \
             (id, creditor_sovereign_id, debtor_sovereign_id, period_start, period_end, \
              total_tokens, entry_count, invoice_hash, invoice_signature, status) \
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'pending')"
        )
        .bind(invoice_id)
        .bind(creditor)
        .bind(debtor)
        .bind(now)
        .bind(now)
        .bind(1000i64)
        .bind(1i32)
        .bind("hash")
        .bind("sig")
        .execute(&pool)
        .await
        .unwrap();

        // Attempt to settle as wrong debtor
        let result = mark_invoice_settled(&pool, invoice_id, wrong_debtor).await.unwrap();
        assert!(!result, "Wrong debtor should not be able to settle");

        // Verify status is still pending
        let status: String = sqlx::query_scalar(
            "SELECT status FROM settlement_invoices WHERE id = $1"
        )
        .bind(invoice_id)
        .fetch_one(&pool)
        .await
        .unwrap();
        assert_eq!(status, "pending");
    }

    #[tokio::test]
    async fn test_insert_revocation_from_gossip_idempotent() {
        let (_container, pool) = setup_postgres().await;

        let sovereign = Uuid::new_v4();
        sqlx::query("INSERT INTO sovereigns (id, name, public_key_pem) VALUES ($1, $2, $3)")
            .bind(sovereign)
            .bind("Sovereign")
            .bind("key")
            .execute(&pool)
            .await
            .unwrap();

        let now = Utc::now();

        // Insert first revocation
        let result1 = insert_revocation_from_gossip(&pool, "alice", sovereign, now, "sig-1")
            .await
            .unwrap();

        // Insert duplicate (same agent_id, same source_sovereign_id)
        let result2 = insert_revocation_from_gossip(&pool, "alice", sovereign, now, "sig-1")
            .await
            .unwrap();

        // Both should return a UUID (idempotent)
        assert_ne!(result1, Uuid::nil());
        assert_ne!(result2, Uuid::nil());
        // Second insert should return the same UUID as the first
        assert_eq!(result1, result2);

        // Verify only one row in DB
        let count: i64 = sqlx::query_scalar(
            "SELECT COUNT(*) FROM revocation_certificates WHERE agent_id = 'alice' AND source_sovereign_id = $1"
        )
        .bind(sovereign)
        .fetch_one(&pool)
        .await
        .unwrap();
        assert_eq!(count, 1);
    }

    #[tokio::test]
    async fn test_list_active_peer_endpoints() {
        let (_container, pool) = setup_postgres().await;

        let sovereign_a = Uuid::new_v4();
        let sovereign_b = Uuid::new_v4();
        let sovereign_c = Uuid::new_v4();

        // Setup sovereigns
        sqlx::query("INSERT INTO sovereigns (id, name, public_key_pem, endpoint_url) VALUES ($1, $2, $3, $4)")
            .bind(sovereign_a)
            .bind("Sovereign A")
            .bind("key-a")
            .bind("https://a.example.com/gossip")
            .execute(&pool)
            .await
            .unwrap();

        sqlx::query("INSERT INTO sovereigns (id, name, public_key_pem, endpoint_url) VALUES ($1, $2, $3, $4)")
            .bind(sovereign_b)
            .bind("Sovereign B")
            .bind("key-b")
            .bind("https://b.example.com/gossip")
            .execute(&pool)
            .await
            .unwrap();

        sqlx::query("INSERT INTO sovereigns (id, name, public_key_pem, endpoint_url) VALUES ($1, $2, $3, $4)")
            .bind(sovereign_c)
            .bind("Sovereign C")
            .bind("key-c")
            .bind(None::<&str>) // No endpoint
            .execute(&pool)
            .await
            .unwrap();

        // Insert active agreements: A → B and A → C
        sqlx::query(
            "INSERT INTO federation_peers (sovereign_a_id, sovereign_b_id, max_admitted_tier, granted_attestation_types, foreign_agent_budget_cap) \
             VALUES ($1, $2, $3, $4, $5)"
        )
        .bind(sovereign_a)
        .bind(sovereign_b)
        .bind(3i16)
        .bind(vec!["SovereignOrigin"])
        .bind(500000i64)
        .execute(&pool)
        .await
        .unwrap();

        sqlx::query(
            "INSERT INTO federation_peers (sovereign_a_id, sovereign_b_id, max_admitted_tier, granted_attestation_types, foreign_agent_budget_cap) \
             VALUES ($1, $2, $3, $4, $5)"
        )
        .bind(sovereign_a)
        .bind(sovereign_c)
        .bind(3i16)
        .bind(vec!["SovereignOrigin"])
        .bind(500000i64)
        .execute(&pool)
        .await
        .unwrap();

        // List endpoints from sovereign_a
        let endpoints = list_active_peer_endpoints(&pool, sovereign_a).await.unwrap();

        // Should only include B (has endpoint), not C (endpoint_url is NULL)
        assert_eq!(endpoints.len(), 1);
        assert_eq!(endpoints[0].0, sovereign_b);
        assert_eq!(endpoints[0].1, "https://b.example.com/gossip");
    }
}
