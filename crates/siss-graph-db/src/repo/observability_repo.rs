use chrono::{DateTime, Utc};
use sqlx::PgPool;
use uuid::Uuid;

use super::feedback_recorder::{AnomalyEvent, record_feedback_for_anomaly};

// ============================================================================
// Ingestion Record Types
// ============================================================================

/// Represents a behavioral action ingested from behavior_events table.
#[derive(Debug, Clone)]
pub struct AgentActionIngestionRecord {
    pub behavior_event_id: Uuid,
    pub session_id: Uuid,
    pub persona_id: Uuid,
    pub sovereign_id: Uuid,
    pub event_type: String,
    pub tier_before: i16,
    pub tier_after: i16,
    pub cost_incurred: i64,
    pub lineage_safe: bool,
    pub scored_at: DateTime<Utc>,
}

/// Represents an anomaly ingested from behavioral_anomalies table.
#[derive(Debug, Clone)]
pub struct AnomalyIngestionRecord {
    pub anomaly_db_id: Uuid,
    pub sovereign_id: Uuid,
    pub anomaly_type: String,
    pub severity: String,
    pub event_count: i64,
    pub window_hours: i64,
    pub evidence: serde_json::Value,
    pub detected_at: DateTime<Utc>,
}

/// Represents a system metric snapshot for token budget health.
#[derive(Debug, Clone)]
pub struct SystemMetricIngestionRecord {
    pub session_id: Uuid,
    pub sovereign_id: Uuid,
    pub token_budget_remaining: i64,
    pub token_budget_consumed: i64,
    pub budget_utilization_pct: f64,
    pub snapshot_at: DateTime<Utc>,
}

// ============================================================================
// Ingestion Functions
// ============================================================================

/// Ingest an agent action into the intelligence graph.
/// Upserts AgentActionNode by behavior_event_id, creates EMITTED_BY edge to sovereign.
pub async fn ingest_agent_action(
    pool: &PgPool,
    record: &AgentActionIngestionRecord,
) -> Result<Uuid, sqlx::Error> {
    let properties = serde_json::json!({
        "behavior_event_id": record.behavior_event_id.to_string(),
        "session_id": record.session_id.to_string(),
        "persona_id": record.persona_id.to_string(),
        "sovereign_id": record.sovereign_id.to_string(),
        "event_type": record.event_type,
        "tier_before": record.tier_before,
        "tier_after": record.tier_after,
        "cost_incurred": record.cost_incurred,
        "lineage_safe": record.lineage_safe,
        "scored_at": record.scored_at.to_rfc3339(),
    });

    // Upsert AgentActionNode
    let node_id: Uuid = sqlx::query_scalar(
        "INSERT INTO graph_entities (label, properties, graph_id)
         VALUES ('AgentActionNode', $1, 0)
         ON CONFLICT ((properties->>'behavior_event_id'))
         WHERE label = 'AgentActionNode'
         DO UPDATE SET properties = EXCLUDED.properties, updated_at = NOW()
         RETURNING id",
    )
    .bind(&properties)
    .fetch_one(pool)
    .await?;

    // Get or create sovereign node
    let sovereign_node_id =
        super::intelligence_graph_repo::get_or_create_sovereign_node(pool, record.sovereign_id)
            .await?;

    // Upsert EMITTED_BY edge
    sqlx::query(
        "INSERT INTO graph_relationships (source_entity_id, target_entity_id, relationship_type)
         VALUES ($1, $2, 'EMITTED_BY')
         ON CONFLICT DO NOTHING",
    )
    .bind(node_id)
    .bind(sovereign_node_id)
    .execute(pool)
    .await?;

    Ok(node_id)
}

