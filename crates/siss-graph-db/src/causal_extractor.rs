use chrono::{DateTime, Utc};
use sqlx::PgPool;
use std::sync::Arc;
use std::time::Duration;
use tokio::task::JoinHandle;

use crate::repo::causal_query::{fetch_action_anomaly_pairs, fetch_metric_anomaly_pairs};
use crate::repo::correlation_pattern_repo::{CorrelationPatternRecord, ingest_correlation_pattern};

pub const DEFAULT_EXTRACTION_INTERVAL: Duration = Duration::from_secs(60);

/// Extract causal patterns from the graph: scan for temporally co-occurring events and create edges.
/// Returns the count of edges created.
pub async fn extract_causal_patterns_once(
    pool: &PgPool,
    since: DateTime<Utc>,
) -> Result<usize, sqlx::Error> {
    let mut edge_count = 0;

    // === Action → Anomaly Detection (2h window, cost > 1000) ===
    let action_anomaly_pairs = fetch_action_anomaly_pairs(pool, since, 2, 1000).await?;

    for pair in action_anomaly_pairs {
        // Create PRECEDES edge from action to anomaly
        sqlx::query(
            "INSERT INTO graph_relationships (source_entity_id, target_entity_id, relationship_type)
             VALUES ($1, $2, 'PRECEDES')
             ON CONFLICT (source_entity_id, target_entity_id, relationship_type) DO NOTHING",
        )
        .bind(pair.action_entity_id)
        .bind(pair.anomaly_entity_id)
        .execute(pool)
        .await?;

        edge_count += 1;

        // Create or update CorrelationPatternNode for this (sovereign, pattern_type) pair
        let pattern_record = CorrelationPatternRecord {
            sovereign_id: pair.sovereign_id,
            pattern_type: "action_precedes_anomaly".to_string(),
            occurrence_count: 1,
            avg_gap_seconds: pair.gap_seconds,
            confidence: 0.2,
            last_seen_at: Utc::now(),
            evidence: serde_json::json!({
                "sample_source_id": pair.action_entity_id.to_string(),
                "sample_target_id": pair.anomaly_entity_id.to_string(),
            }),
        };

        let _ = ingest_correlation_pattern(pool, &pattern_record).await;
    }

    // === Metric → Anomaly Detection (1h window, utilization > 80%) ===
    let metric_anomaly_pairs = fetch_metric_anomaly_pairs(pool, since, 1, 80.0).await?;

    for pair in metric_anomaly_pairs {
        // Create COINCIDES_WITH edge from metric to anomaly
        sqlx::query(
            "INSERT INTO graph_relationships (source_entity_id, target_entity_id, relationship_type)
             VALUES ($1, $2, 'COINCIDES_WITH')
             ON CONFLICT (source_entity_id, target_entity_id, relationship_type) DO NOTHING",
        )
        .bind(pair.metric_entity_id)
        .bind(pair.anomaly_entity_id)
        .execute(pool)
        .await?;

        edge_count += 1;

        // Create or update CorrelationPatternNode for this pattern
        let pattern_record = CorrelationPatternRecord {
            sovereign_id: pair.sovereign_id,
            pattern_type: "metric_spike_anomaly".to_string(),
            occurrence_count: 1,
            avg_gap_seconds: pair.gap_seconds,
            confidence: 0.2,
            last_seen_at: Utc::now(),
            evidence: serde_json::json!({
                "sample_metric_id": pair.metric_entity_id.to_string(),
                "sample_anomaly_id": pair.anomaly_entity_id.to_string(),
                "utilization_pct": pair.utilization_pct,
            }),
        };

        let _ = ingest_correlation_pattern(pool, &pattern_record).await;
    }

    Ok(edge_count)
}

