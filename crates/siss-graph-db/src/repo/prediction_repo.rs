use chrono::{DateTime, Utc};
use serde_json::{Value, json};
use sqlx::PgPool;
use uuid::Uuid;

/// Represents a prediction for a sovereign: the next likely anomaly type and overall risk score.
#[derive(Debug, Clone)]
pub struct PredictionRecord {
    pub sovereign_id: Uuid,
    pub predicted_anomaly_type: String,
    pub prediction_horizon_hours: i64,
    pub risk_score: f64,
    pub signal_breakdown: Value,
    pub evidence: Value,
    pub last_computed_at: DateTime<Utc>,
}

/// Ingest a prediction into the graph as a PredictionNode.
/// Idempotent: upsert on sovereign_id (one prediction per sovereign).
/// Returns the stable node UUID.
pub async fn upsert_prediction(
    pool: &PgPool,
    record: &PredictionRecord,
) -> Result<Uuid, sqlx::Error> {
    let properties = json!({
        "sovereign_id": record.sovereign_id.to_string(),
        "predicted_anomaly_type": record.predicted_anomaly_type,
        "prediction_horizon_hours": record.prediction_horizon_hours,
        "risk_score": record.risk_score,
        "signal_breakdown": record.signal_breakdown,
        "evidence": record.evidence,
        "last_computed_at": record.last_computed_at.to_rfc3339(),
    });

    let node_id: Uuid = sqlx::query_scalar(
        "INSERT INTO graph_entities (label, properties, graph_id)
         VALUES ('PredictionNode', $1, 0)
         ON CONFLICT ((properties->>'sovereign_id'))
         WHERE label = 'PredictionNode'
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
    async fn test_upsert_prediction_creates_node() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = Uuid::new_v4();

        let record = PredictionRecord {
            sovereign_id,
            predicted_anomaly_type: "timeout_spam".to_string(),
            prediction_horizon_hours: 4,
            risk_score: 0.65,
            signal_breakdown: json!({
                "chain": 0.6,
                "correlation": 0.4,
                "recovery": 0.0,
            }),
            evidence: json!({
                "top_chain_type": "dispute_spam→timeout_spam",
                "top_anomaly_type": "timeout_spam",
            }),
            last_computed_at: Utc::now(),
        };

        let node_id = upsert_prediction(&pool, &record)
            .await
            .expect("upsert prediction");

        // Verify node was created
        let result: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities WHERE id = $1 AND label = 'PredictionNode'",
        )
        .bind(node_id)
        .fetch_one(&pool)
        .await
        .expect("query");

        assert_eq!(result.0, 1, "PredictionNode should be created");

        // Verify properties
        let props: (String, f64) = sqlx::query_as(
            "SELECT properties->>'predicted_anomaly_type', (properties->>'risk_score')::float FROM graph_entities WHERE id = $1",
        )
        .bind(node_id)
        .fetch_one(&pool)
        .await
        .expect("query properties");

        assert_eq!(
            props.0, "timeout_spam",
            "predicted_anomaly_type should match"
        );
        assert_eq!(props.1, 0.65, "risk_score should match");
    }

    #[tokio::test]
    async fn test_upsert_prediction_updates_on_second_call() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = Uuid::new_v4();

        let record1 = PredictionRecord {
            sovereign_id,
            predicted_anomaly_type: "timeout_spam".to_string(),
            prediction_horizon_hours: 4,
            risk_score: 0.65,
            signal_breakdown: json!({
                "chain": 0.6,
                "correlation": 0.4,
                "recovery": 0.0,
            }),
            evidence: json!({
                "top_chain_type": "dispute_spam→timeout_spam",
                "top_anomaly_type": "timeout_spam",
            }),
            last_computed_at: Utc::now(),
        };

        let node_id_1 = upsert_prediction(&pool, &record1)
            .await
            .expect("upsert first prediction");

        let record2 = PredictionRecord {
            sovereign_id,
            predicted_anomaly_type: "timeout_spam".to_string(),
            prediction_horizon_hours: 4,
            risk_score: 0.75,
            signal_breakdown: json!({
                "chain": 0.7,
                "correlation": 0.4,
                "recovery": 0.0,
            }),
            evidence: json!({
                "top_chain_type": "dispute_spam→timeout_spam",
                "top_anomaly_type": "timeout_spam",
            }),
            last_computed_at: Utc::now(),
        };

        let node_id_2 = upsert_prediction(&pool, &record2)
            .await
            .expect("upsert second prediction");

        // Should be same UUID (idempotent)
        assert_eq!(
            node_id_1, node_id_2,
            "Same sovereign should return same UUID"
        );

        // Verify no duplicate nodes
        let count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities WHERE label = 'PredictionNode' AND properties->>'sovereign_id' = $1",
        )
        .bind(sovereign_id.to_string())
        .fetch_one(&pool)
        .await
        .expect("query count");

        assert_eq!(count.0, 1, "Should have exactly one PredictionNode");

        // Verify risk_score was updated
        let risk: (f64,) = sqlx::query_as(
            "SELECT (properties->>'risk_score')::float FROM graph_entities WHERE id = $1",
        )
        .bind(node_id_1)
        .fetch_one(&pool)
        .await
        .expect("query risk");

        assert_eq!(risk.0, 0.75, "risk_score should be updated to 0.75");
    }
}
