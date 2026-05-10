/// Phase 11: Peer Discovery Protocol
/// Opt-in discovery and peer announcements

use sqlx::PgPool;
use uuid::Uuid;
use serde_json::{json, Value};
use std::collections::BTreeMap;

pub const DISCOVERY_OPT_IN_REQUIRED: &str = "sovereign_must_set_is_discoverable_true";

#[derive(Debug, Clone)]
pub enum DiscoveryError {
    NoEndpointUrl,
    InvalidSignature,
    Database(String),
}

impl From<sqlx::Error> for DiscoveryError {
    fn from(err: sqlx::Error) -> Self {
        DiscoveryError::Database(err.to_string())
    }
}

/// Set a sovereign as discoverable (requires endpoint_url).
pub async fn set_sovereign_discoverable(
    pool: &PgPool,
    sovereign_id: Uuid,
    is_discoverable: bool,
    discovery_metadata: Option<Value>,
) -> Result<bool, DiscoveryError> {
    if is_discoverable {
        // Check endpoint_url exists
        let has_endpoint: bool = sqlx::query_scalar(
            "SELECT EXISTS(SELECT 1 FROM sovereigns WHERE id = $1 AND endpoint_url IS NOT NULL)"
        )
        .bind(sovereign_id)
        .fetch_one(pool)
        .await?;

        if !has_endpoint {
            return Err(DiscoveryError::NoEndpointUrl);
        }
    }

    let affected = sqlx::query_scalar::<_, i64>(
        "UPDATE sovereigns SET is_discoverable = $1, discovery_metadata = $2 WHERE id = $3 \
         RETURNING 1"
    )
    .bind(is_discoverable)
    .bind(discovery_metadata)
    .bind(sovereign_id)
    .fetch_optional(pool)
    .await?
    .unwrap_or(0);

    Ok(affected > 0)
}

/// List all discoverable sovereigns (DISCOVERY_OPT_IN_REQUIRED enforced).
pub async fn list_discoverable_sovereigns(
    pool: &PgPool,
) -> Result<Vec<(Uuid, String, Option<Value>)>, sqlx::Error> {
    sqlx::query_as::<_, (Uuid, String, Option<Value>)>(
        "SELECT id, endpoint_url, discovery_metadata \
         FROM sovereigns \
         WHERE is_discoverable = TRUE AND endpoint_url IS NOT NULL \
         ORDER BY id"
    )
    .fetch_all(pool)
    .await
}

/// Insert or update a discovered sovereign (inserts with is_discoverable=false).
pub async fn upsert_discovered_sovereign(
    pool: &PgPool,
    sovereign_id: Uuid,
    sovereign_name: &str,
    public_key_pem: &str,
    endpoint_url: &str,
    _announcement_signature: &str,
) -> Result<bool, sqlx::Error> {
    let existing: Option<Uuid> = sqlx::query_scalar(
        "SELECT id FROM sovereigns WHERE id = $1"
    )
    .bind(sovereign_id)
    .fetch_optional(pool)
    .await?;

    if existing.is_some() {
        // Already known
        return Ok(false);
    }

    sqlx::query(
        "INSERT INTO sovereigns (id, name, endpoint_url, public_key_pem, is_discoverable) \
         VALUES ($1, $2, $3, $4, false)"
    )
    .bind(sovereign_id)
    .bind(sovereign_name)
    .bind(endpoint_url)
    .bind(public_key_pem)
    .execute(pool)
    .await?;

    Ok(true)
}

