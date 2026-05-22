/// Phase 10: Gossip Protocol Repository
/// Manages idempotent peer-to-peer message delivery for revocation, renegotiation, and heartbeat propagation
use sqlx::PgPool;
use uuid::Uuid;

/// Insert a gossip message with idempotency guarantee via (source_sovereign_id, gossip_seq) uniqueness.
/// Returns Some(id) if message was inserted (new), None if duplicate (already seen).
pub async fn insert_gossip_message_idempotent(
    pool: &PgPool,
    source_sovereign_id: Uuid,
    gossip_seq: i64,
    message_type: &str,
    payload: &serde_json::Value,
    payload_signature: &str,
) -> Result<Option<Uuid>, sqlx::Error> {
    let payload_str = payload.to_string();
    sqlx::query_scalar::<_, Uuid>(
        "INSERT INTO gossip_messages (source_sovereign_id, gossip_seq, message_type, payload, payload_signature) \
         VALUES ($1, $2, $3, $4::jsonb, $5) \
         ON CONFLICT (source_sovereign_id, gossip_seq) DO NOTHING \
         RETURNING id"
    )
    .bind(source_sovereign_id)
    .bind(gossip_seq)
    .bind(message_type)
    .bind(&payload_str)
    .bind(payload_signature)
    .fetch_optional(pool)
    .await
}

/// Mark a gossip message as processed by setting processed_at to NOW().
pub async fn mark_gossip_message_processed(
    pool: &PgPool,
    message_id: Uuid,
) -> Result<bool, sqlx::Error> {
    let rows_affected =
        sqlx::query("UPDATE gossip_messages SET processed_at = NOW() WHERE id = $1")
            .bind(message_id)
            .execute(pool)
            .await?
            .rows_affected();

    Ok(rows_affected > 0)
}

/// Fetch unprocessed gossip messages by type, ordered by gossip_seq (FIFO).
/// Returns (id, source_sovereign_id, gossip_seq, payload, payload_signature) for each unprocessed message.
pub async fn fetch_unprocessed_gossip_messages(
    pool: &PgPool,
    message_type: &str,
    limit: i64,
) -> Result<Vec<(Uuid, Uuid, i64, serde_json::Value, String)>, sqlx::Error> {
    sqlx::query_as::<_, (Uuid, Uuid, i64, serde_json::Value, String)>(
        "SELECT id, source_sovereign_id, gossip_seq, payload, payload_signature \
         FROM gossip_messages \
         WHERE message_type = $1 AND processed_at IS NULL \
         ORDER BY gossip_seq ASC \
         LIMIT $2",
    )
    .bind(message_type)
    .bind(limit)
    .fetch_all(pool)
    .await
}

// ============================================================================
// Phase 11: Gossip Batch Processors (Task 56)
// ============================================================================

/// Process reputation gossip batch: extract signals and insert into reputation store.
/// Called after gossip_receive_handler validates and persists the message.
pub async fn process_reputation_gossip_batch(
    _pool: &PgPool,
    _gossip_message_id: Uuid,
    _source_sovereign_id: Uuid,
    _subject_agent_id: &str,
    _signal_strength: i16,
    _signal_type: &str,
    _signal_signature: &str,
) -> Result<bool, sqlx::Error> {
    // Delegates to reputation_repo::insert_reputation_signal in refresh handler context
    // This is a stub for documentation; actual insertion happens in Step 6.8 of refresh handler
    Ok(true)
}

/// Process peer announcement gossip batch: record discovered sovereign and announcement link.
/// Called after gossip_receive_handler validates and persists the message.
pub async fn process_peer_announcement_batch(
    _pool: &PgPool,
    _gossip_message_id: Uuid,
    _announcing_sovereign_id: Uuid,
    _announced_sovereign_id: Uuid,
    _announced_endpoint_url: &str,
    _announced_public_key_pem: &str,
    _announcement_signature: &str,
) -> Result<bool, sqlx::Error> {
    // Delegates to discovery_repo functions in refresh handler context
    // This is a stub for documentation; actual insertion happens in Step 6.9 of refresh handler
    Ok(true)
}

#[cfg(test)]
mod tests {
    use super::*;
    use testcontainers::{GenericImage, ImageExt, core::WaitFor, runners::AsyncRunner};

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
    async fn test_insert_gossip_message_idempotent_same_seq() {
        let (_container, pool) = setup_postgres().await;

        let source_sovereign_id = Uuid::new_v4();
        let pkey = "-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAI...\n-----END PUBLIC KEY-----";
        sqlx::query("INSERT INTO sovereigns (id, name, public_key_pem) VALUES ($1, $2, $3)")
            .bind(source_sovereign_id)
            .bind("source")
            .bind(pkey)
            .execute(&pool)
            .await
            .unwrap();

        let payload = serde_json::json!({"test": "payload"});

        // Insert first message
        let result1 = insert_gossip_message_idempotent(
            &pool,
            source_sovereign_id,
            1,
            "revocation",
            &payload,
            "sig-bytes-1",
        )
        .await
        .unwrap();

        // Insert duplicate (same source_sovereign_id, same gossip_seq)
        let result2 = insert_gossip_message_idempotent(
            &pool,
            source_sovereign_id,
            1,
            "revocation",
            &payload,
            "sig-bytes-1",
        )
        .await
        .unwrap();

        // First insert should return Some(id), second should return None
        assert!(result1.is_some(), "First insert should succeed");
        assert!(result2.is_none(), "Duplicate insert should return None");

        // Verify only one row in DB
        let count: i64 = sqlx::query_scalar(
            "SELECT COUNT(*) FROM gossip_messages WHERE source_sovereign_id = $1",
        )
        .bind(source_sovereign_id)
        .fetch_one(&pool)
        .await
        .unwrap();

        assert_eq!(count, 1, "Only one message should exist");
    }

