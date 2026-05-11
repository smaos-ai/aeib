use chrono::{DateTime, Utc};
use sqlx::PgPool;
use uuid::Uuid;

/// Represents an anomaly event to be evaluated against predictions.
#[derive(Debug, Clone)]
pub struct AnomalyEvent {
    pub sovereign_id: Uuid,
    pub anomaly_type: String,
    pub detected_at: DateTime<Utc>,
}

/// Record feedback for an anomaly by matching it against active predictions.
/// Returns Some(feedback_node_id) if feedback was created, None if no matching prediction found.
pub async fn record_feedback_for_anomaly(
    pool: &PgPool,
    anomaly: &AnomalyEvent,
) -> Result<Option<Uuid>, sqlx::Error> {
    todo!()
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
    async fn test_record_feedback_exact_match() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = Uuid::new_v4();

        // Create a PredictionNode with last_computed_at = now
        let now = Utc::now();
        let prediction = crate::repo::prediction_repo::PredictionRecord {
            sovereign_id,
            predicted_anomaly_type: "timeout_spam".to_string(),
            prediction_horizon_hours: 4,
            risk_score: 0.65,
            signal_breakdown: serde_json::json!({"chain": 0.6}),
            evidence: serde_json::json!({"top_chain_type": "dispute_spam→timeout_spam"}),
            last_computed_at: now,
        };
        let _pred_id = crate::repo::prediction_repo::upsert_prediction(&pool, &prediction)
            .await
            .expect("upsert prediction");

        // Create anomaly within 4h window with matching type
        let anomaly = AnomalyEvent {
            sovereign_id,
            anomaly_type: "timeout_spam".to_string(),
            detected_at: now + chrono::Duration::hours(2),
        };

        let feedback_id = record_feedback_for_anomaly(&pool, &anomaly)
            .await
            .expect("record feedback");

        assert!(feedback_id.is_some(), "Should create feedback for exact match");

        // Verify FeedbackNode was created with matched=true
        let result: (bool,) = sqlx::query_as(
            "SELECT (properties->>'matched')::boolean FROM graph_entities WHERE id = $1 AND label = 'FeedbackNode'",
        )
        .bind(feedback_id.unwrap())
        .fetch_one(&pool)
        .await
        .expect("query feedback");

        assert_eq!(result.0, true, "matched should be true");
    }

    #[tokio::test]
    async fn test_record_feedback_no_match() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = Uuid::new_v4();

        let now = Utc::now();
        let prediction = crate::repo::prediction_repo::PredictionRecord {
            sovereign_id,
            predicted_anomaly_type: "timeout_spam".to_string(),
            prediction_horizon_hours: 4,
            risk_score: 0.65,
            signal_breakdown: serde_json::json!({"chain": 0.6}),
            evidence: serde_json::json!({"top_chain_type": "dispute_spam→timeout_spam"}),
            last_computed_at: now,
        };
        let _pred_id = crate::repo::prediction_repo::upsert_prediction(&pool, &prediction)
            .await
            .expect("upsert prediction");

        // Create anomaly with DIFFERENT type
        let anomaly = AnomalyEvent {
            sovereign_id,
            anomaly_type: "dispute_spam".to_string(),
            detected_at: now + chrono::Duration::hours(2),
        };

        let feedback_id = record_feedback_for_anomaly(&pool, &anomaly)
            .await
            .expect("record feedback");

        assert!(feedback_id.is_some(), "Should create feedback even with no match");

        let result: (bool,) = sqlx::query_as(
            "SELECT (properties->>'matched')::boolean FROM graph_entities WHERE id = $1 AND label = 'FeedbackNode'",
        )
        .bind(feedback_id.unwrap())
        .fetch_one(&pool)
        .await
        .expect("query feedback");

        assert_eq!(result.0, false, "matched should be false");
    }

    #[tokio::test]
    async fn test_record_feedback_outside_window() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = Uuid::new_v4();

        let now = Utc::now();
        let prediction = crate::repo::prediction_repo::PredictionRecord {
            sovereign_id,
            predicted_anomaly_type: "timeout_spam".to_string(),
            prediction_horizon_hours: 4,
            risk_score: 0.65,
            signal_breakdown: serde_json::json!({"chain": 0.6}),
            evidence: serde_json::json!({"top_chain_type": "dispute_spam→timeout_spam"}),
            last_computed_at: now,
        };
        let _pred_id = crate::repo::prediction_repo::upsert_prediction(&pool, &prediction)
            .await
            .expect("upsert prediction");

        // Create anomaly OUTSIDE 4h window (5 hours after prediction)
        let anomaly = AnomalyEvent {
            sovereign_id,
            anomaly_type: "timeout_spam".to_string(),
            detected_at: now + chrono::Duration::hours(5),
        };

        let feedback_id = record_feedback_for_anomaly(&pool, &anomaly)
            .await
            .expect("record feedback");

        assert!(feedback_id.is_some(), "Should create feedback");

        let result: (bool,) = sqlx::query_as(
            "SELECT (properties->>'matched')::boolean FROM graph_entities WHERE id = $1 AND label = 'FeedbackNode'",
        )
        .bind(feedback_id.unwrap())
        .fetch_one(&pool)
        .await
        .expect("query feedback");

        assert_eq!(result.0, false, "matched should be false for outside window");
    }

    #[tokio::test]
    async fn test_record_feedback_idempotent() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = Uuid::new_v4();

        let now = Utc::now();
        let prediction = crate::repo::prediction_repo::PredictionRecord {
            sovereign_id,
            predicted_anomaly_type: "timeout_spam".to_string(),
            prediction_horizon_hours: 4,
            risk_score: 0.65,
            signal_breakdown: serde_json::json!({"chain": 0.6}),
            evidence: serde_json::json!({"top_chain_type": "dispute_spam→timeout_spam"}),
            last_computed_at: now,
        };
        let _pred_id = crate::repo::prediction_repo::upsert_prediction(&pool, &prediction)
            .await
            .expect("upsert prediction");

        let anomaly = AnomalyEvent {
            sovereign_id,
            anomaly_type: "timeout_spam".to_string(),
            detected_at: now + chrono::Duration::hours(2),
        };

        // Record feedback twice
        let feedback_id_1 = record_feedback_for_anomaly(&pool, &anomaly)
            .await
            .expect("record feedback first");

        let feedback_id_2 = record_feedback_for_anomaly(&pool, &anomaly)
            .await
            .expect("record feedback second");

        // Should be the same UUID (idempotent)
        assert_eq!(feedback_id_1, feedback_id_2, "Should return same UUID on re-record");

        // Verify no duplicate FeedbackNodes were created
        let count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities WHERE label = 'FeedbackNode' AND properties->>'sovereign_id' = $1",
        )
        .bind(sovereign_id.to_string())
        .fetch_one(&pool)
        .await
        .expect("query count");

        assert_eq!(count.0, 1, "Should have exactly one FeedbackNode");
    }
}
