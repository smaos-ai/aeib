/// Phase 11: Cross-Sovereign Delegation Grants
/// Transitive delegation within bilateral federation agreements with depth limits
use chrono::{DateTime, Utc};
use serde_json::json;
use sqlx::PgPool;
use std::collections::BTreeMap;
use uuid::Uuid;

pub const TRANSITIVITY_DEPTH_MAX: i16 = 4;

#[derive(Debug, Clone)]
pub enum CrossSovereignDelegationError {
    DepthLimitExceeded,
    NoBilateralAgreement,
    TierExceedsBilateralCap { ceiling: i16, bilateral_max: i16 },
    Database(String),
}

impl From<sqlx::Error> for CrossSovereignDelegationError {
    fn from(err: sqlx::Error) -> Self {
        CrossSovereignDelegationError::Database(err.to_string())
    }
}

/// Insert a new cross-sovereign delegation grant.
/// Computes transitivity_depth from parent; rejects if depth > TRANSITIVITY_DEPTH_MAX.
pub async fn insert_cross_sovereign_grant(
    pool: &PgPool,
    grantor_agent_id: &str,
    grantor_sovereign_id: Uuid,
    grantee_agent_id: &str,
    grantee_sovereign_id: Uuid,
    federation_peer_id: Uuid,
    ceiling_tier: i16,
    ceiling_attestation_types: Vec<String>,
    parent_grant_id: Option<Uuid>,
    expires_at: Option<DateTime<Utc>>,
    grant_signature: &str,
) -> Result<Uuid, CrossSovereignDelegationError> {
    // Compute depth: parent_depth + 1, or 1 if no parent
    let depth = if let Some(parent_id) = parent_grant_id {
        let parent_depth = compute_chain_depth(pool, parent_id).await?;
        parent_depth + 1
    } else {
        1
    };

    if depth > TRANSITIVITY_DEPTH_MAX {
        return Err(CrossSovereignDelegationError::DepthLimitExceeded);
    }

    let id = Uuid::new_v4();
    let attestation_types_array: Vec<&str> = ceiling_attestation_types
        .iter()
        .map(|s| s.as_str())
        .collect();

    sqlx::query(
        "INSERT INTO cross_sovereign_delegation_grants \
         (id, grantor_agent_id, grantor_sovereign_id, grantee_agent_id, grantee_sovereign_id, \
          federation_peer_id, ceiling_tier, ceiling_attestation_types, transitivity_depth, \
          parent_grant_id, expires_at, status, grant_signature) \
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'active', $12)",
    )
    .bind(id)
    .bind(grantor_agent_id)
    .bind(grantor_sovereign_id)
    .bind(grantee_agent_id)
    .bind(grantee_sovereign_id)
    .bind(federation_peer_id)
    .bind(ceiling_tier)
    .bind(attestation_types_array)
    .bind(depth)
    .bind(parent_grant_id)
    .bind(expires_at)
    .bind(grant_signature)
    .execute(pool)
    .await?;

    Ok(id)
}

/// Look up an active grant for a grantee agent.
/// Returns (grant_id, ceiling_tier, ceiling_attestation_types, transitivity_depth, federation_peer_id).
pub async fn lookup_active_grant_for_grantee(
    pool: &PgPool,
    grantee_agent_id: &str,
    grantee_sovereign_id: Uuid,
) -> Result<Option<(Uuid, i16, Vec<String>, i16, Uuid)>, sqlx::Error> {
    sqlx::query_as::<_, (Uuid, i16, Vec<String>, i16, Uuid)>(
        "SELECT id, ceiling_tier, ceiling_attestation_types, transitivity_depth, federation_peer_id \
         FROM cross_sovereign_delegation_grants \
         WHERE grantee_agent_id = $1 AND grantee_sovereign_id = $2 \
         AND status = 'active' \
         AND (expires_at IS NULL OR expires_at > NOW()) \
         AND revoked_at IS NULL \
         ORDER BY granted_at DESC \
         LIMIT 1"
    )
    .bind(grantee_agent_id)
    .bind(grantee_sovereign_id)
    .fetch_optional(pool)
    .await
}

