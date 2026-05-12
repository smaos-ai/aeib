use chrono::{DateTime, Utc};
use serde_json::json;
use sqlx::{FromRow, PgPool};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::Duration;
use tokio::task::JoinHandle;
use uuid::Uuid;

use crate::repo::intelligence_graph_repo::get_or_create_sovereign_node;
use crate::repo::prediction_query::fetch_sovereign_signals;
use crate::repo::prediction_repo::{PredictionRecord, upsert_prediction};
use crate::signal_tier_promotion::apply_decay_with_tier;

pub const DEFAULT_FORECAST_INTERVAL: Duration = Duration::from_secs(60);

/// JSONB bulk query row for AccuracyMetricsNode
#[derive(Debug, Clone, FromRow)]
struct AccuracyMetricsRow {
    sovereign_id: Uuid,
    anomaly_type: String,
    precision: Option<f64>,
    sample_count: i64,
}

/// Lightweight wrapper for accuracy weight storage
#[derive(Debug, Clone)]
struct AccuracyWeight {
    precision: Option<f64>,
    sample_count: i64,
}

/// Load accuracy weights from graph_entities (AccuracyMetricsNode records).
/// Returns a HashMap keyed by (sovereign_id, anomaly_type).
async fn load_accuracy_weights(
    pool: &PgPool,
) -> Result<HashMap<(Uuid, String), AccuracyWeight>, sqlx::Error> {
    let rows: Vec<AccuracyMetricsRow> = sqlx::query_as(
        "SELECT
            (properties->>'sovereign_id')::uuid AS sovereign_id,
            properties->>'anomaly_type' AS anomaly_type,
            (properties->>'precision')::float AS precision,
            (properties->>'sample_count')::bigint AS sample_count
        FROM graph_entities
        WHERE label = 'AccuracyMetricsNode'",
    )
    .fetch_all(pool)
    .await?;

    let mut map = HashMap::new();
    for row in rows {
        map.insert(
            (row.sovereign_id, row.anomaly_type),
            AccuracyWeight {
                precision: row.precision,
                sample_count: row.sample_count,
            },
        );
    }
    Ok(map)
}

/// Compute accuracy weight from AccuracyWeight record.
/// Returns 1.0 (no adjustment) if no data, sample_count < 5, or precision is None.
/// Otherwise returns (precision / 0.5).min(1.0).
fn compute_accuracy_weight(weight: Option<&AccuracyWeight>) -> f64 {
    match weight {
        None => 1.0,
        Some(w) if w.sample_count < 5 => 1.0,
        Some(w) => match w.precision {
            None => 1.0,
            Some(p) => (p / 0.5_f64).min(1.0),
        },
    }
}