/// Ingest an anomaly event into the intelligence graph.
/// Upserts AnomalyEventNode by anomaly_db_id, creates DETECTED_IN edge to sovereign.
pub async fn ingest_anomaly_event(
    pool: &PgPool,
    record: &AnomalyIngestionRecord,
) -> Result<Uuid, sqlx::Error> {
    let properties = serde_json::json!({
        "anomaly_db_id": record.anomaly_db_id.to_string(),
        "sovereign_id": record.sovereign_id.to_string(),
        "anomaly_type": record.anomaly_type,
        "severity": record.severity,
        "event_count": record.event_count,
        "window_hours": record.window_hours,
        "evidence": record.evidence,
        "detected_at": record.detected_at.to_rfc3339(),
    });

    // Upsert AnomalyEventNode
    let node_id: Uuid = sqlx::query_scalar(
        "INSERT INTO graph_entities (label, properties, graph_id)
         VALUES ('AnomalyEventNode', $1, 0)
         ON CONFLICT ((properties->>'anomaly_db_id'))
         WHERE label = 'AnomalyEventNode'
         DO UPDATE SET properties = EXCLUDED.properties, updated_at = NOW()
         RETURNING id",
    )
    .bind(&properties)
    .fetch_one(pool)
    .await?;

    // Get or create sovereign node
    let sovereign_node_id =
        super::intelligence_graph_repo::get_or_create_sovereign_node(pool, record.sovereign_id)
            .await?;

    // Upsert DETECTED_IN edge
    sqlx::query(
        "INSERT INTO graph_relationships (source_entity_id, target_entity_id, relationship_type)
         VALUES ($1, $2, 'DETECTED_IN')
         ON CONFLICT DO NOTHING",
    )
    .bind(node_id)
    .bind(sovereign_node_id)
    .execute(pool)
    .await?;

    // Record feedback for anomaly (non-blocking; failures are ignored)
    let anomaly = AnomalyEvent {
        sovereign_id: record.sovereign_id,
        anomaly_type: record.anomaly_type.clone(),
        detected_at: record.detected_at,
    };
    let _ = record_feedback_for_anomaly(pool, &anomaly).await;

    Ok(node_id)
}

/// Ingest a system metric into the intelligence graph.
/// Upserts SystemMetricNode by (session_id, snapshot_at), creates EMITTED_BY edge to sovereign.
pub async fn ingest_system_metric(
    pool: &PgPool,
    record: &SystemMetricIngestionRecord,
) -> Result<Uuid, sqlx::Error> {
    let properties = serde_json::json!({
        "session_id": record.session_id.to_string(),
        "sovereign_id": record.sovereign_id.to_string(),
        "token_budget_remaining": record.token_budget_remaining,
        "token_budget_consumed": record.token_budget_consumed,
        "budget_utilization_pct": record.budget_utilization_pct,
        "snapshot_at": record.snapshot_at.to_rfc3339(),
    });

    // Upsert SystemMetricNode
    let node_id: Uuid = sqlx::query_scalar(
        "INSERT INTO graph_entities (label, properties, graph_id)
         VALUES ('SystemMetricNode', $1, 0)
         ON CONFLICT ((properties->>'session_id'), (properties->>'snapshot_at'))
         WHERE label = 'SystemMetricNode'
         DO UPDATE SET properties = EXCLUDED.properties, updated_at = NOW()
         RETURNING id",
    )
    .bind(&properties)
    .fetch_one(pool)
    .await?;

    // Get or create sovereign node
    let sovereign_node_id =
        super::intelligence_graph_repo::get_or_create_sovereign_node(pool, record.sovereign_id)
            .await?;

    // Upsert EMITTED_BY edge
    sqlx::query(
        "INSERT INTO graph_relationships (source_entity_id, target_entity_id, relationship_type)
         VALUES ($1, $2, 'EMITTED_BY')
         ON CONFLICT DO NOTHING",
    )
    .bind(node_id)
    .bind(sovereign_node_id)
    .execute(pool)
    .await?;

    Ok(node_id)
}

/// Fetch all agent actions for a given session.
pub async fn fetch_agent_actions_for_session(
    _pool: &PgPool,
    _session_id: Uuid,
) -> Result<Vec<serde_json::Value>, sqlx::Error> {
    todo!()
}

