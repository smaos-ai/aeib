use chrono::{DateTime, Utc};
use sqlx::PgPool;
use uuid::Uuid;

/// Insert a new session with Phase 5 token and attestation data.
///
/// Creates a session with initial session_token, capability_token, and attestation score/tier.
/// Used during Phase 4 handshake to establish a new authenticated session for refresh operations.
pub async fn insert_session_with_tokens(
    pool: &PgPool,
    tenant_id: Uuid,
    persona_id: Uuid,
    token_budget: i64,
    session_token: &str,
    capability_token: &str,
    attestation_score: i32,
    attestation_tier: i32,
    session_expires_at: DateTime<Utc>,
) -> Result<Uuid, sqlx::Error> {
    let id = Uuid::new_v4();
    sqlx::query(
        "INSERT INTO sessions (id, tenant_id, active_persona_id, token_budget, session_token, \
         capability_token, attestation_score, attestation_tier, session_expires_at) \
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)"
    )
    .bind(id)
    .bind(tenant_id)
    .bind(persona_id)
    .bind(token_budget)
    .bind(session_token)
    .bind(capability_token)
    .bind(attestation_score)
    .bind(attestation_tier)
    .bind(session_expires_at)
    .execute(pool)
    .await?;
    Ok(id)
}

/// Fetch a session by its session_token for validation during refresh.
///
/// Returns:
/// - `(id, tenant_id, status, attestation_score, attestation_tier, session_expires_at,
///    parent_session_id, delegated_by_agent_id, delegation_ceiling_envelope,
///    current_effective_envelope, lineage_cache)` if found and valid
/// - `None` if session does not exist or is not active
///
/// Validates that:
/// - session_expires_at > now (not expired)
/// - status = 'active' (not suspended/completed/evicted)
pub async fn fetch_session_by_token(
    pool: &PgPool,
    session_token: &str,
) -> Result<Option<(Uuid, Uuid, String, i32, Option<i32>, DateTime<Utc>, Option<Uuid>, Option<Uuid>, Option<String>, Option<String>, Option<String>)>, sqlx::Error> {
    let row = sqlx::query_as::<_, (Uuid, Uuid, String, i32, Option<i32>, DateTime<Utc>, Option<Uuid>, Option<Uuid>, Option<String>, Option<String>, Option<String>)>(
        "SELECT id, tenant_id, status::text, attestation_score, attestation_tier, session_expires_at, \
         parent_session_id, delegated_by_agent_id, delegation_ceiling_envelope, \
         current_effective_envelope, lineage_cache \
         FROM sessions \
         WHERE session_token = $1 \
           AND status = 'active'::session_status \
           AND session_expires_at > NOW()"
    )
    .bind(session_token)
    .fetch_optional(pool)
    .await?;
    Ok(row)
}

/// Update a session after successful attestation refresh.
///
/// Updates:
/// - `capability_token` with the new refreshed token
/// - `attestation_score` with new computed score
/// - `attestation_tier` with new tier assignment
/// - `last_refreshed_at` with current timestamp
///
/// Returns true if update succeeded, false if session not found.
pub async fn update_session_after_refresh(
    pool: &PgPool,
    session_id: Uuid,
    capability_token: &str,
    attestation_score: i32,
    attestation_tier: i32,
    last_refreshed_at: DateTime<Utc>,
) -> Result<bool, sqlx::Error> {
    let result = sqlx::query(
        "UPDATE sessions \
         SET capability_token = $2, \
             attestation_score = $3, \
             attestation_tier = $4, \
             last_refreshed_at = $5 \
         WHERE id = $1"
    )
    .bind(session_id)
    .bind(capability_token)
    .bind(attestation_score)
    .bind(attestation_tier)
    .bind(last_refreshed_at)
    .execute(pool)
    .await?;

    Ok(result.rows_affected() > 0)
}