/// Run forecast once: aggregate all signals per sovereign, compute risk scores, and upsert predictions.
/// Returns count of PredictionNodes created or updated.
pub async fn run_forecast_once(pool: &PgPool) -> Result<usize, sqlx::Error> {
    let signals = fetch_sovereign_signals(pool).await?;

    // Aggregate signals by sovereign and signal type
    struct SovereignSignals {
        max_chain_confidence: f64,
        max_correlation_confidence: f64,
        max_recovery_confidence: f64,
        top_chain_type: Option<String>,
        top_anomaly_type: Option<String>,
    }

    impl Default for SovereignSignals {
        fn default() -> Self {
            Self {
                max_chain_confidence: 0.0,
                max_correlation_confidence: 0.0,
                max_recovery_confidence: 0.0,
                top_chain_type: None,
                top_anomaly_type: None,
            }
        }
    }

    let mut by_sovereign: HashMap<Uuid, SovereignSignals> = HashMap::new();

    for row in signals {
        // Apply decay to this signal, respecting tier (Phase 34 tier promotion)
        let decayed_confidence = apply_decay_with_tier(
            row.confidence,
            row.last_seen_at,
            &row.tier,
            row.acceleration_mode,
        );

        // Skip signals at or below 0.05 floor (floored signals are discarded)
        if decayed_confidence <= 0.05 {
            continue;
        }

        let entry = by_sovereign.entry(row.sovereign_id).or_default();

        match row.signal_type.as_str() {
            "AnomalyChainNode" if decayed_confidence > entry.max_chain_confidence => {
                entry.max_chain_confidence = decayed_confidence;
                entry.top_chain_type = row.chain_type;
            }
            "CorrelationPatternNode" if decayed_confidence > entry.max_correlation_confidence => {
                entry.max_correlation_confidence = decayed_confidence;
            }
            "RecoveryCorrelationNode" if decayed_confidence > entry.max_recovery_confidence => {
                entry.max_recovery_confidence = decayed_confidence;
                entry.top_anomaly_type = row.anomaly_type;
            }
            _ => {}
        }
    }

    // Process each sovereign with signals
    let mut count = 0;

    let accuracy_weights = load_accuracy_weights(pool).await?;

    for (sovereign_id, signals) in by_sovereign {
        // Skip if no signals
        if signals.max_chain_confidence == 0.0
            && signals.max_correlation_confidence == 0.0
            && signals.max_recovery_confidence == 0.0
        {
            continue;
        }

        // Determine predicted anomaly type
        let predicted_anomaly_type = if signals.max_chain_confidence > 0.0 {
            // Extract end type from chain (e.g., "dispute_spam→timeout_spam" → "timeout_spam")
            if let Some(ref chain_type) = signals.top_chain_type {
                if let Some(end) = chain_type.split('→').nth(1) {
                    end.to_string()
                } else {
                    signals
                        .top_anomaly_type
                        .clone()
                        .unwrap_or_else(|| "unknown".to_string())
                }
            } else {
                signals
                    .top_anomaly_type
                    .clone()
                    .unwrap_or_else(|| "unknown".to_string())
            }
        } else {
            signals
                .top_anomaly_type
                .clone()
                .unwrap_or_else(|| "unknown".to_string())
        };

        // Calculate raw risk score: 0.5*chain + 0.3*correlation + 0.2*recovery
        let raw_risk_score = (0.5 * signals.max_chain_confidence
            + 0.3 * signals.max_correlation_confidence
            + 0.2 * signals.max_recovery_confidence)
            .min(1.0);

        let accuracy_weight = compute_accuracy_weight(
            accuracy_weights.get(&(sovereign_id, predicted_anomaly_type.clone())),
        );
        let risk_score = raw_risk_score * accuracy_weight;

        // Create signal breakdown
        let signal_breakdown = json!({
            "chain": signals.max_chain_confidence,
            "correlation": signals.max_correlation_confidence,
            "recovery": signals.max_recovery_confidence,
            "raw_risk_score": raw_risk_score,
            "accuracy_weight": accuracy_weight,
            "adjusted_risk_score": risk_score,
            "accuracy_sample_count": accuracy_weights.get(&(sovereign_id, predicted_anomaly_type.clone())).map(|w| w.sample_count),
        });

        // Create evidence
        let evidence = json!({
            "top_chain_type": signals.top_chain_type,
            "top_anomaly_type": signals.top_anomaly_type,
        });

        // Upsert prediction node
        let prediction_record = PredictionRecord {
            sovereign_id,
            predicted_anomaly_type,
            prediction_horizon_hours: 4,
            risk_score,
            signal_breakdown,
            evidence,
            last_computed_at: Utc::now(),
        };

        let prediction_node_id = upsert_prediction(pool, &prediction_record).await?;

        // Get or create sovereign node and link with PREDICTS edge
        let sovereign_node_id = get_or_create_sovereign_node(pool, sovereign_id).await?;

        sqlx::query(
            "INSERT INTO graph_relationships (source_entity_id, target_entity_id, relationship_type)
             VALUES ($1, $2, 'PREDICTS')
             ON CONFLICT (source_entity_id, target_entity_id, relationship_type) DO NOTHING",
        )
        .bind(prediction_node_id)
        .bind(sovereign_node_id)
        .execute(pool)
        .await?;

        count += 1;
    }

    Ok(count)
}

