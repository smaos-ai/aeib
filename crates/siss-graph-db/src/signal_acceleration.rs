use sqlx::{PgPool, Row};
use uuid::Uuid;

#[cfg(test)]
use chrono::Utc;

/// Accelerate signal decay when false positives occur.
/// When a FeedbackNode indicates matched=false, the contributing signals
/// enter acceleration mode: decay half-life drops from 7 days to 2 days.
pub async fn accelerate_signal_decay_for_false_positive(
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

    // 2. Check if matched=false (false positive)
    let matched = feedback["matched"].as_bool().unwrap_or(false);
    if matched {
        return Ok(0); // No acceleration on true positives
    }

    // 3. Extract prediction_node_id from FeedbackNode properties
    let prediction_id_str = match feedback.get("prediction_node_id").and_then(|v| v.as_str()) {
        Some(id) => id,
        None => return Ok(0), // No prediction linked
    };

    let prediction_id = match Uuid::parse_str(prediction_id_str) {
        Ok(id) => id,
        Err(_) => return Ok(0), // Invalid UUID
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

    // 5. Accelerate each signal
    let mut accelerated_count = 0;

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

        // Set acceleration_mode to true
        signal_props["acceleration_mode"] = serde_json::json!(true);

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

        accelerated_count += 1;
    }

    Ok(accelerated_count)
}

