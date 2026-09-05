use chrono::Utc;
use sqlx::{PgPool, Row};
use uuid::Uuid;

use crate::signal_tier_promotion::promote_signal_to_semantic_on_validation;

/// Reinforce signal nodes that contributed to a validated prediction.
/// When a FeedbackNode matches (true positive), the contributing signals
/// get a confidence boost: new = current + ((1.0 - current) * 0.05)
/// and last_seen_at is reset to now.
pub async fn reinforce_signals_for_feedback(
    pool: &PgPool,
    feedback_node_id: Uuid,
) -> Result<usize, sqlx::Error> {
    // 1. Fetch FeedbackNode
    let feedback_row = sqlx::query(
        "SELECT properties FROM graph_entities WHERE id = $1 AND label = 'FeedbackNode'",
    )
    .bind(feedback_node_id)
    .fetch_optional(pool)
    .await?;

    let feedback = match feedback_row {
        None => return Ok(0), // FeedbackNode not found
        Some(row) => row.get::<serde_json::Value, _>(0),
    };

    // 2. Check if matched=true
    let matched = feedback["matched"].as_bool().unwrap_or(false);
    if !matched {
        return Ok(0); // No reinforcement on false positives
    }

    // 3. Fetch PredictionNode ID from feedback properties
    let prediction_id_str = match feedback.get("prediction_node_id").and_then(|v| v.as_str()) {
        Some(id_str) => id_str,
        None => return Ok(0), // No prediction_node_id in feedback
    };

    let prediction_id = match Uuid::parse_str(prediction_id_str) {
        Ok(id) => id,
        Err(_) => return Ok(0), // Invalid UUID format
    };

    let prediction_row = sqlx::query(
        "SELECT properties FROM graph_entities WHERE id = $1 AND label = 'PredictionNode'",
    )
    .bind(prediction_id)
    .fetch_optional(pool)
    .await?;

    let prediction = match prediction_row {
        None => return Ok(0), // PredictionNode not found
        Some(row) => row.get::<serde_json::Value, _>(0),
    };

    // 4. Extract evidence array from signal_breakdown
    let signal_breakdown = match prediction.get("signal_breakdown") {
        Some(sb) => sb,
        None => return Ok(0),
    };

    let evidence = match signal_breakdown.get("evidence") {
        Some(ev) if ev.is_array() => ev.as_array().unwrap(),
        _ => return Ok(0),
    };

    // 5. Reinforce each signal
    let mut reinforced_count = 0;

    for evidence_item in evidence {
        let signal_type = match evidence_item.get("signal_type").and_then(|v| v.as_str()) {
            Some(t) => t,
            None => continue,
        };

        let signal_id = match evidence_item.get("signal_id").and_then(|v| v.as_str()) {
            Some(id_str) => match Uuid::parse_str(id_str) {
                Ok(id) => id,
                Err(_) => continue,
            },
            None => continue,
        };

        // Fetch signal node
        let signal_row =
            sqlx::query("SELECT properties FROM graph_entities WHERE id = $1 AND label = $2")
                .bind(signal_id)
                .bind(signal_type)
                .fetch_optional(pool)
                .await?;

        let mut signal_props = match signal_row {
            None => continue, // Signal not found
            Some(row) => row.get::<serde_json::Value, _>(0),
        };

        // Get current confidence
        let current_confidence = match signal_props.get("confidence").and_then(|v| v.as_f64()) {
            Some(c) => c,
            None => continue,
        };

        // Compute new confidence with 5% headroom boost
        let boost = (1.0 - current_confidence) * 0.05;
        let new_confidence = (current_confidence + boost).min(1.0); // Cap at 1.0

        // Update properties
        signal_props["confidence"] = serde_json::json!(new_confidence);
        signal_props["last_seen_at"] = serde_json::json!(Utc::now().to_rfc3339());

        // Upsert signal node
        sqlx::query(
            "INSERT INTO graph_entities (id, label, properties)
             VALUES ($1, $2, $3)
             ON CONFLICT (id) DO UPDATE SET properties = $3",
        )
        .bind(signal_id)
        .bind(signal_type)
        .bind(signal_props)
        .execute(pool)
        .await?;

        // Phase 34: Promote to Semantic tier if confidence now > 0.90
        let _ =
            promote_signal_to_semantic_on_validation(pool, signal_id, signal_type, new_confidence)
                .await;

        reinforced_count += 1;
    }

    Ok(reinforced_count)
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;
    use serde_json::json;
    use sqlx::Row;
    use testcontainers::core::WaitFor;
    use testcontainers::runners::AsyncRunner;
    use testcontainers::{GenericImage, ImageExt};

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
        let pool = sqlx::PgPool::connect(&url).await.expect("pool connect");
        crate::migrations::run_all(&pool).await.expect("migrations");
        (container, pool)
    }

    async fn insert_sovereign_node(pool: &PgPool, sovereign_name: &str) -> Uuid {
        let sovereign_id = Uuid::new_v4();
        let node_id = sovereign_id;
        let props = json!({
            "sovereign_id": sovereign_id.to_string(),
            "name": sovereign_name,
            "created_at": Utc::now().to_rfc3339(),
        });

        sqlx::query(
            "INSERT INTO graph_entities (id, label, properties, graph_id) VALUES ($1, 'SovereignNode', $2, 0)",
        )
        .bind(node_id)
        .bind(props)
        .execute(pool)
        .await
        .expect("insert sovereign node");

        sovereign_id
    }

    #[tokio::test]
    async fn test_reinforce_signals_boosts_confidence_5_percent_headroom() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = insert_sovereign_node(&pool, "test-sovereign").await;

        // Create an AnomalyChainNode with confidence 0.6
        let signal_id = Uuid::new_v4();
        let properties = json!({
            "sovereign_id": sovereign_id.to_string(),
            "chain_type": "dispute_spam→timeout_spam",
            "confidence": 0.6,
            "last_seen_at": Utc::now().to_rfc3339(),
        });
        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(signal_id)
            .bind("AnomalyChainNode")
            .bind(properties)
            .execute(&pool)
            .await
            .expect("Failed to insert signal");

        // Create a PredictionNode with evidence pointing to this signal
        let prediction_id = Uuid::new_v4();
        let pred_properties = json!({
            "sovereign_id": sovereign_id.to_string(),
            "predicted_anomaly_type": "timeout_spam",
            "prediction_horizon_hours": 4,
            "risk_score": 0.3,
            "signal_breakdown": {
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
            },
            "last_computed_at": Utc::now().to_rfc3339(),
        });
        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(prediction_id)
            .bind("PredictionNode")
            .bind(pred_properties)
            .execute(&pool)
            .await
            .expect("Failed to insert prediction");

        // Create a FeedbackNode with matched=true
        let feedback_id = Uuid::new_v4();
        let feedback_properties = json!({
            "prediction_node_id": prediction_id.to_string(),
            "sovereign_id": sovereign_id.to_string(),
            "predicted_anomaly_type": "timeout_spam",
            "matched": true,
            "anomaly_detected_at": Utc::now().to_rfc3339(),
            "prediction_risk_score": 0.3,
            "created_at": Utc::now().to_rfc3339(),
        });
        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(feedback_id)
            .bind("FeedbackNode")
            .bind(feedback_properties)
            .execute(&pool)
            .await
            .expect("Failed to insert feedback");

        // Call reinforce
        let count = reinforce_signals_for_feedback(&pool, feedback_id)
            .await
            .expect("reinforce failed");

        // Assert 1 signal was reinforced
        assert_eq!(count, 1, "Should reinforce 1 signal");

        // Fetch the signal and check confidence
        let signal = sqlx::query("SELECT properties FROM graph_entities WHERE id = $1")
            .bind(signal_id)
            .fetch_one(&pool)
            .await
            .expect("Signal not found");

        let signal_props = signal.get::<serde_json::Value, _>(0);
        let new_confidence: f64 = signal_props["confidence"].as_f64().unwrap();

        // Expected: 0.6 + ((1.0 - 0.6) * 0.05) = 0.6 + 0.02 = 0.62
        assert!(
            (new_confidence - 0.62).abs() < 0.001,
            "Confidence should be 0.62, got {}",
            new_confidence
        );

        // Check last_seen_at was updated (should be close to now, within 5 seconds)
        let last_seen_at_str = signal_props["last_seen_at"].as_str().unwrap();
        let last_seen_at = chrono::DateTime::parse_from_rfc3339(last_seen_at_str)
            .expect("Failed to parse last_seen_at")
            .with_timezone(&Utc);
        let now = Utc::now();
        let diff = (now - last_seen_at).num_seconds();
        assert!(
            (0..=5).contains(&diff),
            "last_seen_at should be very recent, diff={}",
            diff
        );
    }

    #[tokio::test]
    async fn test_reinforce_signals_asymptotic_at_1_0() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = insert_sovereign_node(&pool, "test-sovereign").await;

        // Create a signal with confidence 0.95 (high, close to ceiling)
        let signal_id = Uuid::new_v4();
        let properties = json!({
            "sovereign_id": sovereign_id.to_string(),
            "chain_type": "dispute_spam→timeout_spam",
            "confidence": 0.95,
            "last_seen_at": Utc::now().to_rfc3339(),
        });
        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(signal_id)
            .bind("AnomalyChainNode")
            .bind(properties)
            .execute(&pool)
            .await
            .expect("Failed to insert signal");

        // Create prediction with evidence
        let prediction_id = Uuid::new_v4();
        let pred_properties = json!({
            "sovereign_id": sovereign_id.to_string(),
            "predicted_anomaly_type": "timeout_spam",
            "prediction_horizon_hours": 4,
            "risk_score": 0.475,
            "signal_breakdown": {
                "chain": 0.95,
                "correlation": 0.0,
                "recovery": 0.0,
                "raw_risk_score": 0.475,
                "accuracy_weight": 1.0,
                "adjusted_risk_score": 0.475,
                "accuracy_sample_count": serde_json::Value::Null,
                "evidence": [
                    {
                        "signal_type": "AnomalyChainNode",
                        "signal_id": signal_id.to_string(),
                        "confidence": 0.95
                    }
                ]
            },
            "last_computed_at": Utc::now().to_rfc3339(),
        });
        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(prediction_id)
            .bind("PredictionNode")
            .bind(pred_properties)
            .execute(&pool)
            .await
            .expect("Failed to insert prediction");

        // Create matched feedback
        let feedback_id = Uuid::new_v4();
        let feedback_properties = json!({
            "prediction_node_id": prediction_id.to_string(),
            "sovereign_id": sovereign_id.to_string(),
            "predicted_anomaly_type": "timeout_spam",
            "matched": true,
            "anomaly_detected_at": Utc::now().to_rfc3339(),
            "prediction_risk_score": 0.475,
            "created_at": Utc::now().to_rfc3339(),
        });
        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(feedback_id)
            .bind("FeedbackNode")
            .bind(feedback_properties)
            .execute(&pool)
            .await
            .expect("Failed to insert feedback");

        // Reinforce
        let count = reinforce_signals_for_feedback(&pool, feedback_id)
            .await
            .expect("reinforce failed");

        assert_eq!(count, 1);

        // Fetch signal
        let signal = sqlx::query("SELECT properties FROM graph_entities WHERE id = $1")
            .bind(signal_id)
            .fetch_one(&pool)
            .await
            .expect("Signal not found");

        let signal_props = signal.get::<serde_json::Value, _>(0);
        let new_confidence: f64 = signal_props["confidence"].as_f64().unwrap();

        // Expected: 0.95 + ((1.0 - 0.95) * 0.05) = 0.95 + 0.0025 = 0.9525
        // Asymptotic: never exceeds 1.0
        assert!(
            (new_confidence - 0.9525).abs() < 0.001,
            "Confidence should be 0.9525, got {}",
            new_confidence
        );
        assert!(new_confidence < 1.0, "Should never exceed 1.0");
    }

    #[tokio::test]
    async fn test_reinforce_signals_does_not_penalize_on_false_positive() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = insert_sovereign_node(&pool, "test-sovereign").await;

        let signal_id = Uuid::new_v4();
        let properties = json!({
            "sovereign_id": sovereign_id.to_string(),
            "chain_type": "dispute_spam→timeout_spam",
            "confidence": 0.6,
            "last_seen_at": Utc::now().to_rfc3339(),
        });
        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(signal_id)
            .bind("AnomalyChainNode")
            .bind(properties)
            .execute(&pool)
            .await
            .expect("Failed to insert signal");

        let prediction_id = Uuid::new_v4();
        let pred_properties = json!({
            "sovereign_id": sovereign_id.to_string(),
            "predicted_anomaly_type": "timeout_spam",
            "prediction_horizon_hours": 4,
            "risk_score": 0.3,
            "signal_breakdown": {
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
            },
            "last_computed_at": Utc::now().to_rfc3339(),
        });
        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(prediction_id)
            .bind("PredictionNode")
            .bind(pred_properties)
            .execute(&pool)
            .await
            .expect("Failed to insert prediction");

        // FeedbackNode with matched=false (false positive)
        let feedback_id = Uuid::new_v4();
        let feedback_properties = json!({
            "prediction_node_id": prediction_id.to_string(),
            "sovereign_id": sovereign_id.to_string(),
            "predicted_anomaly_type": "timeout_spam",
            "matched": false,
            "anomaly_detected_at": serde_json::Value::Null,
            "prediction_risk_score": 0.3,
            "created_at": Utc::now().to_rfc3339(),
        });
        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(feedback_id)
            .bind("FeedbackNode")
            .bind(feedback_properties)
            .execute(&pool)
            .await
            .expect("Failed to insert feedback");

        // Reinforce should not modify signal (matched=false)
        let count = reinforce_signals_for_feedback(&pool, feedback_id)
            .await
            .expect("reinforce failed");

        assert_eq!(count, 0, "Should reinforce 0 signals on FP");

        // Verify signal confidence unchanged
        let signal = sqlx::query("SELECT properties FROM graph_entities WHERE id = $1")
            .bind(signal_id)
            .fetch_one(&pool)
            .await
            .expect("Signal not found");

        let signal_props = signal.get::<serde_json::Value, _>(0);
        let confidence: f64 = signal_props["confidence"].as_f64().unwrap();

        assert_eq!(confidence, 0.6, "Confidence should remain unchanged on FP");
    }

    #[tokio::test]
    async fn test_reinforce_signals_updates_all_contributing_signals() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = insert_sovereign_node(&pool, "test-sovereign").await;

        // Create 3 different signal types
        let chain_signal_id = Uuid::new_v4();
        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(chain_signal_id)
            .bind("AnomalyChainNode")
            .bind(json!({
                "sovereign_id": sovereign_id.to_string(),
                "chain_type": "dispute_spam→timeout_spam",
                "confidence": 0.6,
                "last_seen_at": Utc::now().to_rfc3339(),
            }))
            .execute(&pool)
            .await
            .expect("Failed to insert chain signal");

        let corr_signal_id = Uuid::new_v4();
        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(corr_signal_id)
            .bind("CorrelationPatternNode")
            .bind(json!({
                "sovereign_id": sovereign_id.to_string(),
                "pattern_type": "timeout_latency_correlation",
                "confidence": 0.5,
                "last_seen_at": Utc::now().to_rfc3339(),
            }))
            .execute(&pool)
            .await
            .expect("Failed to insert corr signal");

        let recovery_signal_id = Uuid::new_v4();
        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(recovery_signal_id)
            .bind("RecoveryCorrelationNode")
            .bind(json!({
                "sovereign_id": sovereign_id.to_string(),
                "anomaly_type": "timeout_spam",
                "confidence": 0.4,
                "last_seen_at": Utc::now().to_rfc3339(),
            }))
            .execute(&pool)
            .await
            .expect("Failed to insert recovery signal");

        // Create prediction with all 3 signals in evidence
        let prediction_id = Uuid::new_v4();
        let pred_properties = json!({
            "sovereign_id": sovereign_id.to_string(),
            "predicted_anomaly_type": "timeout_spam",
            "prediction_horizon_hours": 4,
            "risk_score": 0.48,
            "signal_breakdown": {
                "chain": 0.6,
                "correlation": 0.5,
                "recovery": 0.4,
                "raw_risk_score": 0.48,
                "accuracy_weight": 1.0,
                "adjusted_risk_score": 0.48,
                "accuracy_sample_count": serde_json::Value::Null,
                "evidence": [
                    {
                        "signal_type": "AnomalyChainNode",
                        "signal_id": chain_signal_id.to_string(),
                        "confidence": 0.6
                    },
                    {
                        "signal_type": "CorrelationPatternNode",
                        "signal_id": corr_signal_id.to_string(),
                        "confidence": 0.5
                    },
                    {
                        "signal_type": "RecoveryCorrelationNode",
                        "signal_id": recovery_signal_id.to_string(),
                        "confidence": 0.4
                    }
                ]
            },
            "last_computed_at": Utc::now().to_rfc3339(),
        });
        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(prediction_id)
            .bind("PredictionNode")
            .bind(pred_properties)
            .execute(&pool)
            .await
            .expect("Failed to insert prediction");

        // Create matched feedback
        let feedback_id = Uuid::new_v4();
        let feedback_properties = json!({
            "prediction_node_id": prediction_id.to_string(),
            "sovereign_id": sovereign_id.to_string(),
            "predicted_anomaly_type": "timeout_spam",
            "matched": true,
            "anomaly_detected_at": Utc::now().to_rfc3339(),
            "prediction_risk_score": 0.48,
            "created_at": Utc::now().to_rfc3339(),
        });
        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(feedback_id)
            .bind("FeedbackNode")
            .bind(feedback_properties)
            .execute(&pool)
            .await
            .expect("Failed to insert feedback");

        // Reinforce
        let count = reinforce_signals_for_feedback(&pool, feedback_id)
            .await
            .expect("reinforce failed");

        assert_eq!(count, 3, "Should reinforce all 3 signals");

        // Verify each signal was boosted correctly
        let chain_signal = sqlx::query("SELECT properties FROM graph_entities WHERE id = $1")
            .bind(chain_signal_id)
            .fetch_one(&pool)
            .await
            .expect("Chain signal not found");
        let chain_props = chain_signal.get::<serde_json::Value, _>(0);
        let chain_confidence: f64 = chain_props["confidence"].as_f64().unwrap();
        assert!(
            (chain_confidence - 0.62).abs() < 0.001,
            "Chain: 0.6 + 0.02 = 0.62"
        );

        let corr_signal = sqlx::query("SELECT properties FROM graph_entities WHERE id = $1")
            .bind(corr_signal_id)
            .fetch_one(&pool)
            .await
            .expect("Corr signal not found");
        let corr_props = corr_signal.get::<serde_json::Value, _>(0);
        let corr_confidence: f64 = corr_props["confidence"].as_f64().unwrap();
        assert!(
            (corr_confidence - 0.525).abs() < 0.001,
            "Corr: 0.5 + 0.025 = 0.525"
        );

        let recovery_signal = sqlx::query("SELECT properties FROM graph_entities WHERE id = $1")
            .bind(recovery_signal_id)
            .fetch_one(&pool)
            .await
            .expect("Recovery signal not found");
        let recovery_props = recovery_signal.get::<serde_json::Value, _>(0);
        let recovery_confidence: f64 = recovery_props["confidence"].as_f64().unwrap();
        assert!(
            (recovery_confidence - 0.43).abs() < 0.001,
            "Recovery: 0.4 + 0.03 = 0.43"
        );
    }
}