/// Fetch all anomaly events for a given sovereign.
pub async fn fetch_anomaly_events_for_sovereign(
    _pool: &PgPool,
    _sovereign_id: Uuid,
) -> Result<Vec<serde_json::Value>, sqlx::Error> {
    todo!()
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;
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
        let pool = PgPool::connect(&url).await.expect("pool connect");
        crate::migrations::run_all(&pool).await.expect("migrations");
        (container, pool)
    }

    #[tokio::test]
    async fn test_ingest_agent_action_creates_graph_entity() {
        let (_container, pool) = setup_postgres().await;

        let sovereign_id = Uuid::new_v4();
        let record = AgentActionIngestionRecord {
            behavior_event_id: Uuid::new_v4(),
            session_id: Uuid::new_v4(),
            persona_id: Uuid::new_v4(),
            sovereign_id,
            event_type: "refresh_success".to_string(),
            tier_before: 1,
            tier_after: 2,
            cost_incurred: 500,
            lineage_safe: true,
            scored_at: Utc::now(),
        };

        let node_id = ingest_agent_action(&pool, &record).await.expect("ingest");

        let row: (String, String) = sqlx::query_as(
            "SELECT label, properties->>'behavior_event_id' FROM graph_entities WHERE id = $1",
        )
        .bind(node_id)
        .fetch_one(&pool)
        .await
        .expect("fetch");

        assert_eq!(row.0, "AgentActionNode");
        assert_eq!(row.1, record.behavior_event_id.to_string());
    }

    #[tokio::test]
    async fn test_ingest_agent_action_creates_emitted_by_edge() {
        let (_container, pool) = setup_postgres().await;

        let sovereign_id = Uuid::new_v4();
        let record = AgentActionIngestionRecord {
            behavior_event_id: Uuid::new_v4(),
            session_id: Uuid::new_v4(),
            persona_id: Uuid::new_v4(),
            sovereign_id,
            event_type: "delegation_created".to_string(),
            tier_before: 2,
            tier_after: 2,
            cost_incurred: 1000,
            lineage_safe: true,
            scored_at: Utc::now(),
        };

        let node_id = ingest_agent_action(&pool, &record).await.expect("ingest");

        let count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_relationships WHERE source_entity_id = $1 AND relationship_type = 'EMITTED_BY'"
        )
        .bind(node_id)
        .fetch_one(&pool)
        .await
        .expect("fetch");

        assert_eq!(count.0, 1, "Should have exactly one EMITTED_BY edge");
    }

    #[tokio::test]
    async fn test_ingest_agent_action_is_idempotent() {
        let (_container, pool) = setup_postgres().await;

        let sovereign_id = Uuid::new_v4();
        let behavior_event_id = Uuid::new_v4();
        let record = AgentActionIngestionRecord {
            behavior_event_id,
            session_id: Uuid::new_v4(),
            persona_id: Uuid::new_v4(),
            sovereign_id,
            event_type: "refresh_success".to_string(),
            tier_before: 1,
            tier_after: 2,
            cost_incurred: 500,
            lineage_safe: true,
            scored_at: Utc::now(),
        };

        let _ = ingest_agent_action(&pool, &record)
            .await
            .expect("first ingest");
        let _ = ingest_agent_action(&pool, &record)
            .await
            .expect("second ingest");

        let count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities WHERE label = 'AgentActionNode' AND properties->>'behavior_event_id' = $1"
        )
        .bind(behavior_event_id.to_string())
        .fetch_one(&pool)
        .await
        .expect("fetch");

        assert_eq!(count.0, 1, "Should have exactly one AgentActionNode");
    }

    #[tokio::test]
    async fn test_ingest_agent_action_returns_same_uuid_on_repeat() {
        let (_container, pool) = setup_postgres().await;

        let sovereign_id = Uuid::new_v4();
        let record = AgentActionIngestionRecord {
            behavior_event_id: Uuid::new_v4(),
            session_id: Uuid::new_v4(),
            persona_id: Uuid::new_v4(),
            sovereign_id,
            event_type: "refresh_success".to_string(),
            tier_before: 1,
            tier_after: 2,
            cost_incurred: 500,
            lineage_safe: true,
            scored_at: Utc::now(),
        };

        let node_id_1 = ingest_agent_action(&pool, &record)
            .await
            .expect("first ingest");
        let node_id_2 = ingest_agent_action(&pool, &record)
            .await
            .expect("second ingest");

        assert_eq!(node_id_1, node_id_2, "Should return same node ID");
    }

    #[tokio::test]
    async fn test_ingest_anomaly_event_creates_graph_entity() {
        let (_container, pool) = setup_postgres().await;

        let record = AnomalyIngestionRecord {
            anomaly_db_id: Uuid::new_v4(),
            sovereign_id: Uuid::new_v4(),
            anomaly_type: "dispute_spam".to_string(),
            severity: "high".to_string(),
            event_count: 5,
            window_hours: 1,
            evidence: serde_json::json!({ "disputes": 5 }),
            detected_at: Utc::now(),
        };

        let node_id = ingest_anomaly_event(&pool, &record).await.expect("ingest");

        let row: (String, String) = sqlx::query_as(
            "SELECT label, properties->>'anomaly_db_id' FROM graph_entities WHERE id = $1",
        )
        .bind(node_id)
        .fetch_one(&pool)
        .await
        .expect("fetch");

        assert_eq!(row.0, "AnomalyEventNode");
        assert_eq!(row.1, record.anomaly_db_id.to_string());
    }

    #[tokio::test]
    async fn test_ingest_anomaly_event_creates_detected_in_edge() {
        let (_container, pool) = setup_postgres().await;

        let record = AnomalyIngestionRecord {
            anomaly_db_id: Uuid::new_v4(),
            sovereign_id: Uuid::new_v4(),
            anomaly_type: "timeout_spam".to_string(),
            severity: "medium".to_string(),
            event_count: 3,
            window_hours: 2,
            evidence: serde_json::json!({ "timeouts": 3 }),
            detected_at: Utc::now(),
        };

        let node_id = ingest_anomaly_event(&pool, &record).await.expect("ingest");

        let count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_relationships WHERE source_entity_id = $1 AND relationship_type = 'DETECTED_IN'"
        )
        .bind(node_id)
        .fetch_one(&pool)
        .await
        .expect("fetch");

        assert_eq!(count.0, 1, "Should have exactly one DETECTED_IN edge");
    }

    #[tokio::test]
    async fn test_ingest_anomaly_event_is_idempotent() {
        let (_container, pool) = setup_postgres().await;

        let anomaly_db_id = Uuid::new_v4();
        let record = AnomalyIngestionRecord {
            anomaly_db_id,
            sovereign_id: Uuid::new_v4(),
            anomaly_type: "revocation_pattern".to_string(),
            severity: "critical".to_string(),
            event_count: 10,
            window_hours: 24,
            evidence: serde_json::json!({ "revocations": 10 }),
            detected_at: Utc::now(),
        };

        let _ = ingest_anomaly_event(&pool, &record)
            .await
            .expect("first ingest");
        let _ = ingest_anomaly_event(&pool, &record)
            .await
            .expect("second ingest");

        let count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities WHERE label = 'AnomalyEventNode' AND properties->>'anomaly_db_id' = $1"
        )
        .bind(anomaly_db_id.to_string())
        .fetch_one(&pool)
        .await
        .expect("fetch");

        assert_eq!(count.0, 1, "Should have exactly one AnomalyEventNode");
    }

    #[tokio::test]
    async fn test_ingest_system_metric_creates_entity_and_edge() {
        let (_container, pool) = setup_postgres().await;

        let record = SystemMetricIngestionRecord {
            session_id: Uuid::new_v4(),
            sovereign_id: Uuid::new_v4(),
            token_budget_remaining: 50000,
            token_budget_consumed: 10000,
            budget_utilization_pct: 16.67,
            snapshot_at: Utc::now(),
        };

        let node_id = ingest_system_metric(&pool, &record).await.expect("ingest");

        let row: (String,) = sqlx::query_as("SELECT label FROM graph_entities WHERE id = $1")
            .bind(node_id)
            .fetch_one(&pool)
            .await
            .expect("fetch");

        assert_eq!(row.0, "SystemMetricNode");

        let edge_count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_relationships WHERE source_entity_id = $1 AND relationship_type = 'EMITTED_BY'"
        )
        .bind(node_id)
        .fetch_one(&pool)
        .await
        .expect("fetch");

        assert_eq!(edge_count.0, 1, "Should have exactly one EMITTED_BY edge");
    }

    #[tokio::test]
    async fn test_ingest_system_metric_idempotent_on_same_snapshot() {
        let (_container, pool) = setup_postgres().await;

        let session_id = Uuid::new_v4();
        let snapshot_at = Utc::now();
        let record = SystemMetricIngestionRecord {
            session_id,
            sovereign_id: Uuid::new_v4(),
            token_budget_remaining: 50000,
            token_budget_consumed: 10000,
            budget_utilization_pct: 16.67,
            snapshot_at,
        };

        let _ = ingest_system_metric(&pool, &record)
            .await
            .expect("first ingest");
        let _ = ingest_system_metric(&pool, &record)
            .await
            .expect("second ingest");

        let count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities WHERE label = 'SystemMetricNode' AND properties->>'session_id' = $1 AND properties->>'snapshot_at' = $2"
        )
        .bind(session_id.to_string())
        .bind(snapshot_at.to_rfc3339())
        .fetch_one(&pool)
        .await
        .expect("fetch");

        assert_eq!(
            count.0, 1,
            "Should have exactly one SystemMetricNode per snapshot"
        );
    }

    #[tokio::test]
    async fn test_ingest_anomaly_event_triggers_feedback_recording() {
        let (_container, pool) = setup_postgres().await;

        let sovereign_id = Uuid::new_v4();
        let now = Utc::now();

        // Create a prediction first for feedback to match against
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

        // Ingest an anomaly event that matches the prediction
        let record = AnomalyIngestionRecord {
            anomaly_db_id: Uuid::new_v4(),
            sovereign_id,
            anomaly_type: "timeout_spam".to_string(),
            severity: "medium".to_string(),
            event_count: 3,
            window_hours: 2,
            evidence: serde_json::json!({ "timeouts": 3 }),
            detected_at: now + chrono::Duration::hours(1),
        };

        let anomaly_node_id = ingest_anomaly_event(&pool, &record)
            .await
            .expect("ingest anomaly");

        // Verify AnomalyEventNode was created
        let anomaly_count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities WHERE id = $1 AND label = 'AnomalyEventNode'",
        )
        .bind(anomaly_node_id)
        .fetch_one(&pool)
        .await
        .expect("fetch");
        assert_eq!(anomaly_count.0, 1, "AnomalyEventNode should exist");

        // Verify FeedbackNode was created by feedback_recording flow
        let feedback_count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities WHERE label = 'FeedbackNode' AND properties->>'sovereign_id' = $1",
        )
        .bind(sovereign_id.to_string())
        .fetch_one(&pool)
        .await
        .expect("fetch");
        assert_eq!(feedback_count.0, 1, "FeedbackNode should be created by feedback recording");

        // Verify FEEDBACK_FOR edge was created
        let edge_count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_relationships WHERE relationship_type = 'FEEDBACK_FOR'",
        )
        .fetch_one(&pool)
        .await
        .expect("fetch");
        assert!(edge_count.0 > 0, "FEEDBACK_FOR edge should exist");
    }
}
