use chrono::{DateTime, Utc};
use sqlx::PgPool;
use uuid::Uuid;

/// Insert a new refresh challenge nonce for pull-based refresh flow.
///
/// Creates a single-use challenge that an agent must respond to with
/// fresh attestations and a nonce-signed proof.
///
/// Returns the challenge ID.
pub async fn insert_challenge(
    pool: &PgPool,
    session_id: Uuid,
    nonce: &str,
    required_attestations: &[String],
    expires_at: DateTime<Utc>,
) -> Result<Uuid, sqlx::Error> {
    let id = Uuid::new_v4();
    sqlx::query(
        "INSERT INTO refresh_challenges (id, session_id, nonce, required_attestations, expires_at) \
         VALUES ($1, $2, $3, $4, $5)",
    )
    .bind(id)
    .bind(session_id)
    .bind(nonce)
    .bind(required_attestations)
    .bind(expires_at)
    .execute(pool)
    .await?;

    Ok(id)
}

/// Fetch a challenge by nonce and atomically mark it as consumed (single-use enforcement).
///
/// Returns:
/// - `(id, expires_at)` if challenge found, non-expired, and not yet consumed
/// - `None` if challenge missing, expired, or already consumed
///
/// The atomicity ensures the same nonce cannot be used twice even in concurrent requests.
pub async fn fetch_and_consume_challenge(
    pool: &PgPool,
    session_id: Uuid,
    nonce: &str,
) -> Result<Option<(Uuid, DateTime<Utc>)>, sqlx::Error> {
    let row: Option<(Uuid, DateTime<Utc>)> = sqlx::query_as(
        "UPDATE refresh_challenges \
         SET consumed = TRUE \
         WHERE session_id = $1 \
           AND nonce = $2 \
           AND NOT consumed \
           AND expires_at > NOW() \
         RETURNING id, expires_at",
    )
    .bind(session_id)
    .bind(nonce)
    .fetch_optional(pool)
    .await?;

    Ok(row)
}

#[cfg(test)]
mod tests {
    use super::*;
    use testcontainers::{GenericImage, ImageExt, core::WaitFor, runners::AsyncRunner};

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

    async fn create_test_session(pool: &PgPool) -> Uuid {
        let tenant_id = crate::repo::node_repo::insert_tenant(pool, "ChallengeCorp")
            .await
            .expect("insert tenant");
        let persona_id =
            crate::repo::node_repo::insert_persona(pool, "ChallengeAgent", "ai_agent", tenant_id)
                .await
                .expect("insert persona");

        let now = Utc::now();
        let expires_at = now + chrono::Duration::hours(1);
        crate::repo::session_repo::insert_session_with_tokens(
            pool,
            tenant_id,
            persona_id,
            100_000,
            "challenge-session-token",
            "challenge-cap-token",
            80,
            2,
            expires_at,
        )
        .await
        .expect("insert session")
    }

    #[tokio::test]
    async fn test_insert_challenge() {
        let (_container, pool) = start_postgres().await;
        let session_id = create_test_session(&pool).await;

        let now = Utc::now();
        let expires_at = now + chrono::Duration::minutes(5);
        let nonce = "test-nonce-abc123";
        let required = vec!["hardware".to_string(), "model".to_string()];

        let challenge_id = insert_challenge(&pool, session_id, nonce, &required, expires_at)
            .await
            .expect("insert challenge");

        assert_ne!(challenge_id, Uuid::nil());
    }

    #[tokio::test]
    async fn test_fetch_and_consume_challenge_success() {
        let (_container, pool) = start_postgres().await;
        let session_id = create_test_session(&pool).await;

        let now = Utc::now();
        let expires_at = now + chrono::Duration::minutes(5);
        let nonce = "consume-nonce-xyz";
        let required = vec!["hardware".to_string()];

        let _challenge_id = insert_challenge(&pool, session_id, nonce, &required, expires_at)
            .await
            .expect("insert");

        // First fetch should succeed
        let result = fetch_and_consume_challenge(&pool, session_id, nonce)
            .await
            .expect("fetch")
            .expect("challenge found");

        assert_ne!(result.0, Uuid::nil());
        assert!(result.1 > now);
    }

    #[tokio::test]
    async fn test_fetch_and_consume_challenge_single_use() {
        let (_container, pool) = start_postgres().await;
        let session_id = create_test_session(&pool).await;

        let now = Utc::now();
        let expires_at = now + chrono::Duration::minutes(5);
        let nonce = "single-use-nonce";
        let required = vec!["hardware".to_string()];

        let _challenge_id = insert_challenge(&pool, session_id, nonce, &required, expires_at)
            .await
            .expect("insert");

        // First use succeeds
        let first = fetch_and_consume_challenge(&pool, session_id, nonce)
            .await
            .expect("first fetch");
        assert!(first.is_some());

        // Second use fails (already consumed)
        let second = fetch_and_consume_challenge(&pool, session_id, nonce)
            .await
            .expect("second fetch");
        assert!(second.is_none());
    }

    #[tokio::test]
    async fn test_fetch_and_consume_challenge_expired() {
        let (_container, pool) = start_postgres().await;
        let session_id = create_test_session(&pool).await;

        let now = Utc::now();
        let expires_at = now - chrono::Duration::minutes(1); // Already expired
        let nonce = "expired-nonce";
        let required = vec!["hardware".to_string()];

        let _challenge_id = insert_challenge(&pool, session_id, nonce, &required, expires_at)
            .await
            .expect("insert");

        // Fetch fails (expired)
        let result = fetch_and_consume_challenge(&pool, session_id, nonce)
            .await
            .expect("fetch");
        assert!(result.is_none());
    }

    #[tokio::test]
    async fn test_fetch_and_consume_challenge_not_found() {
        let (_container, pool) = start_postgres().await;
        let session_id = create_test_session(&pool).await;

        // Try to fetch non-existent challenge
        let result = fetch_and_consume_challenge(&pool, session_id, "nonexistent-nonce")
            .await
            .expect("fetch");
        assert!(result.is_none());
    }
}
