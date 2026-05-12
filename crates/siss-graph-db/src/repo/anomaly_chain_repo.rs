use chrono::{DateTime, Utc};
use serde_json::{Value, json};
use sqlx::PgPool;
use uuid::Uuid;

/// Represents a detected recurring sequence of two anomaly types for a sovereign.
#[derive(Debug, Clone)]
pub struct AnomalyChainRecord {
    pub sovereign_id: Uuid,
    pub chain_type: String, // "dispute_spam→timeout_spam"
    pub chain_length: i64,
    pub start_anomaly_type: String,
    pub end_anomaly_type: String,
    pub occurrence_count: i64,
    pub avg_elapsed_hours: f64,
    pub confidence: f64,
    pub last_seen_at: DateTime<Utc>,
    pub evidence: Value,
}

/// Ingest an anomaly chain into the graph as an AnomalyChainNode.
/// Idempotent: upsert on (sovereign_id, chain_type) composite key.
/// Returns the stable node UUID.
pub async fn ingest_anomaly_chain(
    pool: &PgPool,
    record: &AnomalyChainRecord,
) -> Result<Uuid, sqlx::Error> {
    let properties = json!({
        "sovereign_id": record.sovereign_id.to_string(),
        "chain_type": record.chain_type,
        "chain_length": record.chain_length,
        "start_anomaly_type": record.start_anomaly_type,
        "end_anomaly_type": record.end_anomaly_type,
        "occurrence_count": record.occurrence_count,
        "avg_elapsed_hours": record.avg_elapsed_hours,
        "confidence": record.confidence,
        "last_seen_at": record.last_seen_at.to_rfc3339(),
        "evidence": record.evidence,
    });

    let node_id: Uuid = sqlx::query_scalar(
        "INSERT INTO graph_entities (label, properties, graph_id)
         VALUES ('AnomalyChainNode', $1, 0)
         ON CONFLICT ((properties->>'sovereign_id'), (properties->>'chain_type'))
         WHERE label = 'AnomalyChainNode'
         DO UPDATE SET properties = EXCLUDED.properties, updated_at = NOW()
         RETURNING id",
    )
    .bind(properties)
    .fetch_one(pool)
    .await?;

    Ok(node_id)
}

#[cfg(test)]
mod tests {
    use super::*;
    use testcontainers::runners::AsyncRunner;
    use testcontainers::{GenericImage, ImageExt, core::WaitFor};

    async fn setup_test_db() -> (testcontainers::ContainerAsync<GenericImage>, PgPool) {
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
    async fn test_ingest_anomaly_chain_creates_node() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = Uuid::new_v4();

        let record = AnomalyChainRecord {
            sovereign_id,
            chain_type: "dispute_spam→timeout_spam".to_string(),
            chain_length: 2,
            start_anomaly_type: "dispute_spam".to_string(),
            end_anomaly_type: "timeout_spam".to_string(),
            occurrence_count: 1,
            avg_elapsed_hours: 1.5,
            confidence: 0.2,
            last_seen_at: Utc::now(),
            evidence: json!({
                "first_id": Uuid::new_v4().to_string(),
                "second_id": Uuid::new_v4().to_string(),
            }),
        };

        let node_id = ingest_anomaly_chain(&pool, &record)
            .await
            .expect("ingest chain");

        // Verify node was created
        let result: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities WHERE id = $1 AND label = 'AnomalyChainNode'",
        )
        .bind(node_id)
        .fetch_one(&pool)
        .await
        .expect("query");

        assert_eq!(result.0, 1, "AnomalyChainNode should be created");

        // Verify properties
        let props: (String,) =
            sqlx::query_as("SELECT properties->>'chain_type' FROM graph_entities WHERE id = $1")
                .bind(node_id)
                .fetch_one(&pool)
                .await
                .expect("query properties");

        assert_eq!(
            props.0, "dispute_spam→timeout_spam",
            "Chain type should be in properties"
        );
    }

    #[tokio::test]
    async fn test_ingest_anomaly_chain_upsert_increments_count() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = Uuid::new_v4();

        let record1 = AnomalyChainRecord {
            sovereign_id,
            chain_type: "dispute_spam→timeout_spam".to_string(),
            chain_length: 2,
            start_anomaly_type: "dispute_spam".to_string(),
            end_anomaly_type: "timeout_spam".to_string(),
            occurrence_count: 1,
            avg_elapsed_hours: 1.5,
            confidence: 0.2,
            last_seen_at: Utc::now(),
            evidence: json!({
                "first_id": Uuid::new_v4().to_string(),
                "second_id": Uuid::new_v4().to_string(),
            }),
        };

        let node_id_1 = ingest_anomaly_chain(&pool, &record1)
            .await
            .expect("ingest first chain");

        let record2 = AnomalyChainRecord {
            sovereign_id,
            chain_type: "dispute_spam→timeout_spam".to_string(),
            chain_length: 2,
            start_anomaly_type: "dispute_spam".to_string(),
            end_anomaly_type: "timeout_spam".to_string(),
            occurrence_count: 2,
            avg_elapsed_hours: 2.0,
            confidence: 0.4,
            last_seen_at: Utc::now(),
            evidence: json!({
                "first_id": Uuid::new_v4().to_string(),
                "second_id": Uuid::new_v4().to_string(),
            }),
        };

        let node_id_2 = ingest_anomaly_chain(&pool, &record2)
            .await
            .expect("ingest second chain");

        // Should be same UUID (idempotent)
        assert_eq!(node_id_1, node_id_2, "Same chain should return same UUID");

        // Verify no duplicate nodes
        let count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities WHERE label = 'AnomalyChainNode' AND properties->>'sovereign_id' = $1",
        )
        .bind(sovereign_id.to_string())
        .fetch_one(&pool)
        .await
        .expect("query count");

        assert_eq!(count.0, 1, "Should have exactly one AnomalyChainNode");

        // Verify occurrence_count was updated
        let occurrence: (i64,) = sqlx::query_as(
            "SELECT (properties->>'occurrence_count')::bigint FROM graph_entities WHERE id = $1",
        )
        .bind(node_id_1)
        .fetch_one(&pool)
        .await
        .expect("query occurrence");

        assert_eq!(occurrence.0, 2, "occurrence_count should be updated to 2");
    }
}