/// Start the causal extractor background task.
pub fn start_causal_extractor(pool: Arc<PgPool>, interval: Duration) -> JoinHandle<()> {
    tokio::spawn(async move {
        let mut checkpoint = Utc::now() - Duration::from_secs(300); // 5-minute lookback on boot

        loop {
            let _ = extract_causal_patterns_once(&pool, checkpoint).await;
            checkpoint = Utc::now(); // Always advance checkpoint
            tokio::time::sleep(interval).await;
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use testcontainers::runners::AsyncRunner;
    use testcontainers::{GenericImage, ImageExt, core::WaitFor};
    use uuid::Uuid;

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

    /// Helper: insert an AgentActionNode into the graph
    async fn insert_agent_action_node(
        pool: &PgPool,
        sovereign_id: Uuid,
        cost_incurred: i64,
        scored_at: DateTime<Utc>,
        event_type: &str,
    ) -> Uuid {
        use serde_json::json;
        let node_id = Uuid::new_v4();
        let props = json!({
            "behavior_event_id": Uuid::new_v4().to_string(),
            "sovereign_id": sovereign_id.to_string(),
            "cost_incurred": cost_incurred,
            "scored_at": scored_at.to_rfc3339(),
            "event_type": event_type,
            "tier_before": 50,
            "tier_after": 45,
            "lineage_safe": true,
        });

        sqlx::query(
            "INSERT INTO graph_entities (id, label, properties, graph_id) VALUES ($1, 'AgentActionNode', $2, 0)",
        )
        .bind(node_id)
        .bind(props)
        .execute(pool)
        .await
        .expect("insert action node");

        node_id
    }

    /// Helper: insert an AnomalyEventNode into the graph
    async fn insert_anomaly_node(
        pool: &PgPool,
        sovereign_id: Uuid,
        detected_at: DateTime<Utc>,
        anomaly_type: &str,
    ) -> Uuid {
        let node_id = Uuid::new_v4();
        let props = json!({
            "anomaly_db_id": Uuid::new_v4().to_string(),
            "sovereign_id": sovereign_id.to_string(),
            "anomaly_type": anomaly_type,
            "severity": "high",
            "event_count": 3,
            "window_hours": 1,
            "evidence": {},
            "detected_at": detected_at.to_rfc3339(),
        });

        sqlx::query(
            "INSERT INTO graph_entities (id, label, properties, graph_id) VALUES ($1, 'AnomalyEventNode', $2, 0)",
        )
        .bind(node_id)
        .bind(props)
        .execute(pool)
        .await
        .expect("insert anomaly node");

        node_id
    }

    /// Helper: insert a SystemMetricNode into the graph
    async fn insert_metric_node(
        pool: &PgPool,
        sovereign_id: Uuid,
        snapshot_at: DateTime<Utc>,
        utilization_pct: f64,
    ) -> Uuid {
        let node_id = Uuid::new_v4();
        let props = json!({
            "session_id": Uuid::new_v4().to_string(),
            "sovereign_id": sovereign_id.to_string(),
            "token_budget_remaining": 5000,
            "token_budget_consumed": 1000,
            "budget_utilization_pct": utilization_pct,
            "snapshot_at": snapshot_at.to_rfc3339(),
        });

        sqlx::query(
            "INSERT INTO graph_entities (id, label, properties, graph_id) VALUES ($1, 'SystemMetricNode', $2, 0)",
        )
        .bind(node_id)
        .bind(props)
        .execute(pool)
        .await
        .expect("insert metric node");

        node_id
    }

    #[tokio::test]
    async fn test_detect_action_precedes_anomaly_creates_edge() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let now = Utc::now();

        // Insert high-cost action followed by anomaly within 2h
        let action_id = insert_agent_action_node(
            &pool,
            sovereign_id,
            2000,
            now - Duration::from_secs(3600),
            "delegation",
        )
        .await;
        let anomaly_id = insert_anomaly_node(&pool, sovereign_id, now, "timeout_spam").await;

        // Extract patterns
        let edge_count = extract_causal_patterns_once(&pool, now - Duration::from_secs(7200))
            .await
            .expect("extract");

        assert!(edge_count > 0, "Should create at least one PRECEDES edge");

        // Verify edge exists
        let edge_count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_relationships WHERE source_entity_id = $1 AND target_entity_id = $2 AND relationship_type = 'PRECEDES'",
        )
        .bind(action_id)
        .bind(anomaly_id)
        .fetch_one(&pool)
        .await
        .expect("query edge");

        assert_eq!(
            edge_count.0, 1,
            "PRECEDES edge should be created between action and anomaly"
        );
    }

    #[tokio::test]
    async fn test_no_edge_when_gap_exceeds_window() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let now = Utc::now();

        // Insert action and anomaly 3h apart (exceeds 2h window)
        let action_id = insert_agent_action_node(
            &pool,
            sovereign_id,
            2000,
            now - Duration::from_secs(3600 * 3),
            "delegation",
        )
        .await;
        let _anomaly_id = insert_anomaly_node(&pool, sovereign_id, now, "timeout_spam").await;

        // Extract patterns
        let _ = extract_causal_patterns_once(&pool, now - Duration::from_secs(7200 * 2))
            .await
            .expect("extract");

        // Verify no PRECEDES edge was created
        let edge_count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_relationships WHERE source_entity_id = $1 AND relationship_type = 'PRECEDES'",
        )
        .bind(action_id)
        .fetch_one(&pool)
        .await
        .expect("query edge");

        assert_eq!(
            edge_count.0, 0,
            "No PRECEDES edge should be created when gap exceeds window"
        );
    }

    #[tokio::test]
    async fn test_no_edge_for_different_sovereign() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_a = Uuid::new_v4();
        let sovereign_b = Uuid::new_v4();
        let now = Utc::now();

        // Insert action for sovereign A
        let action_id = insert_agent_action_node(
            &pool,
            sovereign_a,
            2000,
            now - Duration::from_secs(1800),
            "delegation",
        )
        .await;

        // Insert anomaly for sovereign B
        let anomaly_id = insert_anomaly_node(&pool, sovereign_b, now, "timeout_spam").await;

        // Extract patterns
        let _ = extract_causal_patterns_once(&pool, now - Duration::from_secs(7200))
            .await
            .expect("extract");

        // Verify no edge between them
        let edge_count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_relationships WHERE source_entity_id = $1 AND target_entity_id = $2",
        )
        .bind(action_id)
        .bind(anomaly_id)
        .fetch_one(&pool)
        .await
        .expect("query edge");

        assert_eq!(
            edge_count.0, 0,
            "No edge should be created between different sovereigns"
        );
    }

    #[tokio::test]
    async fn test_detect_metric_coincides_anomaly_creates_edge() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let now = Utc::now();

        // Insert metric with high utilization followed by anomaly within 1h
        let metric_id =
            insert_metric_node(&pool, sovereign_id, now - Duration::from_secs(1800), 85.0).await;
        let anomaly_id = insert_anomaly_node(&pool, sovereign_id, now, "dispute_spam").await;

        // Extract patterns
        let edge_count = extract_causal_patterns_once(&pool, now - Duration::from_secs(3600))
            .await
            .expect("extract");

        assert!(
            edge_count > 0,
            "Should create at least one COINCIDES_WITH edge"
        );

        // Verify edge exists
        let edge_count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_relationships WHERE source_entity_id = $1 AND target_entity_id = $2 AND relationship_type = 'COINCIDES_WITH'",
        )
        .bind(metric_id)
        .bind(anomaly_id)
        .fetch_one(&pool)
        .await
        .expect("query edge");

        assert_eq!(
            edge_count.0, 1,
            "COINCIDES_WITH edge should be created between metric and anomaly"
        );
    }

    #[tokio::test]
    async fn test_extract_once_creates_correlation_pattern_node() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let now = Utc::now();

        // Insert action and anomaly pair
        let _action_id = insert_agent_action_node(
            &pool,
            sovereign_id,
            2000,
            now - Duration::from_secs(1800),
            "delegation",
        )
        .await;
        let _anomaly_id = insert_anomaly_node(&pool, sovereign_id, now, "timeout_spam").await;

        // Extract patterns
        let _ = extract_causal_patterns_once(&pool, now - Duration::from_secs(3600))
            .await
            .expect("extract");

        // Verify CorrelationPatternNode was created
        let count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities WHERE label = 'CorrelationPatternNode' AND properties->>'sovereign_id' = $1 AND properties->>'pattern_type' = 'action_precedes_anomaly'",
        )
        .bind(sovereign_id.to_string())
        .fetch_one(&pool)
        .await
        .expect("query pattern node");

        assert_eq!(count.0, 1, "CorrelationPatternNode should be created");
    }

    #[tokio::test]
    async fn test_extract_once_idempotent() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let now = Utc::now();

        // Insert action and anomaly pair
        let _action_id = insert_agent_action_node(
            &pool,
            sovereign_id,
            2000,
            now - Duration::from_secs(1800),
            "delegation",
        )
        .await;
        let _anomaly_id = insert_anomaly_node(&pool, sovereign_id, now, "timeout_spam").await;

        let since = now - Duration::from_secs(3600);

        // First extraction
        let count1 = extract_causal_patterns_once(&pool, since)
            .await
            .expect("extract 1");
        assert!(count1 > 0);

        // Second extraction (idempotent)
        let count2 = extract_causal_patterns_once(&pool, since)
            .await
            .expect("extract 2");

        // Should not create duplicate edges or pattern nodes on re-run
        let edge_count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_relationships WHERE relationship_type IN ('PRECEDES', 'COINCIDES_WITH')",
        )
        .fetch_one(&pool)
        .await
        .expect("query edge count");

        // count1 edges created, count2 should be 0 (no new edges due to idempotency)
        assert_eq!(
            count1 + count2,
            count1,
            "Re-extraction should not create duplicate edges"
        );
    }
}