/// Start the forecast engine background task.
pub fn start_forecast_engine(pool: Arc<PgPool>, interval: Duration) -> JoinHandle<()> {
    tokio::spawn(async move {
        loop {
            let _ = run_forecast_once(&pool).await;
            tokio::time::sleep(interval).await;
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use sqlx::Row;
    use testcontainers::runners::AsyncRunner;
    use testcontainers::{GenericImage, ImageExt, core::WaitFor};

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

    /// Helper: insert an AnomalyChainNode
    async fn insert_anomaly_chain_node(
        pool: &PgPool,
        sovereign_id: Uuid,
        chain_type: &str,
        confidence: f64,
    ) -> Uuid {
        let node_id = Uuid::new_v4();
        let props = json!({
            "sovereign_id": sovereign_id.to_string(),
            "chain_type": chain_type,
            "chain_length": 2,
            "start_anomaly_type": "dispute_spam",
            "end_anomaly_type": "timeout_spam",
            "occurrence_count": 1,
            "avg_elapsed_hours": 2.5,
            "confidence": confidence,
            "last_seen_at": Utc::now().to_rfc3339(),
            "evidence": {},
        });

        sqlx::query(
            "INSERT INTO graph_entities (id, label, properties, graph_id) VALUES ($1, 'AnomalyChainNode', $2, 0)",
        )
        .bind(node_id)
        .bind(props)
        .execute(pool)
        .await
        .expect("insert anomaly chain node");

        node_id
    }

    /// Helper: insert a CorrelationPatternNode
    async fn insert_correlation_pattern_node(
        pool: &PgPool,
        sovereign_id: Uuid,
        event_type: &str,
        anomaly_type: &str,
        confidence: f64,
    ) -> Uuid {
        let node_id = Uuid::new_v4();
        let props = json!({
            "sovereign_id": sovereign_id.to_string(),
            "event_type": event_type,
            "anomaly_type": anomaly_type,
            "co_occurrence_count": 5,
            "confidence": confidence,
            "last_seen_at": Utc::now().to_rfc3339(),
            "evidence": {},
        });

        sqlx::query(
            "INSERT INTO graph_entities (id, label, properties, graph_id) VALUES ($1, 'CorrelationPatternNode', $2, 0)",
        )
        .bind(node_id)
        .bind(props)
        .execute(pool)
        .await
        .expect("insert correlation pattern node");

        node_id
    }

    /// Helper: insert a RecoveryCorrelationNode
    async fn insert_recovery_correlation_node(
        pool: &PgPool,
        sovereign_id: Uuid,
        anomaly_type: &str,
        confidence: f64,
    ) -> Uuid {
        let node_id = Uuid::new_v4();
        let props = json!({
            "sovereign_id": sovereign_id.to_string(),
            "anomaly_type": anomaly_type,
            "occurrence_count": 2,
            "avg_gap_hours": 12.0,
            "confidence": confidence,
            "last_seen_at": Utc::now().to_rfc3339(),
            "evidence": {},
        });

        sqlx::query(
            "INSERT INTO graph_entities (id, label, properties, graph_id) VALUES ($1, 'RecoveryCorrelationNode', $2, 0)",
        )
        .bind(node_id)
        .bind(props)
        .execute(pool)
        .await
        .expect("insert recovery correlation node");

        node_id
    }

    /// Helper: insert a SovereignNode
    async fn insert_sovereign_node(pool: &PgPool, sovereign_id: Uuid) -> Uuid {
        let node_id = sovereign_id; // Use same UUID as sovereignty identifier
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

        node_id
    }

    /// Helper: insert an AccuracyMetricsNode
    async fn insert_accuracy_metrics_node(
        pool: &PgPool,
        sovereign_id: Uuid,
        anomaly_type: &str,
        precision: Option<f64>,
        sample_count: i64,
    ) -> Uuid {
        let node_id = Uuid::new_v4();
        let properties = json!({
            "sovereign_id": sovereign_id.to_string(),
            "anomaly_type": anomaly_type,
            "precision": precision,
            "sample_count": sample_count,
            "true_positives": 0,
            "false_positives": 0,
            "false_negatives": 0,
            "recall": serde_json::Value::Null,
            "avg_risk_score_correct": serde_json::Value::Null,
            "avg_risk_score_incorrect": serde_json::Value::Null,
            "last_updated_at": Utc::now().to_rfc3339(),
        });

        sqlx::query(
            "INSERT INTO graph_entities (id, label, properties)
             VALUES ($1, $2, $3)
             ON CONFLICT (id) DO UPDATE SET properties = $3",
        )
        .bind(node_id)
        .bind("AccuracyMetricsNode")
        .bind(properties)
        .execute(pool)
        .await
        .expect("Failed to insert test AccuracyMetricsNode");

        node_id
    }

    #[tokio::test]
    async fn test_forecast_with_chain_signal_predicts_end_type() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let _sov_node = insert_sovereign_node(&pool, sovereign_id).await;

        // Insert chain signal: dispute_spam → timeout_spam, confidence 0.6
        let _chain_id =
            insert_anomaly_chain_node(&pool, sovereign_id, "dispute_spam→timeout_spam", 0.6).await;

        // Run forecast
        let count = run_forecast_once(&pool).await.expect("run forecast");

        assert!(count > 0, "Should create at least one prediction");

        // Verify PredictionNode was created with predicted_anomaly_type = "timeout_spam"
        let prediction: (String,) = sqlx::query_as(
            "SELECT properties->>'predicted_anomaly_type' FROM graph_entities WHERE label = 'PredictionNode' AND properties->>'sovereign_id' = $1",
        )
        .bind(sovereign_id.to_string())
        .fetch_one(&pool)
        .await
        .expect("query prediction");

        assert_eq!(
            prediction.0, "timeout_spam",
            "Predicted anomaly type should be extracted from chain end type"
        );
    }

    #[tokio::test]
    async fn test_forecast_with_only_correlation_signal() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let _sov_node = insert_sovereign_node(&pool, sovereign_id).await;

        // Insert correlation signal only: event→dispute_spam, confidence 0.7
        let _corr_id =
            insert_correlation_pattern_node(&pool, sovereign_id, "some_event", "dispute_spam", 0.7)
                .await;

        // Run forecast
        let count = run_forecast_once(&pool).await.expect("run forecast");

        assert!(count > 0, "Should create at least one prediction");

        // Verify risk_score = 0.3 * 0.7 = 0.21
        let risk: (f64,) = sqlx::query_as(
            "SELECT (properties->>'risk_score')::float FROM graph_entities WHERE label = 'PredictionNode' AND properties->>'sovereign_id' = $1",
        )
        .bind(sovereign_id.to_string())
        .fetch_one(&pool)
        .await
        .expect("query prediction");

        assert!(
            (risk.0 - 0.21).abs() < 0.01,
            "risk_score should be 0.3 * 0.7 = 0.21"
        );
    }

    #[tokio::test]
    async fn test_forecast_with_all_signals_combines_weights() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let _sov_node = insert_sovereign_node(&pool, sovereign_id).await;

        // Insert all three signal types with different confidences
        let _chain_id =
            insert_anomaly_chain_node(&pool, sovereign_id, "dispute_spam→timeout_spam", 0.6).await;
        let _corr_id =
            insert_correlation_pattern_node(&pool, sovereign_id, "some_event", "timeout_spam", 0.5)
                .await;
        let _recovery_id =
            insert_recovery_correlation_node(&pool, sovereign_id, "timeout_spam", 0.4).await;

        // Run forecast
        let count = run_forecast_once(&pool).await.expect("run forecast");

        assert!(count > 0, "Should create at least one prediction");

        // Verify risk_score = 0.5 * 0.6 + 0.3 * 0.5 + 0.2 * 0.4 = 0.3 + 0.15 + 0.08 = 0.53
        let risk: (f64,) = sqlx::query_as(
            "SELECT (properties->>'risk_score')::float FROM graph_entities WHERE label = 'PredictionNode' AND properties->>'sovereign_id' = $1",
        )
        .bind(sovereign_id.to_string())
        .fetch_one(&pool)
        .await
        .expect("query prediction");

        assert!(
            (risk.0 - 0.53).abs() < 0.01,
            "risk_score should be 0.5*0.6 + 0.3*0.5 + 0.2*0.4 = 0.53"
        );
    }

    #[tokio::test]
    async fn test_forecast_no_signal_no_prediction() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let _sov_node = insert_sovereign_node(&pool, sovereign_id).await;

        // Don't insert any signal nodes

        // Run forecast
        let count = run_forecast_once(&pool).await.expect("run forecast");

        // Should not create any predictions
        let prediction_count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities WHERE label = 'PredictionNode' AND properties->>'sovereign_id' = $1",
        )
        .bind(sovereign_id.to_string())
        .fetch_one(&pool)
        .await
        .expect("query count");

        assert_eq!(
            prediction_count.0, 0,
            "Should not create prediction without any signal nodes"
        );
    }

    #[tokio::test]
    async fn test_run_forecast_once_creates_predicts_edge() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let sov_node = insert_sovereign_node(&pool, sovereign_id).await;

        // Insert chain signal
        let _chain_id =
            insert_anomaly_chain_node(&pool, sovereign_id, "dispute_spam→timeout_spam", 0.6).await;

        // Run forecast
        let count = run_forecast_once(&pool).await.expect("run forecast");

        assert!(count > 0, "Should create at least one prediction");

        // Verify PREDICTS edge exists
        let edge_result: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_relationships WHERE relationship_type = 'PREDICTS' AND target_entity_id = $1",
        )
        .bind(sov_node)
        .fetch_one(&pool)
        .await
        .expect("query edge");

        assert_eq!(
            edge_result.0, 1,
            "PREDICTS edge should exist from PredictionNode to SovereignNode"
        );
    }

    #[tokio::test]
    async fn test_run_forecast_idempotent() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let _sov_node = insert_sovereign_node(&pool, sovereign_id).await;

        // Insert chain signal
        let _chain_id =
            insert_anomaly_chain_node(&pool, sovereign_id, "dispute_spam→timeout_spam", 0.6).await;

        // First forecast
        let count1 = run_forecast_once(&pool).await.expect("run forecast 1");
        assert!(count1 > 0);

        // Second forecast (idempotent)
        let count2 = run_forecast_once(&pool).await.expect("run forecast 2");

        // Should not create duplicate edges on re-run
        let edge_result: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_relationships WHERE relationship_type = 'PREDICTS'",
        )
        .fetch_one(&pool)
        .await
        .expect("query edge count");

        // count1 edges created, count2 should be 0 (no new edges due to idempotency)
        assert_eq!(
            edge_result.0, 1,
            "Re-forecast should not create duplicate PREDICTS edges"
        );
    }

    #[tokio::test]
    async fn test_decay_at_zero_days_is_identity() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let _sov_node = insert_sovereign_node(&pool, sovereign_id).await;

        // Insert chain signal with last_seen_at = now, confidence = 0.8
        let now = Utc::now();
        let node_id = Uuid::new_v4();
        let props = json!({
            "sovereign_id": sovereign_id.to_string(),
            "chain_type": "dispute_spam→timeout_spam",
            "chain_length": 2,
            "start_anomaly_type": "dispute_spam",
            "end_anomaly_type": "timeout_spam",
            "occurrence_count": 1,
            "avg_elapsed_hours": 2.5,
            "confidence": 0.8,
            "last_seen_at": now.to_rfc3339(),
            "evidence": {},
        });

        sqlx::query(
            "INSERT INTO graph_entities (id, label, properties, graph_id) VALUES ($1, 'AnomalyChainNode', $2, 0)",
        )
        .bind(node_id)
        .bind(props)
        .execute(&pool)
        .await
        .expect("insert chain node");

        // Run forecast
        let count = run_forecast_once(&pool).await.expect("run forecast");

        assert!(count > 0, "Should create at least one prediction");

        // Verify risk_score reflects full (non-decayed) confidence
        // With only chain signal (no decay), risk should be 0.5 * 0.8 = 0.4
        let risk: (f64,) = sqlx::query_as(
            "SELECT (properties->>'risk_score')::float FROM graph_entities WHERE label = 'PredictionNode' AND properties->>'sovereign_id' = $1",
        )
        .bind(sovereign_id.to_string())
        .fetch_one(&pool)
        .await
        .expect("query prediction");

        assert!(
            (risk.0 - 0.4).abs() < 0.01,
            "risk_score should be 0.5 * 0.8 = 0.4 (no decay at time 0)"
        );
    }

    #[tokio::test]
    async fn test_decay_at_seven_days_is_half() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let _sov_node = insert_sovereign_node(&pool, sovereign_id).await;

        // Insert chain signal with last_seen_at = 7 days ago, confidence = 0.8
        let seven_days_ago = Utc::now() - Duration::from_secs(7 * 24 * 3600);
        let node_id = Uuid::new_v4();
        let props = json!({
            "sovereign_id": sovereign_id.to_string(),
            "chain_type": "dispute_spam→timeout_spam",
            "chain_length": 2,
            "start_anomaly_type": "dispute_spam",
            "end_anomaly_type": "timeout_spam",
            "occurrence_count": 1,
            "avg_elapsed_hours": 2.5,
            "confidence": 0.8,
            "last_seen_at": seven_days_ago.to_rfc3339(),
            "evidence": {},
        });

        sqlx::query(
            "INSERT INTO graph_entities (id, label, properties, graph_id) VALUES ($1, 'AnomalyChainNode', $2, 0)",
        )
        .bind(node_id)
        .bind(props)
        .execute(&pool)
        .await
        .expect("insert chain node");

        // Run forecast
        let count = run_forecast_once(&pool).await.expect("run forecast");

        assert!(count > 0, "Should create at least one prediction");

        // Verify risk_score reflects decayed confidence
        // With only chain signal at 7-day decay: 0.8 * 0.5 = 0.4 (decayed confidence)
        // Risk = 0.5 * 0.4 = 0.2
        let risk: (f64,) = sqlx::query_as(
            "SELECT (properties->>'risk_score')::float FROM graph_entities WHERE label = 'PredictionNode' AND properties->>'sovereign_id' = $1",
        )
        .bind(sovereign_id.to_string())
        .fetch_one(&pool)
        .await
        .expect("query prediction");

        assert!(
            (risk.0 - 0.2).abs() < 0.01,
            "risk_score should be 0.5 * 0.4 = 0.2 (decayed confidence at 7 days)"
        );
    }

    #[tokio::test]
    async fn test_decay_below_floor_is_skipped() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let _sov_node = insert_sovereign_node(&pool, sovereign_id).await;

        // Insert chain signal with last_seen_at = 40 days ago, confidence = 0.8
        // Decayed: 0.8 * 0.5^(40/7) ≈ 0.0283, which is < 0.05 (floor)
        let forty_days_ago = Utc::now() - Duration::from_secs(40 * 24 * 3600);
        let node_id = Uuid::new_v4();
        let props = json!({
            "sovereign_id": sovereign_id.to_string(),
            "chain_type": "dispute_spam→timeout_spam",
            "chain_length": 2,
            "start_anomaly_type": "dispute_spam",
            "end_anomaly_type": "timeout_spam",
            "occurrence_count": 1,
            "avg_elapsed_hours": 2.5,
            "confidence": 0.8,
            "last_seen_at": forty_days_ago.to_rfc3339(),
            "evidence": {},
        });

        sqlx::query(
            "INSERT INTO graph_entities (id, label, properties, graph_id) VALUES ($1, 'AnomalyChainNode', $2, 0)",
        )
        .bind(node_id)
        .bind(props)
        .execute(&pool)
        .await
        .expect("insert chain node");

        // Run forecast
        let count = run_forecast_once(&pool).await.expect("run forecast");

        // Should NOT create any predictions because signal is below floor
        assert_eq!(
            count, 0,
            "Should not create prediction; signal below 0.05 floor"
        );

        // Verify no PredictionNode was created
        let pred_count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities WHERE label = 'PredictionNode' AND properties->>'sovereign_id' = $1",
        )
        .bind(sovereign_id.to_string())
        .fetch_one(&pool)
        .await
        .expect("query count");

        assert_eq!(
            pred_count.0, 0,
            "No PredictionNode should exist for sovereign"
        );
    }

    #[tokio::test]
    async fn test_forecast_with_decayed_signals_lowers_risk() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let _sov_node = insert_sovereign_node(&pool, sovereign_id).await;

        // Insert fresh chain signal (confidence 0.6, last_seen_at = now)
        let now = Utc::now();
        let chain_id = Uuid::new_v4();
        let chain_props = json!({
            "sovereign_id": sovereign_id.to_string(),
            "chain_type": "dispute_spam→timeout_spam",
            "chain_length": 2,
            "start_anomaly_type": "dispute_spam",
            "end_anomaly_type": "timeout_spam",
            "occurrence_count": 1,
            "avg_elapsed_hours": 2.5,
            "confidence": 0.6,
            "last_seen_at": now.to_rfc3339(),
            "evidence": {},
        });

        sqlx::query(
            "INSERT INTO graph_entities (id, label, properties, graph_id) VALUES ($1, 'AnomalyChainNode', $2, 0)",
        )
        .bind(chain_id)
        .bind(chain_props)
        .execute(&pool)
        .await
        .expect("insert chain node");

        // Insert correlation signal at 14 days ago (confidence 0.5)
        // Decayed: 0.5 * 0.5^(14/7) = 0.5 * 0.25 = 0.125
        let fourteen_days_ago = Utc::now() - Duration::from_secs(14 * 24 * 3600);
        let corr_id = Uuid::new_v4();
        let corr_props = json!({
            "sovereign_id": sovereign_id.to_string(),
            "event_type": "some_event",
            "anomaly_type": "timeout_spam",
            "co_occurrence_count": 5,
            "confidence": 0.5,
            "last_seen_at": fourteen_days_ago.to_rfc3339(),
            "evidence": {},
        });

        sqlx::query(
            "INSERT INTO graph_entities (id, label, properties, graph_id) VALUES ($1, 'CorrelationPatternNode', $2, 0)",
        )
        .bind(corr_id)
        .bind(corr_props)
        .execute(&pool)
        .await
        .expect("insert correlation node");

        // Run forecast
        let count = run_forecast_once(&pool).await.expect("run forecast");

        assert!(count > 0, "Should create at least one prediction");

        // Risk score: 0.5*0.6 + 0.3*0.125 + 0.2*0 = 0.3375
        let risk: (f64,) = sqlx::query_as(
            "SELECT (properties->>'risk_score')::float FROM graph_entities WHERE label = 'PredictionNode' AND properties->>'sovereign_id' = $1",
        )
        .bind(sovereign_id.to_string())
        .fetch_one(&pool)
        .await
        .expect("query prediction");

        assert!(
            (risk.0 - 0.3375).abs() < 0.01,
            "risk_score should be 0.5*0.6 + 0.3*0.125 = 0.3375"
        );
    }

    #[tokio::test]
    async fn test_accuracy_weight_reduces_risk_when_low_precision() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let _sov_node = insert_sovereign_node(&pool, sovereign_id).await;

        // Create a chain signal with confidence 1.0 (would give raw_risk = 0.5)
        insert_anomaly_chain_node(&pool, sovereign_id, "dispute_spam→timeout_spam", 1.0).await;

        // Create AccuracyMetricsNode with precision 0.3, sample_count 10
        // Expected: accuracy_weight = min(1.0, 0.3/0.5) = 0.6
        // Expected final risk_score = 0.5 * 0.6 = 0.3
        insert_accuracy_metrics_node(&pool, sovereign_id, "timeout_spam", Some(0.3), 10).await;

        run_forecast_once(&pool).await.expect("forecast failed");

        let prediction = sqlx::query(
            "SELECT properties FROM graph_entities WHERE label = 'PredictionNode' AND (properties->>'sovereign_id')::uuid = $1"
        )
        .bind(sovereign_id)
        .fetch_one(&pool)
        .await
        .expect("No prediction found");

        let props = prediction.get::<serde_json::Value, _>(0);
        let risk_score: f64 = props["risk_score"].as_f64().unwrap();
        let signal_breakdown = &props["signal_breakdown"];
        let accuracy_weight: f64 = signal_breakdown["accuracy_weight"].as_f64().unwrap();
        let raw_risk_score: f64 = signal_breakdown["raw_risk_score"].as_f64().unwrap();

        // Assertions
        assert!(
            (raw_risk_score - 0.5).abs() < 0.01,
            "raw_risk_score should be 0.5"
        );
        assert!(
            (accuracy_weight - 0.6).abs() < 0.001,
            "accuracy_weight should be 0.6"
        );
        assert!(
            (risk_score - 0.3).abs() < 0.01,
            "risk_score should be 0.3 (0.5 * 0.6)"
        );
    }

    #[tokio::test]
    async fn test_accuracy_weight_no_reduction_at_precision_threshold() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let _sov_node = insert_sovereign_node(&pool, sovereign_id).await;

        insert_anomaly_chain_node(&pool, sovereign_id, "dispute_spam→timeout_spam", 1.0).await;

        // Precision = 0.5 (threshold)
        // Expected: accuracy_weight = min(1.0, 0.5/0.5) = 1.0
        // Expected final risk_score = 0.5 * 1.0 = 0.5 (no change)
        insert_accuracy_metrics_node(&pool, sovereign_id, "timeout_spam", Some(0.5), 10).await;

        run_forecast_once(&pool).await.expect("forecast failed");

        let prediction = sqlx::query(
            "SELECT properties FROM graph_entities WHERE label = 'PredictionNode' AND (properties->>'sovereign_id')::uuid = $1"
        )
        .bind(sovereign_id)
        .fetch_one(&pool)
        .await
        .expect("No prediction found");

        let props = prediction.get::<serde_json::Value, _>(0);
        let risk_score: f64 = props["risk_score"].as_f64().unwrap();
        let signal_breakdown = &props["signal_breakdown"];
        let accuracy_weight: f64 = signal_breakdown["accuracy_weight"].as_f64().unwrap();
        let raw_risk_score: f64 = signal_breakdown["raw_risk_score"].as_f64().unwrap();

        assert!(
            (raw_risk_score - 0.5).abs() < 0.01,
            "raw_risk_score should be 0.5"
        );
        assert!(
            (accuracy_weight - 1.0).abs() < 0.001,
            "accuracy_weight should be 1.0 at threshold"
        );
        assert!(
            (risk_score - 0.5).abs() < 0.01,
            "risk_score should be 0.5 (no change at threshold)"
        );
    }

    #[tokio::test]
    async fn test_accuracy_weight_no_amplification_above_threshold() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let _sov_node = insert_sovereign_node(&pool, sovereign_id).await;

        insert_anomaly_chain_node(&pool, sovereign_id, "dispute_spam→timeout_spam", 1.0).await;

        // Precision = 0.8 (above threshold)
        // Expected: accuracy_weight = min(1.0, 0.8/0.5) = min(1.0, 1.6) = 1.0 (capped)
        // Expected final risk_score = 0.5 * 1.0 = 0.5 (no amplification)
        insert_accuracy_metrics_node(&pool, sovereign_id, "timeout_spam", Some(0.8), 10).await;

        run_forecast_once(&pool).await.expect("forecast failed");

        let prediction = sqlx::query(
            "SELECT properties FROM graph_entities WHERE label = 'PredictionNode' AND (properties->>'sovereign_id')::uuid = $1"
        )
        .bind(sovereign_id)
        .fetch_one(&pool)
        .await
        .expect("No prediction found");

        let props = prediction.get::<serde_json::Value, _>(0);
        let risk_score: f64 = props["risk_score"].as_f64().unwrap();
        let signal_breakdown = &props["signal_breakdown"];
        let accuracy_weight: f64 = signal_breakdown["accuracy_weight"].as_f64().unwrap();

        assert!(
            (accuracy_weight - 1.0).abs() < 0.001,
            "accuracy_weight should be 1.0 (capped)"
        );
        assert!(
            (risk_score - 0.5).abs() < 0.01,
            "risk_score should be 0.5 (no amplification)"
        );
    }

    #[tokio::test]
    async fn test_accuracy_weight_defaults_to_one_when_no_metrics_node() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let _sov_node = insert_sovereign_node(&pool, sovereign_id).await;

        insert_anomaly_chain_node(&pool, sovereign_id, "dispute_spam→timeout_spam", 1.0).await;

        // NO AccuracyMetricsNode inserted
        // Expected: accuracy_weight = 1.0 (default)
        // Expected final risk_score = 0.5 * 1.0 = 0.5

        run_forecast_once(&pool).await.expect("forecast failed");

        let prediction = sqlx::query(
            "SELECT properties FROM graph_entities WHERE label = 'PredictionNode' AND (properties->>'sovereign_id')::uuid = $1"
        )
        .bind(sovereign_id)
        .fetch_one(&pool)
        .await
        .expect("No prediction found");

        let props = prediction.get::<serde_json::Value, _>(0);
        let risk_score: f64 = props["risk_score"].as_f64().unwrap();
        let signal_breakdown = &props["signal_breakdown"];
        let accuracy_weight: f64 = signal_breakdown["accuracy_weight"].as_f64().unwrap();
        let accuracy_sample_count = &signal_breakdown["accuracy_sample_count"];

        assert!((risk_score - 0.5).abs() < 0.01, "risk_score should be 0.5");
        assert!(
            (accuracy_weight - 1.0).abs() < 0.001,
            "accuracy_weight should be 1.0"
        );
        assert!(
            accuracy_sample_count.is_null(),
            "accuracy_sample_count should be null when no metrics node"
        );
    }

    #[tokio::test]
    async fn test_accuracy_weight_defaults_to_one_when_sample_count_below_five() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let _sov_node = insert_sovereign_node(&pool, sovereign_id).await;

        insert_anomaly_chain_node(&pool, sovereign_id, "dispute_spam→timeout_spam", 1.0).await;

        // AccuracyMetricsNode with precision 0.1 (would give weight 0.2), but sample_count = 3
        // Expected: accuracy_weight = 1.0 (insufficient samples, no penalty applied)
        // Expected final risk_score = 0.5 * 1.0 = 0.5
        insert_accuracy_metrics_node(&pool, sovereign_id, "timeout_spam", Some(0.1), 3).await;

        run_forecast_once(&pool).await.expect("forecast failed");

        let prediction = sqlx::query(
            "SELECT properties FROM graph_entities WHERE label = 'PredictionNode' AND (properties->>'sovereign_id')::uuid = $1"
        )
        .bind(sovereign_id)
        .fetch_one(&pool)
        .await
        .expect("No prediction found");

        let props = prediction.get::<serde_json::Value, _>(0);
        let risk_score: f64 = props["risk_score"].as_f64().unwrap();
        let signal_breakdown = &props["signal_breakdown"];
        let accuracy_weight: f64 = signal_breakdown["accuracy_weight"].as_f64().unwrap();
        let accuracy_sample_count: i64 =
            signal_breakdown["accuracy_sample_count"].as_i64().unwrap();

        assert!(
            (risk_score - 0.5).abs() < 0.01,
            "risk_score should be 0.5 (no penalty for low sample count)"
        );
        assert!(
            (accuracy_weight - 1.0).abs() < 0.001,
            "accuracy_weight should be 1.0 (insufficient samples)"
        );
        assert_eq!(
            accuracy_sample_count, 3,
            "accuracy_sample_count should record the actual count (3)"
        );
    }
}