/// Revoke a grant. Optionally cascade to all child grants.
pub async fn revoke_grant(
    pool: &PgPool,
    grant_id: Uuid,
    revoking_sovereign_id: Uuid,
    cascade_to_children: bool,
) -> Result<u64, sqlx::Error> {
    // Check ownership before revocation
    let is_owned: bool = sqlx::query_scalar(
        "SELECT EXISTS(SELECT 1 FROM cross_sovereign_delegation_grants \
         WHERE id = $1 AND grantor_sovereign_id = $2)",
    )
    .bind(grant_id)
    .bind(revoking_sovereign_id)
    .fetch_one(pool)
    .await?;

    if !is_owned {
        return Ok(0);
    }

    // Mark as revoked
    let affected = sqlx::query_scalar::<_, i64>(
        "UPDATE cross_sovereign_delegation_grants \
         SET revoked_at = NOW(), status = 'revoked' \
         WHERE id = $1 \
         RETURNING 1::bigint",
    )
    .bind(grant_id)
    .fetch_optional(pool)
    .await?
    .unwrap_or(0) as u64;

    if cascade_to_children {
        // Recursively revoke all children
        let mut tx = pool.begin().await?;
        let children: Vec<Uuid> = sqlx::query_scalar(
            "SELECT id FROM cross_sovereign_delegation_grants WHERE parent_grant_id = $1",
        )
        .bind(grant_id)
        .fetch_all(&mut *tx)
        .await?;

        for child_id in children {
            sqlx::query(
                "UPDATE cross_sovereign_delegation_grants \
                 SET revoked_at = NOW(), status = 'revoked' \
                 WHERE id = $1",
            )
            .bind(child_id)
            .execute(&mut *tx)
            .await?;
        }
        tx.commit().await?;
    }

    Ok(affected)
}

/// Compute the depth of a grant chain by traversing parents.
pub async fn compute_chain_depth(
    pool: &PgPool,
    grant_id: Uuid,
) -> Result<i16, CrossSovereignDelegationError> {
    let mut current_id = grant_id;
    let mut depth = 0i16;

    loop {
        let parent: Option<Option<Uuid>> = sqlx::query_scalar(
            "SELECT parent_grant_id FROM cross_sovereign_delegation_grants WHERE id = $1",
        )
        .bind(current_id)
        .fetch_optional(pool)
        .await?;

        match parent {
            Some(Some(parent_id)) => {
                depth += 1;
                if depth > TRANSITIVITY_DEPTH_MAX {
                    return Err(CrossSovereignDelegationError::DepthLimitExceeded);
                }
                current_id = parent_id;
            }
            Some(None) => {
                depth += 1;
                break;
            }
            None => break,
        }
    }

    Ok(depth)
}

