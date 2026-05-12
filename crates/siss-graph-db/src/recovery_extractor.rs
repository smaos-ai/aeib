use chrono::{DateTime, Utc};
use sqlx::PgPool;
use std::sync::Arc;
use std::time::Duration;
use tokio::task::JoinHandle;

use crate::repo::recovery_preceded_repo::{RecoveryCorrelationRecord, ingest_recovery_correlation};
use crate::repo::recovery_query::fetch_anomaly_recovery_pairs;

pub const DEFAULT_RECOVERY_EXTRACTION_INTERVAL: Duration = Duration::from_secs(60);

/// Extract recovery correlations from the graph: scan for anomalies preceding recovery entries.
/// Returns the count of PRECEDED_RECOVERY edges created.
pub async fn extract_recovery_preceded_once(
    pool: &PgPool,
    since: DateTime<Utc>,
) -> Result<usize, sqlx::Error> {
    let mut edge_count = 0;

    // === Anomaly → Recovery Detection (24h window, any anomaly type) ===
    let anomaly_recovery_pairs = fetch_anomaly_recovery_pairs(pool, since, 24).await?;

    for pair in anomaly_recovery_pairs {
        // Create PRECEDED_RECOVERY edge from anomaly to recovery
        sqlx::query(
            "INSERT INTO graph_relationships (source_entity_id, target_entity_id, relationship_type)
             VALUES ($1, $2, 'PRECEDED_RECOVERY')
             ON CONFLICT (source_entity_id, target_entity_id, relationship_type) DO NOTHING",
        )
        .bind(pair.anomaly_entity_id)
        .bind(pair.recovery_entity_id)
        .execute(pool)
        .await?;

        edge_count += 1;

        // Create or update RecoveryCorrelationNode for this (sovereign, anomaly_type) pair
        let correlation_record = RecoveryCorrelationRecord {
            sovereign_id: pair.sovereign_id,
            anomaly_type: pair.anomaly_type,
            occurrence_count: 1,
            avg_gap_hours: pair.gap_hours,
            confidence: 0.2,
            last_seen_at: Utc::now(),
            evidence: serde_json::json!({
                "anomaly_id": pair.anomaly_entity_id.to_string(),
                "recovery_id": pair.recovery_entity_id.to_string(),
            }),
        };

        let _ = ingest_recovery_correlation(pool, &correlation_record).await;
    }

    Ok(edge_count)
}

