use chrono::{DateTime, Utc};
use sqlx::PgPool;
use std::sync::Arc;
use std::time::Duration;
use tokio::task::JoinHandle;

use crate::repo::anomaly_chain_repo::{AnomalyChainRecord, ingest_anomaly_chain};
use crate::repo::chain_query::fetch_anomaly_chain_pairs;

pub const DEFAULT_CHAIN_EXTRACTION_INTERVAL: Duration = Duration::from_secs(60);

/// Extract anomaly chains from the graph: scan for consecutive anomalies and create edges.
/// Returns the count of LEADS_TO edges created.
pub async fn extract_anomaly_chains_once(
    pool: &PgPool,
    since: DateTime<Utc>,
) -> Result<usize, sqlx::Error> {
    let mut edge_count = 0;

    // === Anomaly → Anomaly Detection (4h window, different types) ===
    let anomaly_pairs = fetch_anomaly_chain_pairs(pool, since, 4).await?;

    for pair in anomaly_pairs {
        // Create LEADS_TO edge from first anomaly to second anomaly
        sqlx::query(
            "INSERT INTO graph_relationships (source_entity_id, target_entity_id, relationship_type)
             VALUES ($1, $2, 'LEADS_TO')
             ON CONFLICT (source_entity_id, target_entity_id, relationship_type) DO NOTHING",
        )
        .bind(pair.first_anomaly_id)
        .bind(pair.second_anomaly_id)
        .execute(pool)
        .await?;

        edge_count += 1;

        // Create or update AnomalyChainNode for this (sovereign, chain_type) pair
        let chain_type = format!("{}→{}", pair.first_type, pair.second_type);
        let chain_record = AnomalyChainRecord {
            sovereign_id: pair.sovereign_id,
            chain_type,
            chain_length: 2,
            start_anomaly_type: pair.first_type,
            end_anomaly_type: pair.second_type,
            occurrence_count: 1,
            avg_elapsed_hours: pair.elapsed_hours,
            confidence: 0.2,
            last_seen_at: Utc::now(),
            evidence: serde_json::json!({
                "first_id": pair.first_anomaly_id.to_string(),
                "second_id": pair.second_anomaly_id.to_string(),
            }),
        };

        let _ = ingest_anomaly_chain(pool, &chain_record).await;
    }

    Ok(edge_count)
}

