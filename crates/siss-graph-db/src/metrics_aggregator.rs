use chrono::{DateTime, Duration, Utc};
use sqlx::PgPool;
use std::sync::Arc;
use tokio::task::JoinHandle;
use uuid::Uuid;

pub const DEFAULT_AGGREGATION_INTERVAL: Duration = Duration::hours(1);

/// Aggregate metrics once: compute precision/recall for all active (sovereign, anomaly_type) pairs.
pub async fn aggregate_metrics_once(pool: &PgPool) -> Result<usize, sqlx::Error> {
    // Query all unique (sovereign_id, anomaly_type) pairs from recent FeedbackNodes
    let pairs: Vec<(String, String)> = sqlx::query_as(
        "SELECT DISTINCT properties->>'sovereign_id', properties->>'predicted_anomaly_type'
         FROM graph_entities
         WHERE label = 'FeedbackNode'",
    )
    .fetch_all(pool)
    .await?;

    let mut count = 0;

    for (sovereign_id_str, anomaly_type) in pairs {
        // Count TP: matched=true
        let tp_count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities
             WHERE label = 'FeedbackNode'
             AND properties->>'sovereign_id' = $1
             AND properties->>'predicted_anomaly_type' = $2
             AND (properties->>'matched')::boolean = true",
        )
        .bind(&sovereign_id_str)
        .bind(&anomaly_type)
        .fetch_one(pool)
        .await?;

        // Count FP: matched=false
        let fp_count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities
             WHERE label = 'FeedbackNode'
             AND properties->>'sovereign_id' = $1
             AND properties->>'predicted_anomaly_type' = $2
             AND (properties->>'matched')::boolean = false",
        )
        .bind(&sovereign_id_str)
        .bind(&anomaly_type)
        .fetch_one(pool)
        .await?;

        let tp = tp_count.0;
        let fp = fp_count.0;

        // Count FN: anomalies with no matching feedback
        let fn_count: (i64,) = sqlx::query_as(
            "SELECT COUNT(DISTINCT ae.id) FROM graph_entities ae
             WHERE ae.label = 'AnomalyEventNode'
             AND ae.properties->>'sovereign_id' = $1
             AND ae.properties->>'anomaly_type' = $2",
        )
        .bind(&sovereign_id_str)
        .bind(&anomaly_type)
        .fetch_one(pool)
        .await?;

        let fn_count = fn_count.0;

        // Compute precision and recall
        let precision = if tp + fp > 0 {
            Some(tp as f64 / (tp + fp) as f64)
        } else {
            None
        };

        let recall = if tp + fn_count > 0 {
            Some(tp as f64 / (tp + fn_count) as f64)
        } else {
            None
        };

        // Compute average risk scores
        let avg_risk_correct: (Option<f64>,) = sqlx::query_as(
            "SELECT AVG((properties->>'prediction_risk_score')::float) FROM graph_entities
             WHERE label = 'FeedbackNode'
             AND properties->>'sovereign_id' = $1
             AND properties->>'predicted_anomaly_type' = $2
             AND (properties->>'matched')::boolean = true",
        )
        .bind(&sovereign_id_str)
        .bind(&anomaly_type)
        .fetch_one(pool)
        .await?;

        let avg_risk_incorrect: (Option<f64>,) = sqlx::query_as(
            "SELECT AVG((properties->>'prediction_risk_score')::float) FROM graph_entities
             WHERE label = 'FeedbackNode'
             AND properties->>'sovereign_id' = $1
             AND properties->>'predicted_anomaly_type' = $2
             AND (properties->>'matched')::boolean = false",
        )
        .bind(&sovereign_id_str)
        .bind(&anomaly_type)
        .fetch_one(pool)
        .await?;

        // Create/update AccuracyMetricsNode
        let properties = serde_json::json!({
            "sovereign_id": sovereign_id_str,
            "anomaly_type": anomaly_type,
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn_count,
            "precision": precision,
            "recall": recall,
            "avg_risk_score_correct": avg_risk_correct.0,
            "avg_risk_score_incorrect": avg_risk_incorrect.0,
            "sample_count": tp + fp,
            "last_updated_at": Utc::now().to_rfc3339(),
        });

        sqlx::query(
            "INSERT INTO graph_entities (label, properties, graph_id) VALUES ('AccuracyMetricsNode', $1, 0)
             ON CONFLICT ((properties->>'sovereign_id'), (properties->>'anomaly_type'))
             WHERE label = 'AccuracyMetricsNode'
             DO UPDATE SET properties = EXCLUDED.properties, updated_at = NOW()",
        )
        .bind(properties)
        .execute(pool)
        .await?;

        count += 1;
    }

    Ok(count)
}

