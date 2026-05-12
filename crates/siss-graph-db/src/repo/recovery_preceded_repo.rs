use chrono::{DateTime, Utc};
use serde_json::{Value, json};
use sqlx::PgPool;
use uuid::Uuid;

/// Represents a detected correlation between an anomaly type and recovery for a sovereign.
#[derive(Debug, Clone)]
pub struct RecoveryCorrelationRecord {
    pub sovereign_id: Uuid,
    pub anomaly_type: String,
    pub occurrence_count: i64,
    pub avg_gap_hours: f64,
    pub confidence: f64,
    pub last_seen_at: DateTime<Utc>,
    pub evidence: Value,
}

/// Ingest a recovery correlation into the graph as a RecoveryCorrelationNode.
/// Idempotent: upsert on (sovereign_id, anomaly_type) composite key.
/// Returns the stable node UUID.
pub async fn ingest_recovery_correlation(
    pool: &PgPool,
    record: &RecoveryCorrelationRecord,
) -> Result<Uuid, sqlx::Error> {
    let properties = json!({
        "sovereign_id": record.sovereign_id.to_string(),
        "anomaly_type": record.anomaly_type,
        "occurrence_count": record.occurrence_count,
        "avg_gap_hours": record.avg_gap_hours,
        "confidence": record.confidence,
        "last_seen_at": record.last_seen_at.to_rfc3339(),
        "evidence": record.evidence,
    });

    let node_id: Uuid = sqlx::query_scalar(
        "INSERT INTO graph_entities (label, properties, graph_id)
         VALUES ('RecoveryCorrelationNode', $1, 0)
         ON CONFLICT ((properties->>'sovereign_id'), (properties->>'anomaly_type'))
         WHERE label = 'RecoveryCorrelationNode'
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
    async fn test_ingest_recovery_correlation_creates_node() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = Uuid::new_v4();

        let record = RecoveryCorrelationRecord {
            sovereign_id,
            anomaly_type: "dispute_spam".to_string(),
            occurrence_count: 1,
            avg_gap_hours: 12.0,
            confidence: 0.2,
            last_seen_at: Utc::now(),
            evidence: json!({
                "anomaly_id": Uuid::new_v4().to_string(),
                "recovery_id": Uuid::new_v4().to_string(),
            }),
        };

        let node_id = ingest_recovery_correlation(&pool, &record)
            .await
            .expect("ingest correlation");

        // Verify node was created
        let result: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities WHERE id = $1 AND label = 'RecoveryCorrelationNode'",
        )
        .bind(node_id)
        .fetch_one(&pool)
        .await
        .expect("query");

        assert_eq!(result.0, 1, "RecoveryCorrelationNode should be created");

        // Verify properties
        let props: (String,) =
            sqlx::query_as("SELECT properties->>'anomaly_type' FROM graph_entities WHERE id = $1")
                .bind(node_id)
                .fetch_one(&pool)
                .await
                .expect("query properties");

        assert_eq!(
            props.0, "dispute_spam",
            "Anomaly type should be in properties"
        );
    }

    #[tokio::test]
    async fn test_ingest_recovery_correlation_upsert_increments_count() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = Uuid::new_v4();

        let record1 = RecoveryCorrelationRecord {
            sovereign_id,
            anomaly_type: "dispute_spam".to_string(),
            occurrence_count: 1,
            avg_gap_hours: 12.0,
            confidence: 0.2,
            last_seen_at: Utc::now(),
            evidence: json!({
                "anomaly_id": Uuid::new_v4().to_string(),
                "recovery_id": Uuid::new_v4().to_string(),
            }),
        };

        let node_id_1 = ingest_recovery_correlation(&pool, &record1)
            .await
            .expect("ingest first correlation");

        let record2 = RecoveryCorrelationRecord {
            sovereign_id,
            anomaly_type: "dispute_spam".to_string(),
            occurrence_count: 2,
            avg_gap_hours: 18.0,
            confidence: 0.4,
            last_seen_at: Utc::now(),
            evidence: json!({
                "anomaly_id": Uuid::new_v4().to_string(),
                "recovery_id": Uuid::new_v4().to_string(),
            }),
        };

        let node_id_2 = ingest_recovery_correlation(&pool, &record2)
            .await
            .expect("ingest second correlation");

        // Should be same UUID (idempotent)
        assert_eq!(
            node_id_1, node_id_2,
            "Same correlation should return same UUID"
        );

        // Verify no duplicate nodes
        let count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities WHERE label = 'RecoveryCorrelationNode' AND properties->>'sovereign_id' = $1",
        )
        .bind(sovereign_id.to_string())
        .fetch_one(&pool)
        .await
        .expect("query count");

        assert_eq!(
            count.0, 1,
            "Should have exactly one RecoveryCorrelationNode"
        );

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