/// Start the recovery correlation extractor background task.
pub fn start_recovery_extractor(pool: Arc<PgPool>, interval: Duration) -> JoinHandle<()> {
    tokio::spawn(async move {
        let mut checkpoint = Utc::now() - Duration::from_secs(300); // 5-minute lookback on boot

        loop {
            let _ = extract_recovery_preceded_once(&pool, checkpoint).await;
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

    /// Helper: insert a RecoveryNode with DEPENDS_ON edge to SovereignNode
    async fn insert_recovery_node(
        pool: &PgPool,
        sovereign_id: Uuid,
        recovery_timestamp: DateTime<Utc>,
        event_type: &str,
    ) -> Uuid {
        // Insert SovereignNode
        let sov_node_id = Uuid::new_v4();
        let sov_props = json!({
            "sovereign_id": sovereign_id.to_string(),
            "created_at": Utc::now().to_rfc3339(),
        });
        sqlx::query(
            "INSERT INTO graph_entities (id, label, properties, graph_id) VALUES ($1, 'SovereignNode', $2, 0)",
        )
        .bind(sov_node_id)
        .bind(sov_props)
        .execute(pool)
        .await
        .expect("insert sovereign node");

        // Insert RecoveryNode
        let recovery_node_id = Uuid::new_v4();
        let recovery_props = json!({
            "event_type": event_type,
            "weeks_elapsed": 4,
            "timestamp": recovery_timestamp.to_rfc3339(),
            "evidence": {},
        });
        sqlx::query(
            "INSERT INTO graph_entities (id, label, properties, graph_id) VALUES ($1, 'RecoveryNode', $2, 0)",
        )
        .bind(recovery_node_id)
        .bind(recovery_props)
        .execute(pool)
        .await
        .expect("insert recovery node");

        // Insert DEPENDS_ON edge
        sqlx::query(
            "INSERT INTO graph_relationships (source_entity_id, target_entity_id, relationship_type) VALUES ($1, $2, 'DEPENDS_ON')",
        )
        .bind(recovery_node_id)
        .bind(sov_node_id)
        .execute(pool)
        .await
        .expect("insert DEPENDS_ON edge");

        recovery_node_id
    }

    #[tokio::test]
    async fn test_anomaly_precedes_recovery_creates_edge() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let now = Utc::now();

        // Insert anomaly 1h before recovery
        let anomaly_id = insert_anomaly_node(
            &pool,
            sovereign_id,
            now - Duration::from_secs(3600),
            "dispute_spam",
        )
        .await;
        let recovery_id =
            insert_recovery_node(&pool, sovereign_id, now, "probation_to_recovery").await;

        // Extract correlations
        let edge_count = extract_recovery_preceded_once(&pool, now - Duration::from_secs(7200))
            .await
            .expect("extract");

        assert!(
            edge_count > 0,
            "Should create at least one PRECEDED_RECOVERY edge"
        );

        // Verify edge exists
        let edge_result: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_relationships WHERE source_entity_id = $1 AND target_entity_id = $2 AND relationship_type = 'PRECEDED_RECOVERY'",
        )
        .bind(anomaly_id)
        .bind(recovery_id)
        .fetch_one(&pool)
        .await
        .expect("query edge");

        assert_eq!(
            edge_result.0, 1,
            "PRECEDED_RECOVERY edge should be created between anomaly and recovery"
        );
    }

    #[tokio::test]
    async fn test_no_edge_when_gap_exceeds_window() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let now = Utc::now();

        // Insert anomaly 25h before recovery (exceeds 24h window)
        let anomaly_id = insert_anomaly_node(
            &pool,
            sovereign_id,
            now - Duration::from_secs(3600 * 25),
            "dispute_spam",
        )
        .await;
        let _recovery_id =
            insert_recovery_node(&pool, sovereign_id, now, "probation_to_recovery").await;

        // Extract correlations
        let _ = extract_recovery_preceded_once(&pool, now - Duration::from_secs(3600 * 26))
            .await
            .expect("extract");

        // Verify no PRECEDED_RECOVERY edge was created
        let edge_result: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_relationships WHERE source_entity_id = $1 AND relationship_type = 'PRECEDED_RECOVERY'",
        )
        .bind(anomaly_id)
        .fetch_one(&pool)
        .await
        .expect("query edge");

        assert_eq!(
            edge_result.0, 0,
            "No PRECEDED_RECOVERY edge should be created when gap exceeds 24h window"
        );
    }

    #[tokio::test]
    async fn test_no_edge_for_different_sovereign() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_a = Uuid::new_v4();
        let sovereign_b = Uuid::new_v4();
        let now = Utc::now();

        // Insert anomaly for sovereign A
        let anomaly_id = insert_anomaly_node(
            &pool,
            sovereign_a,
            now - Duration::from_secs(3600),
            "dispute_spam",
        )
        .await;

        // Insert recovery for sovereign B
        let recovery_id =
            insert_recovery_node(&pool, sovereign_b, now, "probation_to_recovery").await;

        // Extract correlations
        let _ = extract_recovery_preceded_once(&pool, now - Duration::from_secs(7200))
            .await
            .expect("extract");

        // Verify no edge between them
        let edge_result: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_relationships WHERE source_entity_id = $1 AND target_entity_id = $2",
        )
        .bind(anomaly_id)
        .bind(recovery_id)
        .fetch_one(&pool)
        .await
        .expect("query edge");

        assert_eq!(
            edge_result.0, 0,
            "No edge should be created between different sovereigns"
        );
    }

    #[tokio::test]
    async fn test_no_edge_when_recovery_precedes_anomaly() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let now = Utc::now();

        // Insert recovery 1h before anomaly (wrong temporal direction)
        let anomaly_id = insert_anomaly_node(&pool, sovereign_id, now, "dispute_spam").await;
        let _recovery_id = insert_recovery_node(
            &pool,
            sovereign_id,
            now - Duration::from_secs(3600),
            "probation_to_recovery",
        )
        .await;

        // Extract correlations
        let _ = extract_recovery_preceded_once(&pool, now - Duration::from_secs(7200))
            .await
            .expect("extract");

        // Verify no PRECEDED_RECOVERY edge was created
        let edge_result: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_relationships WHERE source_entity_id = $1 AND relationship_type = 'PRECEDED_RECOVERY'",
        )
        .bind(anomaly_id)
        .fetch_one(&pool)
        .await
        .expect("query edge");

        assert_eq!(
            edge_result.0, 0,
            "No edge should be created when recovery precedes anomaly"
        );
    }

    #[tokio::test]
    async fn test_extract_recovery_once_creates_correlation_node() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let now = Utc::now();

        // Insert anomaly and recovery pair
        let _anomaly_id = insert_anomaly_node(
            &pool,
            sovereign_id,
            now - Duration::from_secs(3600),
            "dispute_spam",
        )
        .await;
        let _recovery_id =
            insert_recovery_node(&pool, sovereign_id, now, "probation_to_recovery").await;

        // Extract correlations
        let _ = extract_recovery_preceded_once(&pool, now - Duration::from_secs(7200))
            .await
            .expect("extract");

        // Verify RecoveryCorrelationNode was created
        let correlation_result: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities WHERE label = 'RecoveryCorrelationNode' AND properties->>'sovereign_id' = $1 AND properties->>'anomaly_type' = 'dispute_spam'",
        )
        .bind(sovereign_id.to_string())
        .fetch_one(&pool)
        .await
        .expect("query correlation node");

        assert_eq!(
            correlation_result.0, 1,
            "RecoveryCorrelationNode should be created with correct anomaly_type"
        );
    }

    #[tokio::test]
    async fn test_extract_recovery_idempotent() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let now = Utc::now();

        // Insert anomaly and recovery pair
        let _anomaly_id = insert_anomaly_node(
            &pool,
            sovereign_id,
            now - Duration::from_secs(3600),
            "dispute_spam",
        )
        .await;
        let _recovery_id =
            insert_recovery_node(&pool, sovereign_id, now, "probation_to_recovery").await;

        let since = now - Duration::from_secs(7200);

        // First extraction
        let count1 = extract_recovery_preceded_once(&pool, since)
            .await
            .expect("extract 1");
        assert!(count1 > 0);

        // Second extraction (idempotent)
        let count2 = extract_recovery_preceded_once(&pool, since)
            .await
            .expect("extract 2");

        // Should not create duplicate edges on re-run
        let edge_result: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_relationships WHERE relationship_type = 'PRECEDED_RECOVERY'",
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