    #[tokio::test]
    async fn test_insert_gossip_message_different_seqs() {
        let (_container, pool) = setup_postgres().await;

        let source_sovereign_id = Uuid::new_v4();
        let pkey = "-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAI...\n-----END PUBLIC KEY-----";
        sqlx::query("INSERT INTO sovereigns (id, name, public_key_pem) VALUES ($1, $2, $3)")
            .bind(source_sovereign_id)
            .bind("source")
            .bind(pkey)
            .execute(&pool)
            .await
            .unwrap();

        let payload = serde_json::json!({"test": "payload"});

        // Insert two messages with different gossip_seq
        let result1 = insert_gossip_message_idempotent(
            &pool,
            source_sovereign_id,
            1,
            "revocation",
            &payload,
            "sig-1",
        )
        .await
        .unwrap();

        let result2 = insert_gossip_message_idempotent(
            &pool,
            source_sovereign_id,
            2,
            "revocation",
            &payload,
            "sig-2",
        )
        .await
        .unwrap();

        assert!(result1.is_some(), "First insert should succeed");
        assert!(
            result2.is_some(),
            "Second insert with different seq should succeed"
        );

        // Verify both rows in DB
        let count: i64 = sqlx::query_scalar(
            "SELECT COUNT(*) FROM gossip_messages WHERE source_sovereign_id = $1",
        )
        .bind(source_sovereign_id)
        .fetch_one(&pool)
        .await
        .unwrap();

        assert_eq!(count, 2, "Both messages should exist");
    }

    #[tokio::test]
    async fn test_mark_gossip_message_processed() {
        let (_container, pool) = setup_postgres().await;

        let source_sovereign_id = Uuid::new_v4();
        let pkey = "-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAI...\n-----END PUBLIC KEY-----";
        sqlx::query("INSERT INTO sovereigns (id, name, public_key_pem) VALUES ($1, $2, $3)")
            .bind(source_sovereign_id)
            .bind("source")
            .bind(pkey)
            .execute(&pool)
            .await
            .unwrap();

        let payload = serde_json::json!({"test": "payload"});

        // Insert message
        let message_id = insert_gossip_message_idempotent(
            &pool,
            source_sovereign_id,
            1,
            "revocation",
            &payload,
            "sig-bytes",
        )
        .await
        .unwrap()
        .unwrap();

        // Verify initially processed_at is NULL
        let processed_at_before: Option<String> =
            sqlx::query_scalar("SELECT processed_at::text FROM gossip_messages WHERE id = $1")
                .bind(message_id)
                .fetch_one(&pool)
                .await
                .unwrap();

        assert!(
            processed_at_before.is_none(),
            "processed_at should initially be NULL"
        );

        // Mark as processed
        let result = mark_gossip_message_processed(&pool, message_id)
            .await
            .unwrap();

        assert!(result, "mark_gossip_message_processed should return true");

        // Verify processed_at is now set
        let processed_at_after: Option<String> =
            sqlx::query_scalar("SELECT processed_at::text FROM gossip_messages WHERE id = $1")
                .bind(message_id)
                .fetch_one(&pool)
                .await
                .unwrap();

        assert!(
            processed_at_after.is_some(),
            "processed_at should be set after marking"
        );
    }

    #[tokio::test]
    async fn test_fetch_unprocessed_gossip_messages() {
        let (_container, pool) = setup_postgres().await;

        let source_sovereign_id = Uuid::new_v4();
        let pkey = "-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAI...\n-----END PUBLIC KEY-----";
        sqlx::query("INSERT INTO sovereigns (id, name, public_key_pem) VALUES ($1, $2, $3)")
            .bind(source_sovereign_id)
            .bind("source")
            .bind(pkey)
            .execute(&pool)
            .await
            .unwrap();

        let payload = serde_json::json!({"test": "payload"});

        // Insert three messages
        for i in 1..=3 {
            let _ = insert_gossip_message_idempotent(
                &pool,
                source_sovereign_id,
                i,
                "revocation",
                &payload,
                &format!("sig-{}", i),
            )
            .await
            .unwrap();
        }

        // Fetch unprocessed messages
        let messages = fetch_unprocessed_gossip_messages(&pool, "revocation", 10)
            .await
            .unwrap();

        assert_eq!(messages.len(), 3, "Should fetch 3 unprocessed messages");

        // Verify order is by gossip_seq (FIFO)
        assert_eq!(messages[0].2, 1, "First message should have gossip_seq=1");
        assert_eq!(messages[1].2, 2, "Second message should have gossip_seq=2");
        assert_eq!(messages[2].2, 3, "Third message should have gossip_seq=3");

        // Mark first message as processed
        let _ = mark_gossip_message_processed(&pool, messages[0].0)
            .await
            .unwrap();

        // Fetch again
        let messages_after = fetch_unprocessed_gossip_messages(&pool, "revocation", 10)
            .await
            .unwrap();

        assert_eq!(
            messages_after.len(),
            2,
            "Should fetch 2 unprocessed messages after marking one"
        );
    }
}