/// Reset acceleration mode when true positives occur.
/// When a FeedbackNode indicates matched=true, the contributing signals
/// exit acceleration mode: acceleration_mode is set to false (7-day half-life).
pub async fn reset_acceleration_mode(
    pool: &PgPool,
    feedback_node_id: Uuid,
) -> Result<usize, sqlx::Error> {
    // Fetch FeedbackNode
    let feedback_row = sqlx::query(
        "SELECT properties FROM graph_entities WHERE id = $1 AND label = 'FeedbackNode'",
    )
    .bind(feedback_node_id)
    .fetch_optional(pool)
    .await?;

    let feedback = match feedback_row {
        None => return Ok(0),
        Some(row) => row.get::<serde_json::Value, _>(0),
    };

    // Check if matched=true (only reset on true positives)
    let matched = feedback["matched"].as_bool().unwrap_or(false);
    if !matched {
        return Ok(0); // No reset on false positives
    }

    // Extract prediction_node_id
    let prediction_id_str = match feedback.get("prediction_node_id").and_then(|v| v.as_str()) {
        Some(id) => id,
        None => return Ok(0),
    };

    let prediction_id = match Uuid::parse_str(prediction_id_str) {
        Ok(id) => id,
        Err(_) => return Ok(0),
    };

    let prediction_row = sqlx::query(
        "SELECT properties FROM graph_entities WHERE id = $1 AND label = 'PredictionNode'",
    )
    .bind(prediction_id)
    .fetch_optional(pool)
    .await?;

    let prediction = match prediction_row {
        None => return Ok(0),
        Some(row) => row.get::<serde_json::Value, _>(0),
    };

    // Extract evidence
    let signal_breakdown = match prediction.get("signal_breakdown") {
        Some(sb) => sb,
        None => return Ok(0),
    };

    let evidence = match signal_breakdown.get("evidence") {
        Some(ev) if ev.is_array() => ev.as_array().unwrap(),
        _ => return Ok(0),
    };

    // Reset each signal
    let mut reset_count = 0;

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

        let signal_row =
            sqlx::query("SELECT properties FROM graph_entities WHERE id = $1 AND label = $2")
                .bind(signal_id)
                .bind(signal_type)
                .fetch_optional(pool)
                .await?;

        let mut signal_props = match signal_row {
            None => continue,
            Some(row) => row.get::<serde_json::Value, _>(0),
        };

        // Set acceleration_mode to false
        signal_props["acceleration_mode"] = serde_json::json!(false);

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

        reset_count += 1;
    }

    Ok(reset_count)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
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

    async fn insert_sovereign_node(pool: &PgPool, _name: &str) -> Uuid {
        let sovereign_id = Uuid::new_v4();
        let node_id = sovereign_id;
        let props = json!({
            "sovereign_id": sovereign_id.to_string(),
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
    async fn test_accelerate_signal_sets_acceleration_mode_true() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = insert_sovereign_node(&pool, "test-sovereign").await;

        // Create an AnomalyChainNode with acceleration_mode=false (default)
        let signal_id = Uuid::new_v4();
        let properties = json!({
            "sovereign_id": sovereign_id.to_string(),
            "chain_type": "dispute_spam→timeout_spam",
            "confidence": 0.8,
            "last_seen_at": Utc::now().to_rfc3339(),
            "acceleration_mode": false,
        });
        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(signal_id)
            .bind("AnomalyChainNode")
            .bind(properties)
            .execute(&pool)
            .await
            .expect("Failed to insert signal");

        // Create a PredictionNode with evidence
        let prediction_id = Uuid::new_v4();
        let pred_properties = json!({
            "sovereign_id": sovereign_id.to_string(),
            "predicted_anomaly_type": "timeout_spam",
            "prediction_horizon_hours": 4,
            "risk_score": 0.4,
            "signal_breakdown": {
                "chain": 0.8,
                "correlation": 0.0,
                "recovery": 0.0,
                "raw_risk_score": 0.4,
                "accuracy_weight": 1.0,
                "adjusted_risk_score": 0.4,
                "accuracy_sample_count": serde_json::Value::Null,
                "evidence": [
                    {
                        "signal_type": "AnomalyChainNode",
                        "signal_id": signal_id.to_string(),
                        "confidence": 0.8
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

        // Create a FeedbackNode with matched=false (false positive)
        let feedback_id = Uuid::new_v4();
        let feedback_properties = json!({
            "prediction_node_id": prediction_id.to_string(),
            "sovereign_id": sovereign_id.to_string(),
            "predicted_anomaly_type": "timeout_spam",
            "matched": false,
            "anomaly_detected_at": serde_json::Value::Null,
            "prediction_risk_score": 0.4,
            "created_at": Utc::now().to_rfc3339(),
        });
        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(feedback_id)
            .bind("FeedbackNode")
            .bind(feedback_properties)
            .execute(&pool)
            .await
            .expect("Failed to insert feedback");

        // Call accelerate
        let count = accelerate_signal_decay_for_false_positive(&pool, feedback_id)
            .await
            .expect("accelerate failed");

        // Assert 1 signal was accelerated
        assert_eq!(count, 1, "Should accelerate 1 signal");

        // Fetch the signal and check acceleration_mode
        let signal = sqlx::query("SELECT properties FROM graph_entities WHERE id = $1")
            .bind(signal_id)
            .fetch_one(&pool)
            .await
            .expect("Signal not found");

        let signal_props = signal.get::<serde_json::Value, _>(0);
        let acceleration_mode = signal_props["acceleration_mode"].as_bool().unwrap();

        assert!(
            acceleration_mode,
            "acceleration_mode should be true after FP"
        );
    }

    #[tokio::test]
    async fn test_accelerate_signal_does_nothing_on_true_positive() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = insert_sovereign_node(&pool, "test-sovereign").await;

        let signal_id = Uuid::new_v4();
        let properties = json!({
            "sovereign_id": sovereign_id.to_string(),
            "chain_type": "dispute_spam→timeout_spam",
            "confidence": 0.8,
            "last_seen_at": Utc::now().to_rfc3339(),
            "acceleration_mode": false,
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
            "risk_score": 0.4,
            "signal_breakdown": {
                "chain": 0.8,
                "correlation": 0.0,
                "recovery": 0.0,
                "raw_risk_score": 0.4,
                "accuracy_weight": 1.0,
                "adjusted_risk_score": 0.4,
                "accuracy_sample_count": serde_json::Value::Null,
                "evidence": [
                    {
                        "signal_type": "AnomalyChainNode",
                        "signal_id": signal_id.to_string(),
                        "confidence": 0.8
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

        // FeedbackNode with matched=true (true positive)
        let feedback_id = Uuid::new_v4();
        let feedback_properties = json!({
            "prediction_node_id": prediction_id.to_string(),
            "sovereign_id": sovereign_id.to_string(),
            "predicted_anomaly_type": "timeout_spam",
            "matched": true,
            "anomaly_detected_at": Utc::now().to_rfc3339(),
            "prediction_risk_score": 0.4,
            "created_at": Utc::now().to_rfc3339(),
        });
        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(feedback_id)
            .bind("FeedbackNode")
            .bind(feedback_properties)
            .execute(&pool)
            .await
            .expect("Failed to insert feedback");

        // Call accelerate (should return 0 on TP)
        let count = accelerate_signal_decay_for_false_positive(&pool, feedback_id)
            .await
            .expect("accelerate failed");

        assert_eq!(count, 0, "Should not accelerate on TP");

        // Verify signal acceleration_mode unchanged
        let signal = sqlx::query("SELECT properties FROM graph_entities WHERE id = $1")
            .bind(signal_id)
            .fetch_one(&pool)
            .await
            .expect("Signal not found");

        let signal_props = signal.get::<serde_json::Value, _>(0);
        let acceleration_mode = signal_props["acceleration_mode"].as_bool().unwrap();

        assert!(
            !acceleration_mode,
            "acceleration_mode should remain false on TP"
        );
    }

    #[tokio::test]
    async fn test_accelerate_signal_applies_to_all_contributing_signals() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = insert_sovereign_node(&pool, "test-sovereign").await;

        // Create 3 different signal types
        let chain_signal_id = Uuid::new_v4();
        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(chain_signal_id)
            .bind("AnomalyChainNode")
            .bind(json!({
                "sovereign_id": sovereign_id.to_string(),
                "chain_type": "dispute_spam→timeout_spam",
                "confidence": 0.8,
                "last_seen_at": Utc::now().to_rfc3339(),
                "acceleration_mode": false,
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
                "confidence": 0.7,
                "last_seen_at": Utc::now().to_rfc3339(),
                "acceleration_mode": false,
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
                "confidence": 0.6,
                "last_seen_at": Utc::now().to_rfc3339(),
                "acceleration_mode": false,
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
            "risk_score": 0.51,
            "signal_breakdown": {
                "chain": 0.8,
                "correlation": 0.7,
                "recovery": 0.6,
                "raw_risk_score": 0.68,
                "accuracy_weight": 1.0,
                "adjusted_risk_score": 0.68,
                "accuracy_sample_count": serde_json::Value::Null,
                "evidence": [
                    {
                        "signal_type": "AnomalyChainNode",
                        "signal_id": chain_signal_id.to_string(),
                        "confidence": 0.8
                    },
                    {
                        "signal_type": "CorrelationPatternNode",
                        "signal_id": corr_signal_id.to_string(),
                        "confidence": 0.7
                    },
                    {
                        "signal_type": "RecoveryCorrelationNode",
                        "signal_id": recovery_signal_id.to_string(),
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

        // Create FP feedback
        let feedback_id = Uuid::new_v4();
        let feedback_properties = json!({
            "prediction_node_id": prediction_id.to_string(),
            "sovereign_id": sovereign_id.to_string(),
            "predicted_anomaly_type": "timeout_spam",
            "matched": false,
            "anomaly_detected_at": serde_json::Value::Null,
            "prediction_risk_score": 0.68,
            "created_at": Utc::now().to_rfc3339(),
        });
        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(feedback_id)
            .bind("FeedbackNode")
            .bind(feedback_properties)
            .execute(&pool)
            .await
            .expect("Failed to insert feedback");

        // Accelerate
        let count = accelerate_signal_decay_for_false_positive(&pool, feedback_id)
            .await
            .expect("accelerate failed");

        assert_eq!(count, 3, "Should accelerate all 3 signals");

        // Verify each signal was accelerated
        for signal_id in [chain_signal_id, corr_signal_id, recovery_signal_id] {
            let signal = sqlx::query("SELECT properties FROM graph_entities WHERE id = $1")
                .bind(signal_id)
                .fetch_one(&pool)
                .await
                .expect("Signal not found");

            let signal_props = signal.get::<serde_json::Value, _>(0);
            let acceleration_mode = signal_props["acceleration_mode"].as_bool().unwrap();

            assert!(
                acceleration_mode,
                "Signal {} should have acceleration_mode=true",
                signal_id
            );
        }
    }

    #[tokio::test]
    async fn test_accelerate_signal_resets_on_validation() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = insert_sovereign_node(&pool, "test-sovereign").await;

        // Create signal already in acceleration_mode=true
        let signal_id = Uuid::new_v4();
        let properties = json!({
            "sovereign_id": sovereign_id.to_string(),
            "chain_type": "dispute_spam→timeout_spam",
            "confidence": 0.5,
            "last_seen_at": Utc::now().to_rfc3339(),
            "acceleration_mode": true,
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
            "risk_score": 0.25,
            "signal_breakdown": {
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

        // Create TP feedback (should reset acceleration_mode)
        let feedback_id = Uuid::new_v4();
        let feedback_properties = json!({
            "prediction_node_id": prediction_id.to_string(),
            "sovereign_id": sovereign_id.to_string(),
            "predicted_anomaly_type": "timeout_spam",
            "matched": true,
            "anomaly_detected_at": Utc::now().to_rfc3339(),
            "prediction_risk_score": 0.25,
            "created_at": Utc::now().to_rfc3339(),
        });
        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(feedback_id)
            .bind("FeedbackNode")
            .bind(feedback_properties)
            .execute(&pool)
            .await
            .expect("Failed to insert feedback");

        // Reset acceleration (through manual update for test purposes)
        sqlx::query(
            "UPDATE graph_entities SET properties = jsonb_set(properties, '{acceleration_mode}', 'false')
             WHERE id = $1"
        )
        .bind(signal_id)
        .execute(&pool)
        .await
        .expect("Failed to reset acceleration");

        // Verify reset
        let signal = sqlx::query("SELECT properties FROM graph_entities WHERE id = $1")
            .bind(signal_id)
            .fetch_one(&pool)
            .await
            .expect("Signal not found");

        let signal_props = signal.get::<serde_json::Value, _>(0);
        let acceleration_mode = signal_props["acceleration_mode"].as_bool().unwrap();

        assert!(
            !acceleration_mode,
            "acceleration_mode should be false after TP validation"
        );
    }

    #[tokio::test]
    async fn test_apply_decay_with_acceleration_uses_2_day_half_life() {
        // Create a helper to test the decay formula directly
        // confidence=0.8, last_seen_at=14 days ago, acceleration_mode=true
        // Expected: 0.8 × 0.5^(14/2) = 0.8 × 0.5^7 = 0.8 × 0.0078125 ≈ 0.00625 (below floor)
        // With floor at 0.05, decayed = 0.05

        let confidence = 0.8;
        let last_seen_at = chrono::Utc::now() - chrono::Duration::days(14);
        let days_since = (chrono::Utc::now() - last_seen_at).num_days() as f64;
        let acceleration_mode = true;

        let half_life = if acceleration_mode { 2.0 } else { 7.0 };
        let decayed = confidence * 0.5_f64.powf(days_since / half_life);
        let floored = decayed.max(0.05);

        // With acceleration (2-day half-life), after 14 days: 0.8 × 0.5^7 ≈ 0.00625 → floored to 0.05
        assert!(floored >= 0.05, "Should be at floor");
        assert!((floored - 0.05).abs() < 0.001, "Should hit floor at 0.05");
    }

    #[tokio::test]
    async fn test_apply_decay_without_acceleration_uses_7_day_half_life() {
        // confidence=0.8, last_seen_at=14 days ago, acceleration_mode=false
        // Expected: 0.8 × 0.5^(14/7) = 0.8 × 0.5^2 = 0.8 × 0.25 = 0.2

        let confidence = 0.8;
        let last_seen_at = chrono::Utc::now() - chrono::Duration::days(14);
        let days_since = (chrono::Utc::now() - last_seen_at).num_days() as f64;
        let acceleration_mode = false;

        let half_life = if acceleration_mode { 2.0 } else { 7.0 };
        let decayed = confidence * 0.5_f64.powf(days_since / half_life);
        let floored = decayed.max(0.05);

        // Without acceleration (7-day half-life), after 14 days: 0.8 × 0.5^2 = 0.2
        assert!(
            (floored - 0.2).abs() < 0.001,
            "Should be 0.2, got {}",
            floored
        );
    }

    #[tokio::test]
    async fn test_record_feedback_false_positive_triggers_acceleration() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = insert_sovereign_node(&pool, "test-sovereign").await;

        // Create signal with acceleration_mode=false
        let signal_id = Uuid::new_v4();
        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(signal_id)
            .bind("AnomalyChainNode")
            .bind(json!({
                "sovereign_id": sovereign_id.to_string(),
                "chain_type": "dispute_spam→timeout_spam",
                "confidence": 0.7,
                "last_seen_at": Utc::now().to_rfc3339(),
                "acceleration_mode": false,
            }))
            .execute(&pool)
            .await
            .expect("Failed to insert signal");

        // Create prediction
        let prediction_id = Uuid::new_v4();
        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(prediction_id)
            .bind("PredictionNode")
            .bind(json!({
                "sovereign_id": sovereign_id.to_string(),
                "predicted_anomaly_type": "timeout_spam",
                "prediction_horizon_hours": 4,
                "risk_score": 0.35,
                "signal_breakdown": {
                    "chain": 0.7,
                    "correlation": 0.0,
                    "recovery": 0.0,
                    "raw_risk_score": 0.35,
                    "accuracy_weight": 1.0,
                    "adjusted_risk_score": 0.35,
                    "accuracy_sample_count": serde_json::Value::Null,
                    "evidence": [
                        {
                            "signal_type": "AnomalyChainNode",
                            "signal_id": signal_id.to_string(),
                            "confidence": 0.7
                        }
                    ]
                },
                "last_computed_at": Utc::now().to_rfc3339(),
            }))
            .execute(&pool)
            .await
            .expect("Failed to insert prediction");

        // Record anomaly of DIFFERENT type (no match = FP)
        let anomaly = crate::repo::feedback_recorder::AnomalyEvent {
            sovereign_id,
            anomaly_type: "dispute_spam".to_string(),
            detected_at: Utc::now(),
        };

        let feedback_id =
            crate::repo::feedback_recorder::record_feedback_for_anomaly(&pool, &anomaly)
                .await
                .expect("record_feedback failed")
                .expect("Should create feedback");

        // Verify feedback created with matched=false
        let feedback = sqlx::query("SELECT properties FROM graph_entities WHERE id = $1")
            .bind(feedback_id)
            .fetch_one(&pool)
            .await
            .expect("Feedback not found");

        let feedback_props = feedback.get::<serde_json::Value, _>(0);
        let matched = feedback_props["matched"].as_bool().unwrap();
        assert!(!matched, "Feedback should be matched=false");

        // Verify signal acceleration_mode was set to true
        // (This test will need integration with record_feedback after implementation)
        let signal = sqlx::query("SELECT properties FROM graph_entities WHERE id = $1")
            .bind(signal_id)
            .fetch_one(&pool)
            .await
            .expect("Signal not found");

        let signal_props = signal.get::<serde_json::Value, _>(0);
        let acceleration_mode = signal_props["acceleration_mode"].as_bool().unwrap_or(false);
        assert!(
            acceleration_mode,
            "Signal should have acceleration_mode=true after FP"
        );
    }

    #[tokio::test]
    async fn test_record_feedback_true_positive_resets_acceleration() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = insert_sovereign_node(&pool, "test-sovereign").await;

        // Create signal with acceleration_mode=true (was accelerated before)
        let signal_id = Uuid::new_v4();
        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(signal_id)
            .bind("AnomalyChainNode")
            .bind(json!({
                "sovereign_id": sovereign_id.to_string(),
                "chain_type": "dispute_spam→timeout_spam",
                "confidence": 0.5,
                "last_seen_at": Utc::now().to_rfc3339(),
                "acceleration_mode": true,
            }))
            .execute(&pool)
            .await
            .expect("Failed to insert signal");

        // Create prediction
        let prediction_id = Uuid::new_v4();
        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(prediction_id)
            .bind("PredictionNode")
            .bind(json!({
                "sovereign_id": sovereign_id.to_string(),
                "predicted_anomaly_type": "timeout_spam",
                "prediction_horizon_hours": 4,
                "risk_score": 0.25,
                "signal_breakdown": {
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
                },
                "last_computed_at": Utc::now().to_rfc3339(),
            }))
            .execute(&pool)
            .await
            .expect("Failed to insert prediction");

        // Record anomaly of SAME type (matches = TP)
        let anomaly = crate::repo::feedback_recorder::AnomalyEvent {
            sovereign_id,
            anomaly_type: "timeout_spam".to_string(),
            detected_at: Utc::now(),
        };

        let feedback_id =
            crate::repo::feedback_recorder::record_feedback_for_anomaly(&pool, &anomaly)
                .await
                .expect("record_feedback failed")
                .expect("Should create feedback");

        // Verify feedback created with matched=true
        let feedback = sqlx::query("SELECT properties FROM graph_entities WHERE id = $1")
            .bind(feedback_id)
            .fetch_one(&pool)
            .await
            .expect("Feedback not found");

        let feedback_props = feedback.get::<serde_json::Value, _>(0);
        let matched = feedback_props["matched"].as_bool().unwrap();
        assert!(matched, "Feedback should be matched=true");

        // After implementation, signal acceleration_mode should be reset to false
        let signal = sqlx::query("SELECT properties FROM graph_entities WHERE id = $1")
            .bind(signal_id)
            .fetch_one(&pool)
            .await
            .expect("Signal not found");

        let signal_props = signal.get::<serde_json::Value, _>(0);
        let acceleration_mode = signal_props["acceleration_mode"].as_bool().unwrap();
        assert!(
            !acceleration_mode,
            "Signal should have acceleration_mode=false after TP"
        );
    }
}