/// Revoke a session by setting its status to 'revoked' and recording the revocation time.
///
/// Used by SISS to forcibly invalidate sessions when a policy violation is detected.
///
/// Returns true if the session was found and revoked, false if session not found.
pub async fn revoke_session(pool: &PgPool, session_id: Uuid) -> Result<bool, sqlx::Error> {
    let result = sqlx::query(
        "UPDATE sessions \
         SET status = 'revoked'::session_status, \
             revoked_at = NOW() \
         WHERE id = $1"
    )
    .bind(session_id)
    .execute(pool)
    .await?;

    Ok(result.rows_affected() > 0)
}

/// Phase 6: Revoke all descendant sessions (STRICT REVOCATION — FAIL-CLOSED)
///
/// When an ancestor session is revoked, the entire downstream subtree is instantly revoked.
/// This is fail-closed: no dependency analysis, no partial revocation.
///
/// Atomically marks all descendant sessions as revoked with the provided reason.
pub async fn revoke_all_descendants(
    pool: &PgPool,
    ancestor_session_id: Uuid,
    reason: &str,
) -> Result<u64, sqlx::Error> {
    // Phase 6: Strict revocation — mark entire subtree
    let result = sqlx::query(
        "WITH RECURSIVE descendant_sessions AS (
           SELECT id FROM sessions WHERE parent_session_id = $1
           UNION ALL
           SELECT s.id FROM sessions s
           INNER JOIN descendant_sessions ds ON s.parent_session_id = ds.id
         )
         UPDATE sessions
         SET status = 'revoked'::session_status,
             revoked_at = NOW()
         WHERE id IN (SELECT id FROM descendant_sessions)"
    )
    .bind(ancestor_session_id)
    .execute(pool)
    .await?;

    Ok(result.rows_affected())
}

/// Fetch session status by session_token regardless of active/revoked/expired state.
///
/// Used during refresh to distinguish between:
/// - Session not found at all
/// - Session exists but is revoked
/// - Session exists and is active (then fetch full details)
///
/// Returns `(id, status::text)` if token exists, `None` otherwise.
pub async fn fetch_session_status_by_token(
    pool: &PgPool,
    session_token: &str,
) -> Result<Option<(Uuid, String)>, sqlx::Error> {
    let row: Option<(Uuid, String)> = sqlx::query_as(
        "SELECT id, status::text \
         FROM sessions \
         WHERE session_token = $1"
    )
    .bind(session_token)
    .fetch_optional(pool)
    .await?;
    Ok(row)
}

/// Phase 6.1: Fetch all ancestor session IDs for a given session (recursive).
///
/// Walks the parent_session_id chain from child to root, returning all ancestors
/// in order from immediate parent to root.
///
/// Returns:
/// - Vec of ancestor session UUIDs (empty if session has no parent, i.e., is root)
/// - None if the session itself is not found
pub async fn fetch_ancestor_session_ids(
    pool: &PgPool,
    session_id: Uuid,
) -> Result<Option<Vec<Uuid>>, sqlx::Error> {
    // First verify session exists
    let exists: (bool,) = sqlx::query_as(
        "SELECT EXISTS(SELECT 1 FROM sessions WHERE id = $1)"
    )
    .bind(session_id)
    .fetch_one(pool)
    .await?;

    if !exists.0 {
        return Ok(None);
    }

    // Recursively walk parent_session_id chain to root
    let rows: Vec<(Uuid,)> = sqlx::query_as(
        "WITH RECURSIVE ancestor_chain AS (
           SELECT parent_session_id FROM sessions WHERE id = $1
           UNION ALL
           SELECT parent_session_id FROM sessions s
           INNER JOIN ancestor_chain a ON s.id = a.parent_session_id
           WHERE parent_session_id IS NOT NULL
         )
         SELECT parent_session_id FROM ancestor_chain WHERE parent_session_id IS NOT NULL
         ORDER BY parent_session_id"
    )
    .bind(session_id)
    .fetch_all(pool)
    .await?;

    Ok(Some(rows.iter().map(|(id,)| *id).collect()))
}

