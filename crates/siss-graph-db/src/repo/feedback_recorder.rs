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
    // Query active PredictionNodes for this sovereign (last_computed_at > 24h ago)
    let cutoff = Utc::now() - chrono::Duration::hours(24);
    let predictions: Vec<(Uuid, String, f64, DateTime<Utc>)> = sqlx::query_as(
        "SELECT id, properties->>'predicted_anomaly_type', (properties->>'risk_score')::float, (properties->>'last_computed_at')::timestamptz
         FROM graph_entities
         WHERE label = 'PredictionNode'
         AND properties->>'sovereign_id' = $1
         AND (properties->>'last_computed_at')::timestamptz > $2
         ORDER BY (properties->>'last_computed_at')::timestamptz DESC",
    )
    .bind(anomaly.sovereign_id.to_string())
    .bind(cutoff)
    .fetch_all(pool)
    .await?;

    // Try to find exact match
    let mut matched = false;
    let mut matched_prediction_id = None;
    let mut risk_score = 0.0;

    for (pred_id, predicted_type, score, last_computed_at) in &predictions {
        // Check if anomaly type matches
        if anomaly.anomaly_type == *predicted_type {
            // Check if detected_at falls within [last_computed_at, last_computed_at + 4h]
            let window_end = *last_computed_at + chrono::Duration::hours(4);
            if anomaly.detected_at >= *last_computed_at && anomaly.detected_at <= window_end {
                matched = true;
                matched_prediction_id = Some(*pred_id);
                risk_score = *score;
                break;
            }
        }
    }

    // If no matching prediction found, use first prediction (or none)
    if matched_prediction_id.is_none() && !predictions.is_empty() {
        matched_prediction_id = Some(predictions[0].0);
        risk_score = predictions[0].2;
    }

    // Create FeedbackNode if we have a prediction to evaluate
    if let Some(pred_id) = matched_prediction_id {
        let properties = serde_json::json!({
            "prediction_node_id": pred_id.to_string(),
            "sovereign_id": anomaly.sovereign_id.to_string(),
            "predicted_anomaly_type": anomaly.anomaly_type,
            "matched": matched,
            "anomaly_detected_at": if matched { Some(anomaly.detected_at.to_rfc3339()) } else { None },
            "prediction_risk_score": risk_score,
            "created_at": Utc::now().to_rfc3339(),
        });

        let feedback_id: Uuid = sqlx::query_scalar(
            "INSERT INTO graph_entities (label, properties, graph_id)
             VALUES ('FeedbackNode', $1, 0)
             ON CONFLICT ((properties->>'prediction_node_id'))
             WHERE label = 'FeedbackNode'
             DO UPDATE SET properties = EXCLUDED.properties, updated_at = NOW()
             WHERE EXCLUDED.label = 'FeedbackNode'
             RETURNING id",
        )
        .bind(properties)
        .fetch_one(pool)
        .await?;

        // Create FEEDBACK_FOR edge
        let _edge = sqlx::query(
            "INSERT INTO graph_relationships (source_entity_id, target_entity_id, relationship_type)
             VALUES ($1, $2, 'FEEDBACK_FOR')
             ON CONFLICT (source_entity_id, target_entity_id, relationship_type) DO NOTHING",
        )
        .bind(feedback_id)
        .bind(pred_id)
        .execute(pool)
        .await?;

        // If feedback matched (true positive), reinforce the signals and reset acceleration
        // Otherwise accelerate decay on false positives
        if matched {
            let _ = crate::signal_reinforcement::reinforce_signals_for_feedback(pool, feedback_id)
                .await?;
            let _ = crate::signal_acceleration::reset_acceleration_mode(pool, feedback_id).await?;
        } else {
            let _ = crate::signal_acceleration::accelerate_signal_decay_for_false_positive(
                pool,
                feedback_id,
            )
            .await?;
        }

        Ok(Some(feedback_id))
    } else {
        Ok(None)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use sqlx::Row;
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

        assert!(
            feedback_id.is_some(),
            "Should create feedback for exact match"
        );

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

        assert!(
            feedback_id.is_some(),
            "Should create feedback even with no match"
        );

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

        assert_eq!(
            result.0, false,
            "matched should be false for outside window"
        );
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
        assert_eq!(
            feedback_id_1, feedback_id_2,
            "Should return same UUID on re-record"
        );

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

    #[tokio::test]
    async fn test_record_feedback_stale_prediction_not_matched() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = Uuid::new_v4();

        // Create a prediction from 25 hours ago (stale)
        let now = Utc::now();
        let stale_time = now - chrono::Duration::hours(25);

        let prediction = crate::repo::prediction_repo::PredictionRecord {
            sovereign_id,
            predicted_anomaly_type: "timeout_spam".to_string(),
            prediction_horizon_hours: 4,
            risk_score: 0.65,
            signal_breakdown: serde_json::json!({"chain": 0.6}),
            evidence: serde_json::json!({"top_chain_type": "dispute_spam→timeout_spam"}),
            last_computed_at: stale_time,
        };
        let _pred_id = crate::repo::prediction_repo::upsert_prediction(&pool, &prediction)
            .await
            .expect("upsert prediction");

        // Create anomaly that matches type and falls within original 4h window
        let anomaly = AnomalyEvent {
            sovereign_id,
            anomaly_type: "timeout_spam".to_string(),
            detected_at: stale_time + chrono::Duration::hours(2),
        };

        // Should return None because prediction is stale (>24h old)
        let feedback_id = record_feedback_for_anomaly(&pool, &anomaly)
            .await
            .expect("record feedback");

        assert!(
            feedback_id.is_none(),
            "Stale predictions (>24h) should not match"
        );
    }

    #[tokio::test]
    async fn test_record_feedback_creates_edge() {
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
        let pred_id = crate::repo::prediction_repo::upsert_prediction(&pool, &prediction)
            .await
            .expect("upsert prediction");

        let anomaly = AnomalyEvent {
            sovereign_id,
            anomaly_type: "timeout_spam".to_string(),
            detected_at: now + chrono::Duration::hours(2),
        };

        let feedback_id = record_feedback_for_anomaly(&pool, &anomaly)
            .await
            .expect("record feedback");

        assert!(feedback_id.is_some(), "Should create feedback");

        // Verify FEEDBACK_FOR edge exists
        let edge_count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_relationships
             WHERE source_entity_id = $1 AND target_entity_id = $2 AND relationship_type = 'FEEDBACK_FOR'",
        )
        .bind(feedback_id.unwrap())
        .bind(pred_id)
        .fetch_one(&pool)
        .await
        .expect("query edges");

        assert_eq!(edge_count.0, 1, "FEEDBACK_FOR edge should exist");
    }

    #[tokio::test]
    async fn test_record_feedback_triggers_reinforcement_on_match() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = Uuid::new_v4();

        // Create signal with confidence 0.5
        let signal_id = Uuid::new_v4();
        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(signal_id)
            .bind("AnomalyChainNode")
            .bind(serde_json::json!({
                "sovereign_id": sovereign_id.to_string(),
                "chain_type": "dispute_spam→timeout_spam",
                "confidence": 0.5,
                "last_seen_at": chrono::Utc::now().to_rfc3339(),
            }))
            .execute(&pool)
            .await
            .expect("Failed to insert signal");

        // Create prediction
        let now = Utc::now();
        let prediction = crate::repo::prediction_repo::PredictionRecord {
            sovereign_id,
            predicted_anomaly_type: "timeout_spam".to_string(),
            prediction_horizon_hours: 4,
            risk_score: 0.25,
            signal_breakdown: serde_json::json!({
                "chain": 0.5,
                "correlation": 0.0,
                "recovery": 0.0,
                "raw_risk_score": 0.25,
                "accuracy_weight": 1.0,
                "adjusted_risk_score": 0.25,
                "accuracy_sample_count": serde_json::Value::Null,
                "evidence": [
                    {
                        "signal_type": "AnomalyChainNode",
                        "signal_id": signal_id.to_string(),
                        "confidence": 0.5
                    }
                ]
            }),
            evidence: serde_json::json!({"top_chain_type": "dispute_spam→timeout_spam"}),
            last_computed_at: now,
        };
        let _pred_id = crate::repo::prediction_repo::upsert_prediction(&pool, &prediction)
            .await
            .expect("upsert prediction");

        // Record anomaly (should match and trigger reinforcement)
        let anomaly = AnomalyEvent {
            sovereign_id,
            anomaly_type: "timeout_spam".to_string(),
            detected_at: now + chrono::Duration::hours(2),
        };

        let feedback_id = record_feedback_for_anomaly(&pool, &anomaly)
            .await
            .expect("record_feedback failed")
            .expect("Should create feedback");

        // Verify feedback was created with matched=true
        let feedback = sqlx::query("SELECT properties FROM graph_entities WHERE id = $1")
            .bind(feedback_id)
            .fetch_one(&pool)
            .await
            .expect("Feedback not found");

        let feedback_props = feedback.get::<serde_json::Value, _>(0);
        let matched = feedback_props["matched"].as_bool().unwrap();
        assert!(matched, "Feedback should be matched=true");

        // Verify signal confidence was boosted (0.5 + 0.025 = 0.525)
        let signal = sqlx::query("SELECT properties FROM graph_entities WHERE id = $1")
            .bind(signal_id)
            .fetch_one(&pool)
            .await
            .expect("Signal not found");

        let signal_props = signal.get::<serde_json::Value, _>(0);
        let confidence: f64 = signal_props["confidence"].as_f64().unwrap();
        assert!(
            (confidence - 0.525).abs() < 0.001,
            "Signal should be boosted to 0.525, got {}",
            confidence
        );
    }

    #[tokio::test]
    async fn test_record_feedback_no_reinforcement_on_no_match() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = Uuid::new_v4();

        // Create signal with confidence 0.6
        let signal_id = Uuid::new_v4();
        let old_confidence = 0.6;
        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(signal_id)
            .bind("AnomalyChainNode")
            .bind(serde_json::json!({
                "sovereign_id": sovereign_id.to_string(),
                "chain_type": "dispute_spam→timeout_spam",
                "confidence": old_confidence,
                "last_seen_at": chrono::Utc::now().to_rfc3339(),
            }))
            .execute(&pool)
            .await
            .expect("Failed to insert signal");

        // Create prediction
        let now = Utc::now();
        let prediction = crate::repo::prediction_repo::PredictionRecord {
            sovereign_id,
            predicted_anomaly_type: "timeout_spam".to_string(),
            prediction_horizon_hours: 4,
            risk_score: 0.3,
            signal_breakdown: serde_json::json!({
                "chain": 0.6,
                "correlation": 0.0,
                "recovery": 0.0,
                "raw_risk_score": 0.3,
                "accuracy_weight": 1.0,
                "adjusted_risk_score": 0.3,
                "accuracy_sample_count": serde_json::Value::Null,
                "evidence": [
                    {
                        "signal_type": "AnomalyChainNode",
                        "signal_id": signal_id.to_string(),
                        "confidence": 0.6
                    }
                ]
            }),
            evidence: serde_json::json!({"top_chain_type": "dispute_spam→timeout_spam"}),
            last_computed_at: now,
        };
        let _pred_id = crate::repo::prediction_repo::upsert_prediction(&pool, &prediction)
            .await
            .expect("upsert prediction");

        // Record anomaly of DIFFERENT type (no match)
        let anomaly = AnomalyEvent {
            sovereign_id,
            anomaly_type: "dispute_spam".to_string(),
            detected_at: now + chrono::Duration::hours(2),
        };

        let feedback_id = record_feedback_for_anomaly(&pool, &anomaly)
            .await
            .expect("record_feedback failed")
            .expect("Should create feedback");

        // Verify feedback was created with matched=false
        let feedback = sqlx::query("SELECT properties FROM graph_entities WHERE id = $1")
            .bind(feedback_id)
            .fetch_one(&pool)
            .await
            .expect("Feedback not found");

        let feedback_props = feedback.get::<serde_json::Value, _>(0);
        let matched = feedback_props["matched"].as_bool().unwrap();
        assert!(!matched, "Feedback should be matched=false");

        // Verify signal confidence was NOT boosted
        let signal = sqlx::query("SELECT properties FROM graph_entities WHERE id = $1")
            .bind(signal_id)
            .fetch_one(&pool)
            .await
            .expect("Signal not found");

        let signal_props = signal.get::<serde_json::Value, _>(0);
        let confidence: f64 = signal_props["confidence"].as_f64().unwrap();
        assert_eq!(
            confidence, old_confidence,
            "Signal confidence should remain unchanged on no-match"
        );
    }
}