/// Start background ticker for periodic metric aggregation.
pub fn start_metrics_aggregator(pool: Arc<PgPool>, interval: Duration) -> JoinHandle<()> {
    tokio::spawn(async move {
        let mut interval = tokio::time::interval(std::time::Duration::from_millis(interval.num_milliseconds() as u64));
        loop {
            interval.tick().await;
            let _ = aggregate_metrics_once(&pool).await;
        }
    })
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
    async fn test_metrics_precision_calculation() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = Uuid::new_v4();

        // Create 2 FeedbackNodes: 1 matched (TP), 1 unmatched (FP)
        let props_tp = serde_json::json!({
            "prediction_node_id": Uuid::new_v4().to_string(),
            "sovereign_id": sovereign_id.to_string(),
            "predicted_anomaly_type": "timeout_spam",
            "matched": true,
            "anomaly_detected_at": Utc::now().to_rfc3339(),
            "prediction_risk_score": 0.6,
            "created_at": Utc::now().to_rfc3339(),
        });

        let props_fp = serde_json::json!({
            "prediction_node_id": Uuid::new_v4().to_string(),
            "sovereign_id": sovereign_id.to_string(),
            "predicted_anomaly_type": "timeout_spam",
            "matched": false,
            "anomaly_detected_at": serde_json::json!(null),
            "prediction_risk_score": 0.3,
            "created_at": Utc::now().to_rfc3339(),
        });

        sqlx::query("INSERT INTO graph_entities (label, properties, graph_id) VALUES ('FeedbackNode', $1, 0)")
            .bind(&props_tp)
            .execute(&pool)
            .await
            .expect("insert TP feedback");

        sqlx::query("INSERT INTO graph_entities (label, properties, graph_id) VALUES ('FeedbackNode', $1, 0)")
            .bind(&props_fp)
            .execute(&pool)
            .await
            .expect("insert FP feedback");

        // Run aggregation
        let count = aggregate_metrics_once(&pool).await.expect("aggregate");
        assert!(count > 0, "Should update at least one metrics node");

        // Verify AccuracyMetricsNode was created with correct precision
        let result: (f64, i64, i64) = sqlx::query_as(
            "SELECT (properties->>'precision')::float, (properties->>'true_positives')::bigint, (properties->>'false_positives')::bigint
             FROM graph_entities
             WHERE label = 'AccuracyMetricsNode'
             AND properties->>'sovereign_id' = $1
             AND properties->>'anomaly_type' = 'timeout_spam'",
        )
        .bind(sovereign_id.to_string())
        .fetch_one(&pool)
        .await
        .expect("query metrics");

        // precision = TP / (TP + FP) = 1 / 2 = 0.5
        assert_eq!(result.0, 0.5, "precision should be 0.5");
        assert_eq!(result.1, 1, "true_positives should be 1");
        assert_eq!(result.2, 1, "false_positives should be 1");
    }

    #[tokio::test]
    async fn test_metrics_recall_calculation() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = Uuid::new_v4();

        // Create feedback: 1 TP
        let props = serde_json::json!({
            "prediction_node_id": Uuid::new_v4().to_string(),
            "sovereign_id": sovereign_id.to_string(),
            "predicted_anomaly_type": "timeout_spam",
            "matched": true,
            "anomaly_detected_at": Utc::now().to_rfc3339(),
            "prediction_risk_score": 0.6,
            "created_at": Utc::now().to_rfc3339(),
        });

        sqlx::query("INSERT INTO graph_entities (label, properties, graph_id) VALUES ('FeedbackNode', $1, 0)")
            .bind(&props)
            .execute(&pool)
            .await
            .expect("insert feedback");

        // Create AnomalyEventNode (1 FN: anomaly with no matching feedback)
        let anomaly_props = serde_json::json!({
            "sovereign_id": sovereign_id.to_string(),
            "anomaly_type": "timeout_spam",
            "detected_at": (Utc::now() - Duration::hours(1)).to_rfc3339(),
        });

        sqlx::query("INSERT INTO graph_entities (label, properties, graph_id) VALUES ('AnomalyEventNode', $1, 0)")
            .bind(&anomaly_props)
            .execute(&pool)
            .await
            .expect("insert anomaly");

        let count = aggregate_metrics_once(&pool).await.expect("aggregate");
        assert!(count > 0, "Should update metrics");

        // Verify recall
        let result: (f64, i64) = sqlx::query_as(
            "SELECT (properties->>'recall')::float, (properties->>'false_negatives')::bigint
             FROM graph_entities
             WHERE label = 'AccuracyMetricsNode'
             AND properties->>'sovereign_id' = $1",
        )
        .bind(sovereign_id.to_string())
        .fetch_one(&pool)
        .await
        .expect("query metrics");

        // recall = TP / (TP + FN) = 1 / 2 = 0.5
        assert_eq!(result.0, 0.5, "recall should be 0.5");
        assert_eq!(result.1, 1, "false_negatives should be 1");
    }

    #[tokio::test]
    async fn test_metrics_risk_score_weighting() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = Uuid::new_v4();

        // Create matched feedback with risk_score 0.8
        let props_correct = serde_json::json!({
            "prediction_node_id": Uuid::new_v4().to_string(),
            "sovereign_id": sovereign_id.to_string(),
            "predicted_anomaly_type": "timeout_spam",
            "matched": true,
            "anomaly_detected_at": Utc::now().to_rfc3339(),
            "prediction_risk_score": 0.8,
            "created_at": Utc::now().to_rfc3339(),
        });

        // Create unmatched feedback with risk_score 0.2
        let props_incorrect = serde_json::json!({
            "prediction_node_id": Uuid::new_v4().to_string(),
            "sovereign_id": sovereign_id.to_string(),
            "predicted_anomaly_type": "timeout_spam",
            "matched": false,
            "anomaly_detected_at": serde_json::json!(null),
            "prediction_risk_score": 0.2,
            "created_at": Utc::now().to_rfc3339(),
        });

        sqlx::query("INSERT INTO graph_entities (label, properties, graph_id) VALUES ('FeedbackNode', $1, 0)")
            .bind(&props_correct)
            .execute(&pool)
            .await
            .expect("insert correct feedback");

        sqlx::query("INSERT INTO graph_entities (label, properties, graph_id) VALUES ('FeedbackNode', $1, 0)")
            .bind(&props_incorrect)
            .execute(&pool)
            .await
            .expect("insert incorrect feedback");

        aggregate_metrics_once(&pool).await.expect("aggregate");

        let result: (f64, f64) = sqlx::query_as(
            "SELECT (properties->>'avg_risk_score_correct')::float, (properties->>'avg_risk_score_incorrect')::float
             FROM graph_entities
             WHERE label = 'AccuracyMetricsNode'
             AND properties->>'sovereign_id' = $1",
        )
        .bind(sovereign_id.to_string())
        .fetch_one(&pool)
        .await
        .expect("query metrics");

        assert_eq!(result.0, 0.8, "avg_risk_score_correct should be 0.8");
        assert_eq!(result.1, 0.2, "avg_risk_score_incorrect should be 0.2");
    }

    #[tokio::test]
    async fn test_aggregation_periodic() {
        let (_container, pool) = setup_test_db().await;
        let pool = Arc::new(pool);

        // Start the background aggregator with a very short interval (100ms)
        let aggregator = start_metrics_aggregator(pool.clone(), Duration::milliseconds(100));

        // Give it a moment to run
        tokio::time::sleep(tokio::time::Duration::from_millis(150)).await;

        // Verify it's running (no panics)
        assert!(!aggregator.is_finished(), "Aggregator should still be running");

        // Clean up
        drop(aggregator);
    }
}