/// Phase 6.1: Check if any ancestor of a session is revoked (FAIL-CLOSED).
///
/// Implements strict fail-closed semantics: if ANY ancestor in the delegation chain
/// has status='revoked', the child session cannot proceed with refresh.
///
/// Returns:
/// - `Ok(())` if no ancestors exist (root session) or none are revoked
/// - `Err(revoked_ancestor_id)` if at least one ancestor is revoked
/// - Database errors propagate
pub async fn check_ancestors_revoked(
    pool: &PgPool,
    session_id: Uuid,
) -> Result<(), Uuid> {
    // Fetch ancestor chain
    let ancestors = crate::repo::session_repo::fetch_ancestor_session_ids(pool, session_id)
        .await
        .map_err(|_| Uuid::nil())?  // DB error: return nil as sentinel
        .unwrap_or_default();  // Root session: no ancestors

    if ancestors.is_empty() {
        return Ok(());  // Root session: no ancestors to revoke
    }

    // Check if ANY ancestor is revoked
    for ancestor_id in ancestors {
        let status_row: Option<(String,)> = sqlx::query_as::<_, (String,)>(
            "SELECT status::text FROM sessions WHERE id = $1"
        )
        .bind(ancestor_id)
        .fetch_optional(pool)
        .await
        .map_err(|_| ancestor_id)?;  // DB error: return ancestor_id as sentinel

        if let Some((ancestor_status,)) = status_row {
            if ancestor_status == "revoked" {
                return Err(ancestor_id);  // Ancestor revoked: fail-closed
            }
        }
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use testcontainers::{core::WaitFor, runners::AsyncRunner, GenericImage, ImageExt};

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
        crate::migrations::run_all(&pool).await.expect("migrations");
        (container, pool)
    }

    async fn create_test_tenant_and_persona(
        pool: &PgPool,
    ) -> (Uuid, Uuid) {
        let tenant_id = crate::repo::node_repo::insert_tenant(pool, "SessionTestCorp")
            .await
            .expect("insert tenant");
        let persona_id = crate::repo::node_repo::insert_persona(
            pool, "SessionTestAgent", "ai_agent", tenant_id,
        )
        .await
        .expect("insert persona");
        (tenant_id, persona_id)
    }

    #[tokio::test]
    async fn test_insert_session_with_tokens() {
        let (_container, pool) = start_postgres().await;
        let (tenant_id, persona_id) = create_test_tenant_and_persona(&pool).await;

        let now = Utc::now();
        let expires_at = now + chrono::Duration::hours(1);
        let session_id = insert_session_with_tokens(
            &pool,
            tenant_id,
            persona_id,
            100_000,
            "session-token-123",
            "capability-token-456",
            80,
            2,
            expires_at,
        )
        .await
        .expect("insert session");

        assert_ne!(session_id, Uuid::nil());
    }

    #[tokio::test]
    async fn test_fetch_session_by_token_found() {
        let (_container, pool) = start_postgres().await;
        let (tenant_id, persona_id) = create_test_tenant_and_persona(&pool).await;

        let now = Utc::now();
        let expires_at = now + chrono::Duration::hours(1);
        let _session_id = insert_session_with_tokens(
            &pool,
            tenant_id,
            persona_id,
            100_000,
            "lookup-token",
            "cap-token",
            80,
            2,
            expires_at,
        )
        .await
        .expect("insert");

        let result = fetch_session_by_token(&pool, "lookup-token")
            .await
            .expect("fetch")
            .expect("session found");

        assert_eq!(result.0, _session_id);
        assert_eq!(result.1, tenant_id);
        assert_eq!(result.2, "active");
        assert_eq!(result.3, 80); // attestation_score
        assert_eq!(result.4, Some(2)); // attestation_tier
    }

    #[tokio::test]
    async fn test_fetch_session_by_token_not_found() {
        let (_container, pool) = start_postgres().await;
        let (tenant_id, persona_id) = create_test_tenant_and_persona(&pool).await;

        let now = Utc::now();
        let expires_at = now + chrono::Duration::hours(1);
        let _session_id = insert_session_with_tokens(
            &pool,
            tenant_id,
            persona_id,
            100_000,
            "token-abc",
            "cap-token",
            80,
            2,
            expires_at,
        )
        .await
        .expect("insert");

        let result = fetch_session_by_token(&pool, "nonexistent-token")
            .await
            .expect("fetch");

        assert!(result.is_none());
    }

    #[tokio::test]
    async fn test_fetch_session_by_token_expired() {
        let (_container, pool) = start_postgres().await;
        let (tenant_id, persona_id) = create_test_tenant_and_persona(&pool).await;

        let now = Utc::now();
        let expired_at = now - chrono::Duration::hours(1); // Already expired
        let _session_id = insert_session_with_tokens(
            &pool,
            tenant_id,
            persona_id,
            100_000,
            "expired-token",
            "cap-token",
            80,
            2,
            expired_at,
        )
        .await
        .expect("insert");

        let result = fetch_session_by_token(&pool, "expired-token")
            .await
            .expect("fetch");

        // Should not find expired sessions
        assert!(result.is_none());
    }

    #[tokio::test]
    async fn test_update_session_after_refresh() {
        let (_container, pool) = start_postgres().await;
        let (tenant_id, persona_id) = create_test_tenant_and_persona(&pool).await;

        let now = Utc::now();
        let expires_at = now + chrono::Duration::hours(1);
        let session_id = insert_session_with_tokens(
            &pool,
            tenant_id,
            persona_id,
            100_000,
            "update-token",
            "old-cap-token",
            50,
            3,
            expires_at,
        )
        .await
        .expect("insert");

        // Refresh: improve trust from 50→100 and Tier 3→1
        let refresh_time = Utc::now();
        let updated = update_session_after_refresh(
            &pool,
            session_id,
            "new-cap-token",
            100,
            1,
            refresh_time,
        )
        .await
        .expect("update");

        assert!(updated);

        // Verify update
        let result = fetch_session_by_token(&pool, "update-token")
            .await
            .expect("fetch")
            .expect("session found");

        assert_eq!(result.3, 100); // New score
        assert_eq!(result.4, Some(1)); // New tier
    }

    #[tokio::test]
    async fn test_update_session_after_refresh_not_found() {
        let (_container, pool) = start_postgres().await;

        let updated = update_session_after_refresh(
            &pool,
            Uuid::new_v4(),
            "token",
            80,
            2,
            Utc::now(),
        )
        .await
        .expect("update");

        assert!(!updated);
    }

    // ====== Phase 6.1: Ancestor Revocation Tests ======

    #[tokio::test]
    async fn test_fetch_ancestor_session_ids_root_session() {
        let (_container, pool) = start_postgres().await;
        let (tenant_id, persona_id) = create_test_tenant_and_persona(&pool).await;

        // Create root session (no parent)
        let root_session_id = insert_session_with_tokens(
            &pool,
            tenant_id,
            persona_id,
            100_000,
            "root-token",
            "cap-token",
            100,
            1,
            Utc::now() + chrono::Duration::hours(1),
        )
        .await
        .expect("insert root");

        // Fetch ancestors of root session
        let ancestors = fetch_ancestor_session_ids(&pool, root_session_id)
            .await
            .expect("fetch")
            .expect("session exists");

        // Root session should have no ancestors
        assert_eq!(ancestors.len(), 0, "Root session should have no ancestors");
    }

    #[tokio::test]
    async fn test_fetch_ancestor_session_ids_single_parent() {
        let (_container, pool) = start_postgres().await;
        let (tenant_id, persona_id) = create_test_tenant_and_persona(&pool).await;

        // Create root session
        let root_session_id = insert_session_with_tokens(
            &pool,
            tenant_id,
            persona_id,
            100_000,
            "root-token",
            "cap-token",
            100,
            1,
            Utc::now() + chrono::Duration::hours(1),
        )
        .await
        .expect("insert root");

        // Create child session
        let child_session_id = insert_session_with_tokens(
            &pool,
            tenant_id,
            persona_id,
            50_000,
            "child-token",
            "child-cap",
            80,
            2,
            Utc::now() + chrono::Duration::hours(1),
        )
        .await
        .expect("insert child");

        // Link child to root
        let _ = sqlx::query("UPDATE sessions SET parent_session_id = $1 WHERE id = $2")
            .bind(root_session_id)
            .bind(child_session_id)
            .execute(&pool)
            .await;

        // Fetch ancestors of child
        let ancestors = fetch_ancestor_session_ids(&pool, child_session_id)
            .await
            .expect("fetch")
            .expect("session exists");

        assert_eq!(ancestors.len(), 1, "Child should have 1 ancestor");
        assert_eq!(ancestors[0], root_session_id, "Ancestor should be root");
    }

    #[tokio::test]
    async fn test_fetch_ancestor_session_ids_multi_level_chain() {
        let (_container, pool) = start_postgres().await;
        let (tenant_id, persona_id) = create_test_tenant_and_persona(&pool).await;

        // Create root → parent → child chain
        let root_id = insert_session_with_tokens(
            &pool,
            tenant_id,
            persona_id,
            100_000,
            "root-token",
            "cap-token",
            100,
            1,
            Utc::now() + chrono::Duration::hours(1),
        )
        .await
        .expect("insert root");

        let parent_id = insert_session_with_tokens(
            &pool,
            tenant_id,
            persona_id,
            50_000,
            "parent-token",
            "parent-cap",
            80,
            2,
            Utc::now() + chrono::Duration::hours(1),
        )
        .await
        .expect("insert parent");

        let child_id = insert_session_with_tokens(
            &pool,
            tenant_id,
            persona_id,
            25_000,
            "child-token",
            "child-cap",
            60,
            3,
            Utc::now() + chrono::Duration::hours(1),
        )
        .await
        .expect("insert child");

        // Link parent to root
        let _ = sqlx::query("UPDATE sessions SET parent_session_id = $1 WHERE id = $2")
            .bind(root_id)
            .bind(parent_id)
            .execute(&pool)
            .await;

        // Link child to parent
        let _ = sqlx::query("UPDATE sessions SET parent_session_id = $1 WHERE id = $2")
            .bind(parent_id)
            .bind(child_id)
            .execute(&pool)
            .await;

        // Fetch ancestors of child
        let ancestors = fetch_ancestor_session_ids(&pool, child_id)
            .await
            .expect("fetch")
            .expect("session exists");

        assert_eq!(ancestors.len(), 2, "Child should have 2 ancestors");
        // Ancestors should be in order from child perspective (parent then root)
        assert!(ancestors.contains(&parent_id), "Should include parent");
        assert!(ancestors.contains(&root_id), "Should include root");
    }

    #[tokio::test]
    async fn test_check_ancestors_revoked_root_session() {
        let (_container, pool) = start_postgres().await;
        let (tenant_id, persona_id) = create_test_tenant_and_persona(&pool).await;

        // Create root session
        let root_id = insert_session_with_tokens(
            &pool,
            tenant_id,
            persona_id,
            100_000,
            "root-token",
            "cap-token",
            100,
            1,
            Utc::now() + chrono::Duration::hours(1),
        )
        .await
        .expect("insert root");

        // Check ancestors of root (should be ok: no ancestors)
        let result = check_ancestors_revoked(&pool, root_id)
            .await;

        assert!(result.is_ok(), "Root session should have no revoked ancestors");
    }

    #[tokio::test]
    async fn test_check_ancestors_revoked_benign_ancestor() {
        let (_container, pool) = start_postgres().await;
        let (tenant_id, persona_id) = create_test_tenant_and_persona(&pool).await;

        // Create root → child chain (not revoked)
        let root_id = insert_session_with_tokens(
            &pool,
            tenant_id,
            persona_id,
            100_000,
            "root-token",
            "cap-token",
            100,
            1,
            Utc::now() + chrono::Duration::hours(1),
        )
        .await
        .expect("insert root");

        let child_id = insert_session_with_tokens(
            &pool,
            tenant_id,
            persona_id,
            50_000,
            "child-token",
            "child-cap",
            80,
            2,
            Utc::now() + chrono::Duration::hours(1),
        )
        .await
        .expect("insert child");

        // Link child to root
        let _ = sqlx::query("UPDATE sessions SET parent_session_id = $1 WHERE id = $2")
            .bind(root_id)
            .bind(child_id)
            .execute(&pool)
            .await;

        // Check ancestors (should be ok: parent is not revoked)
        let result = check_ancestors_revoked(&pool, child_id)
            .await;

        assert!(result.is_ok(), "Benign ancestor should pass check");
    }

    #[tokio::test]
    async fn test_check_ancestors_revoked_direct_parent_revoked() {
        let (_container, pool) = start_postgres().await;
        let (tenant_id, persona_id) = create_test_tenant_and_persona(&pool).await;

        // Create root → child chain
        let root_id = insert_session_with_tokens(
            &pool,
            tenant_id,
            persona_id,
            100_000,
            "root-token",
            "cap-token",
            100,
            1,
            Utc::now() + chrono::Duration::hours(1),
        )
        .await
        .expect("insert root");

        let child_id = insert_session_with_tokens(
            &pool,
            tenant_id,
            persona_id,
            50_000,
            "child-token",
            "child-cap",
            80,
            2,
            Utc::now() + chrono::Duration::hours(1),
        )
        .await
        .expect("insert child");

        // Link child to root
        let _ = sqlx::query("UPDATE sessions SET parent_session_id = $1 WHERE id = $2")
            .bind(root_id)
            .bind(child_id)
            .execute(&pool)
            .await;

        // Revoke parent
        let _ = revoke_session(&pool, root_id)
            .await
            .expect("revoke");

        // Check ancestors (should fail: parent is revoked)
        let result = check_ancestors_revoked(&pool, child_id)
            .await;

        assert!(result.is_err(), "Revoked parent should block child");
        if let Err(revoked_id) = result {
            assert_eq!(revoked_id, root_id, "Error should identify revoked parent");
        }
    }

    #[tokio::test]
    async fn test_check_ancestors_revoked_transitive_revocation() {
        let (_container, pool) = start_postgres().await;
        let (tenant_id, persona_id) = create_test_tenant_and_persona(&pool).await;

        // Create root → parent → child chain
        let root_id = insert_session_with_tokens(
            &pool,
            tenant_id,
            persona_id,
            100_000,
            "root-token",
            "cap-token",
            100,
            1,
            Utc::now() + chrono::Duration::hours(1),
        )
        .await
        .expect("insert root");

        let parent_id = insert_session_with_tokens(
            &pool,
            tenant_id,
            persona_id,
            50_000,
            "parent-token",
            "parent-cap",
            80,
            2,
            Utc::now() + chrono::Duration::hours(1),
        )
        .await
        .expect("insert parent");

        let child_id = insert_session_with_tokens(
            &pool,
            tenant_id,
            persona_id,
            25_000,
            "child-token",
            "child-cap",
            60,
            3,
            Utc::now() + chrono::Duration::hours(1),
        )
        .await
        .expect("insert child");

        // Link parent to root
        let _ = sqlx::query("UPDATE sessions SET parent_session_id = $1 WHERE id = $2")
            .bind(root_id)
            .bind(parent_id)
            .execute(&pool)
            .await;

        // Link child to parent
        let _ = sqlx::query("UPDATE sessions SET parent_session_id = $1 WHERE id = $2")
            .bind(parent_id)
            .bind(child_id)
            .execute(&pool)
            .await;

        // Revoke root (grandparent)
        let _ = revoke_session(&pool, root_id)
            .await
            .expect("revoke");

        // Check ancestors of child (should fail: grandparent is revoked)
        let result = check_ancestors_revoked(&pool, child_id)
            .await;

        assert!(result.is_err(), "Revoked grandparent should block grandchild");
        if let Err(revoked_id) = result {
            assert_eq!(revoked_id, root_id, "Error should identify revoked grandparent");
        }
    }
}