/// Start the anomaly chain extractor background task.
pub fn start_chain_extractor(pool: Arc<PgPool>, interval: Duration) -> JoinHandle<()> {
    tokio::spawn(async move {
        let mut checkpoint = Utc::now() - Duration::from_secs(300); // 5-minute lookback on boot

        loop {
            let _ = extract_anomaly_chains_once(&pool, checkpoint).await;
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

    #[tokio::test]
    async fn test_detect_anomaly_leads_to_anomaly_creates_edge() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let now = Utc::now();

        // Insert two anomalies: different types, same sovereign, within 4h
        let anomaly1_id = insert_anomaly_node(
            &pool,
            sovereign_id,
            now - Duration::from_secs(3600),
            "dispute_spam",
        )
        .await;
        let anomaly2_id = insert_anomaly_node(&pool, sovereign_id, now, "timeout_spam").await;

        // Extract chains
        let edge_count = extract_anomaly_chains_once(&pool, now - Duration::from_secs(7200))
            .await
            .expect("extract");

        assert!(edge_count > 0, "Should create at least one LEADS_TO edge");

        // Verify edge exists
        let edge_result: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_relationships WHERE source_entity_id = $1 AND target_entity_id = $2 AND relationship_type = 'LEADS_TO'",
        )
        .bind(anomaly1_id)
        .bind(anomaly2_id)
        .fetch_one(&pool)
        .await
        .expect("query edge");

        assert_eq!(
            edge_result.0, 1,
            "LEADS_TO edge should be created between anomalies"
        );
    }

    #[tokio::test]
    async fn test_no_edge_when_gap_exceeds_window() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let now = Utc::now();

        // Insert two anomalies 5h apart (exceeds 4h window)
        let anomaly1_id = insert_anomaly_node(
            &pool,
            sovereign_id,
            now - Duration::from_secs(3600 * 5),
            "dispute_spam",
        )
        .await;
        let _anomaly2_id = insert_anomaly_node(&pool, sovereign_id, now, "timeout_spam").await;

        // Extract chains
        let _ = extract_anomaly_chains_once(&pool, now - Duration::from_secs(3600 * 6))
            .await
            .expect("extract");

        // Verify no LEADS_TO edge was created
        let edge_result: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_relationships WHERE source_entity_id = $1 AND relationship_type = 'LEADS_TO'",
        )
        .bind(anomaly1_id)
        .fetch_one(&pool)
        .await
        .expect("query edge");

        assert_eq!(
            edge_result.0, 0,
            "No LEADS_TO edge should be created when gap exceeds 4h window"
        );
    }

    #[tokio::test]
    async fn test_no_edge_for_same_anomaly_type() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let now = Utc::now();

        // Insert two anomalies of the same type (should be skipped)
        let anomaly1_id = insert_anomaly_node(
            &pool,
            sovereign_id,
            now - Duration::from_secs(1800),
            "dispute_spam",
        )
        .await;
        let _anomaly2_id = insert_anomaly_node(&pool, sovereign_id, now, "dispute_spam").await;

        // Extract chains
        let _ = extract_anomaly_chains_once(&pool, now - Duration::from_secs(3600))
            .await
            .expect("extract");

        // Verify no LEADS_TO edge was created
        let edge_result: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_relationships WHERE source_entity_id = $1 AND relationship_type = 'LEADS_TO'",
        )
        .bind(anomaly1_id)
        .fetch_one(&pool)
        .await
        .expect("query edge");

        assert_eq!(
            edge_result.0, 0,
            "No LEADS_TO edge should be created for same anomaly type"
        );
    }

    #[tokio::test]
    async fn test_no_edge_for_different_sovereign() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_a = Uuid::new_v4();
        let sovereign_b = Uuid::new_v4();
        let now = Utc::now();

        // Insert anomalies for different sovereigns
        let anomaly1_id = insert_anomaly_node(
            &pool,
            sovereign_a,
            now - Duration::from_secs(1800),
            "dispute_spam",
        )
        .await;
        let anomaly2_id = insert_anomaly_node(&pool, sovereign_b, now, "timeout_spam").await;

        // Extract chains
        let _ = extract_anomaly_chains_once(&pool, now - Duration::from_secs(3600))
            .await
            .expect("extract");

        // Verify no edge between them
        let edge_result: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_relationships WHERE source_entity_id = $1 AND target_entity_id = $2",
        )
        .bind(anomaly1_id)
        .bind(anomaly2_id)
        .fetch_one(&pool)
        .await
        .expect("query edge");

        assert_eq!(
            edge_result.0, 0,
            "No edge should be created between different sovereigns"
        );
    }

    #[tokio::test]
    async fn test_extract_chains_once_creates_chain_node() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let now = Utc::now();

        // Insert two anomalies
        let _anomaly1_id = insert_anomaly_node(
            &pool,
            sovereign_id,
            now - Duration::from_secs(1800),
            "dispute_spam",
        )
        .await;
        let _anomaly2_id = insert_anomaly_node(&pool, sovereign_id, now, "timeout_spam").await;

        // Extract chains
        let _ = extract_anomaly_chains_once(&pool, now - Duration::from_secs(3600))
            .await
            .expect("extract");

        // Verify AnomalyChainNode was created
        let chain_result: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities WHERE label = 'AnomalyChainNode' AND properties->>'sovereign_id' = $1 AND properties->>'chain_type' = 'dispute_spam→timeout_spam'",
        )
        .bind(sovereign_id.to_string())
        .fetch_one(&pool)
        .await
        .expect("query chain node");

        assert_eq!(
            chain_result.0, 1,
            "AnomalyChainNode should be created with correct chain_type"
        );
    }

    #[tokio::test]
    async fn test_extract_chains_idempotent() {
        let (_container, pool) = setup_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let now = Utc::now();

        // Insert two anomalies
        let _anomaly1_id = insert_anomaly_node(
            &pool,
            sovereign_id,
            now - Duration::from_secs(1800),
            "dispute_spam",
        )
        .await;
        let _anomaly2_id = insert_anomaly_node(&pool, sovereign_id, now, "timeout_spam").await;

        let since = now - Duration::from_secs(3600);

        // First extraction
        let count1 = extract_anomaly_chains_once(&pool, since)
            .await
            .expect("extract 1");
        assert!(count1 > 0);

        // Second extraction (idempotent)
        let count2 = extract_anomaly_chains_once(&pool, since)
            .await
            .expect("extract 2");

        // Should not create duplicate edges on re-run
        let edge_result: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_relationships WHERE relationship_type = 'LEADS_TO'",
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