/// Record a peer announcement (idempotent via UNIQUE constraint).
pub async fn record_peer_announcement(
    pool: &PgPool,
    announcing_sovereign_id: Uuid,
    announced_to_sovereign_id: Uuid,
    announced_sovereign_id: Uuid,
    gossip_message_id: Option<Uuid>,
) -> Result<bool, sqlx::Error> {
    let id = Uuid::new_v4();
    match sqlx::query(
        "INSERT INTO peer_announcements \
         (id, announcing_sovereign_id, announced_to_sovereign_id, announced_sovereign_id, gossip_message_id) \
         VALUES ($1, $2, $3, $4, $5)"
    )
    .bind(id)
    .bind(announcing_sovereign_id)
    .bind(announced_to_sovereign_id)
    .bind(announced_sovereign_id)
    .bind(gossip_message_id)
    .execute(pool)
    .await
    {
        Ok(_) => Ok(true),
        Err(sqlx::Error::Database(db_err)) if db_err.message().contains("duplicate") => Ok(false),
        Err(e) => Err(e),
    }
}

/// Build canonical peer announcement payload (BTreeMap alphabetical order).
pub fn build_canonical_peer_announcement_payload(
    announcing_sovereign_id: &str,
    announced_sovereign_id: &str,
    announced_endpoint_url: &str,
    announced_public_key_pem: &str,
    announced_at: &str,
) -> String {
    let mut map = BTreeMap::new();
    map.insert("announced_at", json!(announced_at));
    map.insert("announced_endpoint_url", json!(announced_endpoint_url));
    map.insert("announced_public_key_pem", json!(announced_public_key_pem));
    map.insert("announced_sovereign_id", json!(announced_sovereign_id));
    map.insert("announcing_sovereign_id", json!(announcing_sovereign_id));

    serde_json::to_string(&map).unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use super::*;
    use testcontainers::runners::AsyncRunner;
    use testcontainers::{core::WaitFor, GenericImage, ImageExt};

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
    async fn test_set_discoverable_requires_endpoint_url() {
        let (_container, pool) = setup_postgres().await;

        // Create sovereign without endpoint
        let sovereign_id = Uuid::new_v4();
        sqlx::query(
            "INSERT INTO sovereigns (id, name, public_key_pem) VALUES ($1, $2, $3)"
        )
        .bind(sovereign_id)
        .bind("no_endpoint_sovereign")
        .bind("-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBALqxBjq9i\n-----END PUBLIC KEY-----")
        .execute(&pool)
        .await
        .expect("insert");

        let result = set_sovereign_discoverable(&pool, sovereign_id, true, None).await;
        assert!(matches!(result, Err(DiscoveryError::NoEndpointUrl)));
    }

    #[tokio::test]
    async fn test_set_discoverable_succeeds_with_endpoint() {
        let (_container, pool) = setup_postgres().await;

        let sovereign_id = Uuid::new_v4();
        sqlx::query(
            "INSERT INTO sovereigns (id, name, endpoint_url, public_key_pem) VALUES ($1, $2, $3, $4)"
        )
        .bind(sovereign_id)
        .bind("discoverable_sovereign")
        .bind("http://localhost:8001")
        .bind("-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBALqxBjq9i\n-----END PUBLIC KEY-----")
        .execute(&pool)
        .await
        .expect("insert");

        let metadata = json!({"region": "us-east-1"});
        let result = set_sovereign_discoverable(&pool, sovereign_id, true, Some(metadata))
            .await
            .expect("set discoverable");

        assert!(result);

        // Verify
        let (id, discoverable, meta): (Uuid, bool, Option<Value>) = sqlx::query_as(
            "SELECT id, is_discoverable, discovery_metadata FROM sovereigns WHERE id = $1"
        )
        .bind(sovereign_id)
        .fetch_one(&pool)
        .await
        .expect("fetch");

        assert_eq!(id, sovereign_id);
        assert!(discoverable);
        assert!(meta.is_some());
    }

    #[tokio::test]
    async fn test_list_discoverable_filters_opt_in() {
        let (_container, pool) = setup_postgres().await;

        let s1 = Uuid::new_v4();
        let s2 = Uuid::new_v4();

        // Create two sovereigns
        sqlx::query(
            "INSERT INTO sovereigns (id, name, endpoint_url, public_key_pem, is_discoverable) VALUES ($1, $2, $3, $4, true)"
        )
        .bind(s1)
        .bind("discoverable")
        .bind("http://localhost:8001")
        .bind("-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBALqxBjq9i\n-----END PUBLIC KEY-----")
        .execute(&pool)
        .await
        .expect("insert s1");

        sqlx::query(
            "INSERT INTO sovereigns (id, name, endpoint_url, public_key_pem, is_discoverable) VALUES ($1, $2, $3, $4, false)"
        )
        .bind(s2)
        .bind("not_discoverable")
        .bind("http://localhost:8002")
        .bind("-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBALqxBjq9i\n-----END PUBLIC KEY-----")
        .execute(&pool)
        .await
        .expect("insert s2");

        let list = list_discoverable_sovereigns(&pool).await.expect("list");
        assert_eq!(list.len(), 1, "should only return discoverable sovereign");
        assert_eq!(list[0].0, s1);
    }

    #[tokio::test]
    async fn test_upsert_discovered_sovereign_new() {
        let (_container, pool) = setup_postgres().await;

        let new_sovereign_id = Uuid::new_v4();
        let result = upsert_discovered_sovereign(
            &pool,
            new_sovereign_id,
            "new_discovered_sovereign",
            "-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBALqxBjq9i\n-----END PUBLIC KEY-----",
            "http://localhost:9001",
            "sig_hex",
        )
        .await
        .expect("upsert");

        assert!(result, "inserting new sovereign should return true");

        // Verify is_discoverable is false
        let is_disc: bool = sqlx::query_scalar(
            "SELECT is_discoverable FROM sovereigns WHERE id = $1"
        )
        .bind(new_sovereign_id)
        .fetch_one(&pool)
        .await
        .expect("fetch");

        assert!(!is_disc, "newly discovered sovereign should NOT be discoverable by default");
    }

    #[tokio::test]
    async fn test_upsert_discovered_sovereign_existing() {
        let (_container, pool) = setup_postgres().await;

        let sovereign_id = Uuid::new_v4();
        sqlx::query(
            "INSERT INTO sovereigns (id, name, endpoint_url, public_key_pem) VALUES ($1, $2, $3, $4)"
        )
        .bind(sovereign_id)
        .bind("existing")
        .bind("http://localhost:8001")
        .bind("-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBALqxBjq9i\n-----END PUBLIC KEY-----")
        .execute(&pool)
        .await
        .expect("insert");

        let result = upsert_discovered_sovereign(
            &pool,
            sovereign_id,
            "existing",
            "-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBALqxBjq9i\n-----END PUBLIC KEY-----",
            "http://localhost:8001",
            "sig_hex",
        )
        .await
        .expect("upsert");

        assert!(!result, "upserting existing sovereign should return false");
    }

    #[tokio::test]
    async fn test_record_peer_announcement_idempotent() {
        let (_container, pool) = setup_postgres().await;

        let announcing = Uuid::new_v4();
        let announced_to = Uuid::new_v4();
        let announced = Uuid::new_v4();

        // Create all sovereigns
        for (id, name) in [(announcing, "announcing"), (announced_to, "announced_to"), (announced, "announced")] {
            sqlx::query(
                "INSERT INTO sovereigns (id, name, endpoint_url, public_key_pem) VALUES ($1, $2, $3, $4)"
            )
            .bind(id)
            .bind(name)
            .bind("http://localhost:8001")
            .bind("-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBALqxBjq9i\n-----END PUBLIC KEY-----")
            .execute(&pool)
            .await
            .expect("insert");
        }

        // First announcement should succeed
        let result1 = record_peer_announcement(&pool, announcing, announced_to, announced, None)
            .await
            .expect("first record");
        assert!(result1, "first announcement should succeed");

        // Duplicate should return false (idempotent)
        let result2 = record_peer_announcement(&pool, announcing, announced_to, announced, None)
            .await
            .expect("second record");
        assert!(!result2, "duplicate announcement should return false");
    }
}