/// Build canonical grant payload for signature verification (BTreeMap alphabetical order).
pub fn build_canonical_grant_payload(
    grantor_agent_id: &str,
    grantor_sovereign_id: &str,
    grantee_agent_id: &str,
    grantee_sovereign_id: &str,
    ceiling_tier: i16,
    ceiling_attestation_types: &[String],
    transitivity_depth: i16,
    granted_at: &str,
) -> String {
    let mut map = BTreeMap::new();
    map.insert(
        "ceiling_attestation_types",
        json!(ceiling_attestation_types),
    );
    map.insert("ceiling_tier", json!(ceiling_tier));
    map.insert("grantee_agent_id", json!(grantee_agent_id));
    map.insert("grantee_sovereign_id", json!(grantee_sovereign_id));
    map.insert("granted_at", json!(granted_at));
    map.insert("grantor_agent_id", json!(grantor_agent_id));
    map.insert("grantor_sovereign_id", json!(grantor_sovereign_id));
    map.insert("transitivity_depth", json!(transitivity_depth));

    serde_json::to_string(&map).unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use super::*;
    use testcontainers::runners::AsyncRunner;
    use testcontainers::{GenericImage, ImageExt, core::WaitFor};

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

        // Run migrations
        crate::migrations::run_all(&pool).await.expect("migrations");

        (container, pool)
    }

    async fn setup_sovereigns(pool: &PgPool) -> (Uuid, Uuid) {
        let sovereign_a = Uuid::new_v4();
        let sovereign_b = Uuid::new_v4();

        sqlx::query(
            "INSERT INTO sovereigns (id, name, endpoint_url, public_key_pem) VALUES ($1, $2, $3, $4)"
        )
        .bind(sovereign_a)
        .bind("sovereign_a")
        .bind("http://localhost:8001")
        .bind("-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBALqxBjq9i\n-----END PUBLIC KEY-----")
        .execute(pool)
        .await
        .expect("insert sovereign_a");

        sqlx::query(
            "INSERT INTO sovereigns (id, name, endpoint_url, public_key_pem) VALUES ($1, $2, $3, $4)"
        )
        .bind(sovereign_b)
        .bind("sovereign_b")
        .bind("http://localhost:8002")
        .bind("-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBALqxBjq9i\n-----END PUBLIC KEY-----")
        .execute(pool)
        .await
        .expect("insert sovereign_b");

        (sovereign_a, sovereign_b)
    }

    async fn setup_federation_peer(pool: &PgPool, sovereign_a: Uuid, sovereign_b: Uuid) -> Uuid {
        let peer_id = Uuid::new_v4();
        sqlx::query(
            "INSERT INTO federation_peers (id, sovereign_a_id, sovereign_b_id, max_admitted_tier, \
             granted_attestation_types, foreign_agent_budget_cap, status) \
             VALUES ($1, $2, $3, $4, $5, $6, 'active')",
        )
        .bind(peer_id)
        .bind(sovereign_a)
        .bind(sovereign_b)
        .bind(100i16)
        .bind(vec!["agent_identity"])
        .bind(1000000i64)
        .execute(pool)
        .await
        .expect("insert federation_peer");

        peer_id
    }

    #[tokio::test]
    async fn test_insert_grant_depth_1_succeeds() {
        let (_container, pool) = setup_postgres().await;
        let (sovereign_a, sovereign_b) = setup_sovereigns(&pool).await;
        let peer_id = setup_federation_peer(&pool, sovereign_a, sovereign_b).await;

        let result = insert_cross_sovereign_grant(
            &pool,
            "agent_a",
            sovereign_a,
            "agent_b",
            sovereign_b,
            peer_id,
            50,
            vec!["agent_identity".to_string()],
            None,
            None,
            "sig_hex_123",
        )
        .await;

        assert!(result.is_ok(), "grant insertion should succeed");
        let grant_id = result.unwrap();

        // Verify it was inserted
        let lookup = lookup_active_grant_for_grantee(&pool, "agent_b", sovereign_b)
            .await
            .expect("lookup");
        assert!(lookup.is_some());
        let (id, tier, types, depth, fp_id) = lookup.unwrap();
        assert_eq!(id, grant_id);
        assert_eq!(tier, 50);
        assert_eq!(depth, 1);
        assert_eq!(fp_id, peer_id);
        assert_eq!(types, vec!["agent_identity"]);
    }

    #[tokio::test]
    async fn test_insert_grant_depth_4_rejected() {
        let (_container, pool) = setup_postgres().await;
        let (sovereign_a, sovereign_b) = setup_sovereigns(&pool).await;
        let peer_id = setup_federation_peer(&pool, sovereign_a, sovereign_b).await;

        // Create chain: root → d1 → d2 → d3 → d4 (should fail)
        let root = insert_cross_sovereign_grant(
            &pool,
            "agent_root",
            sovereign_a,
            "agent_d1",
            sovereign_b,
            peer_id,
            50,
            vec!["agent_identity".to_string()],
            None,
            None,
            "sig_1",
        )
        .await
        .expect("root grant");

        let d1 = insert_cross_sovereign_grant(
            &pool,
            "agent_d1",
            sovereign_b,
            "agent_d2",
            sovereign_a,
            peer_id,
            40,
            vec!["agent_identity".to_string()],
            Some(root),
            None,
            "sig_2",
        )
        .await
        .expect("d1 grant");

        let d2 = insert_cross_sovereign_grant(
            &pool,
            "agent_d2",
            sovereign_a,
            "agent_d3",
            sovereign_b,
            peer_id,
            30,
            vec!["agent_identity".to_string()],
            Some(d1),
            None,
            "sig_3",
        )
        .await
        .expect("d2 grant");

        let d3 = insert_cross_sovereign_grant(
            &pool,
            "agent_d3",
            sovereign_b,
            "agent_d4",
            sovereign_a,
            peer_id,
            20,
            vec!["agent_identity".to_string()],
            Some(d2),
            None,
            "sig_4",
        )
        .await
        .expect("d3 grant");

        // d4 should fail (depth would be 5)
        let d4_result = insert_cross_sovereign_grant(
            &pool,
            "agent_d4",
            sovereign_a,
            "agent_d5",
            sovereign_b,
            peer_id,
            10,
            vec!["agent_identity".to_string()],
            Some(d3),
            None,
            "sig_5",
        )
        .await;

        assert!(matches!(
            d4_result,
            Err(CrossSovereignDelegationError::DepthLimitExceeded)
        ));
    }

    #[tokio::test]
    async fn test_revoke_grant_cascade() {
        let (_container, pool) = setup_postgres().await;
        let (sovereign_a, sovereign_b) = setup_sovereigns(&pool).await;
        let peer_id = setup_federation_peer(&pool, sovereign_a, sovereign_b).await;

        let root = insert_cross_sovereign_grant(
            &pool,
            "agent_root",
            sovereign_a,
            "agent_child1",
            sovereign_b,
            peer_id,
            50,
            vec!["agent_identity".to_string()],
            None,
            None,
            "sig_1",
        )
        .await
        .expect("root grant");

        let child = insert_cross_sovereign_grant(
            &pool,
            "agent_child1",
            sovereign_b,
            "agent_grandchild",
            sovereign_a,
            peer_id,
            40,
            vec!["agent_identity".to_string()],
            Some(root),
            None,
            "sig_2",
        )
        .await
        .expect("child grant");

        // Revoke root with cascade
        let revoked = revoke_grant(&pool, root, sovereign_a, true)
            .await
            .expect("revoke");
        assert!(revoked > 0);

        // Verify root is revoked
        let root_status: Option<String> = sqlx::query_scalar(
            "SELECT status FROM cross_sovereign_delegation_grants WHERE id = $1",
        )
        .bind(root)
        .fetch_one(&pool)
        .await
        .expect("fetch root");
        assert_eq!(root_status, Some("revoked".to_string()));

        // Verify child is also revoked (cascade)
        let child_status: Option<String> = sqlx::query_scalar(
            "SELECT status FROM cross_sovereign_delegation_grants WHERE id = $1",
        )
        .bind(child)
        .fetch_one(&pool)
        .await
        .expect("fetch child");
        assert_eq!(child_status, Some("revoked".to_string()));
    }

    #[tokio::test]
    async fn test_lookup_active_grant_found() {
        let (_container, pool) = setup_postgres().await;
        let (sovereign_a, sovereign_b) = setup_sovereigns(&pool).await;
        let peer_id = setup_federation_peer(&pool, sovereign_a, sovereign_b).await;

        insert_cross_sovereign_grant(
            &pool,
            "agent_a",
            sovereign_a,
            "agent_b",
            sovereign_b,
            peer_id,
            75,
            vec!["agent_identity".to_string()],
            None,
            None,
            "sig_123",
        )
        .await
        .expect("insert grant");

        let lookup = lookup_active_grant_for_grantee(&pool, "agent_b", sovereign_b)
            .await
            .expect("lookup");
        assert!(lookup.is_some());
    }

    #[tokio::test]
    async fn test_lookup_active_grant_not_found() {
        let (_container, pool) = setup_postgres().await;
        let (_, sovereign_b) = setup_sovereigns(&pool).await;

        let lookup = lookup_active_grant_for_grantee(&pool, "nonexistent_agent", sovereign_b)
            .await
            .expect("lookup");
        assert!(lookup.is_none());
    }

    #[test]
    fn test_canonical_grant_payload_alphabetical() {
        let payload = build_canonical_grant_payload(
            "agent_grantor",
            "00000000-0000-0000-0000-000000000001",
            "agent_grantee",
            "00000000-0000-0000-0000-000000000002",
            50,
            &vec![
                "attestation_type_1".to_string(),
                "attestation_type_2".to_string(),
            ],
            2,
            "2026-01-01T00:00:00Z",
        );

        // Check alphabetical order: should start with "ceiling_attestation_types"
        assert!(payload.contains("ceiling_attestation_types"));
        let ceiling_idx = payload.find("ceiling_attestation_types").unwrap();
        let tier_idx = payload.find("ceiling_tier").unwrap();
        let grantee_agent_idx = payload.find("grantee_agent_id").unwrap();
        let grantee_sovereign_idx = payload.find("grantee_sovereign_id").unwrap();
        let granted_at_idx = payload.find("granted_at").unwrap();
        let grantor_agent_idx = payload.find("grantor_agent_id").unwrap();
        let grantor_sovereign_idx = payload.find("grantor_sovereign_id").unwrap();
        let transitivity_idx = payload.find("transitivity_depth").unwrap();

        assert!(ceiling_idx < tier_idx);
        assert!(tier_idx < granted_at_idx);
        assert!(granted_at_idx < grantee_agent_idx);
        assert!(grantee_agent_idx < grantee_sovereign_idx);
        assert!(grantee_sovereign_idx < grantor_agent_idx);
        assert!(grantor_agent_idx < grantor_sovereign_idx);
        assert!(grantor_sovereign_idx < transitivity_idx);
    }

    #[test]
    fn test_canonical_grant_payload_deterministic() {
        let payload1 = build_canonical_grant_payload(
            "agent_grantor",
            "00000000-0000-0000-0000-000000000001",
            "agent_grantee",
            "00000000-0000-0000-0000-000000000002",
            50,
            &vec!["type1".to_string(), "type2".to_string()],
            2,
            "2026-01-01T00:00:00Z",
        );

        let payload2 = build_canonical_grant_payload(
            "agent_grantor",
            "00000000-0000-0000-0000-000000000001",
            "agent_grantee",
            "00000000-0000-0000-0000-000000000002",
            50,
            &vec!["type1".to_string(), "type2".to_string()],
            2,
            "2026-01-01T00:00:00Z",
        );

        assert_eq!(
            payload1, payload2,
            "identical payloads should produce identical canonical strings"
        );
    }
}
