use chrono::{DateTime, Utc};
use sqlx::PgPool;
use std::sync::Arc;
use std::time::Duration;
use tokio::task::JoinHandle;
use uuid::Uuid;

use crate::repo::observability_repo::{
    AgentActionIngestionRecord, AnomalyIngestionRecord, ingest_agent_action, ingest_anomaly_event,
};

pub const DEFAULT_POLL_INTERVAL: Duration = Duration::from_secs(30);
pub const BOOT_LOOKBACK: Duration = Duration::from_secs(300);

/// Poll behavior_events and anomalies periodically, ingesting them into the intelligence graph.
/// Runs indefinitely on a background task.
pub fn start_observability_watcher(pool: Arc<PgPool>, poll_interval: Duration) -> JoinHandle<()> {
    tokio::spawn(async move {
        let mut checkpoint = Utc::now() - BOOT_LOOKBACK;

        loop {
            let before_poll = checkpoint;

            if let Ok(records) = poll_behavior_events_once(&pool, checkpoint).await {
                for record in records {
                    let _ = ingest_agent_action(&pool, &record).await;
                    checkpoint = checkpoint.max(record.scored_at);
                }
            }

            if let Ok(records) = poll_anomalies_once(&pool, checkpoint).await {
                for record in records {
                    let _ = ingest_anomaly_event(&pool, &record).await;
                    checkpoint = checkpoint.max(record.detected_at);
                }
            }

            if checkpoint == before_poll {
                checkpoint = Utc::now();
            }

            tokio::time::sleep(poll_interval).await;
        }
    })
}

/// Poll behavior_events since a checkpoint and convert to AgentActionIngestionRecord.
/// Returns records where origin_sovereign_id is not null.
pub(crate) async fn poll_behavior_events_once(
    pool: &PgPool,
    since: DateTime<Utc>,
) -> Result<Vec<AgentActionIngestionRecord>, sqlx::Error> {
    #[derive(sqlx::FromRow)]
    struct Row {
        id: Uuid,
        session_id: Uuid,
        active_persona_id: Option<Uuid>,
        origin_sovereign_id: Option<Uuid>,
        event_type: String,
        tier_before: i16,
        tier_after: i16,
        cost_incurred: i64,
        lineage_safe: bool,
        scored_at: DateTime<Utc>,
    }

    let rows = sqlx::query_as::<_, Row>(
        r#"
        SELECT be.id, be.session_id, s.active_persona_id, s.origin_sovereign_id,
               be.event_type, be.tier_before, be.tier_after, be.cost_incurred,
               be.lineage_safe, be.scored_at
        FROM behavior_events be
        JOIN sessions s ON s.id = be.session_id
        WHERE be.scored_at > $1
          AND s.origin_sovereign_id IS NOT NULL
        ORDER BY be.scored_at ASC
        LIMIT 500
        "#,
    )
    .bind(since)
    .fetch_all(pool)
    .await?;

    let records = rows
        .into_iter()
        .map(|row| AgentActionIngestionRecord {
            behavior_event_id: row.id,
            session_id: row.session_id,
            persona_id: row.active_persona_id.unwrap_or_else(Uuid::nil),
            sovereign_id: row.origin_sovereign_id.unwrap(),
            event_type: row.event_type,
            tier_before: row.tier_before,
            tier_after: row.tier_after,
            cost_incurred: row.cost_incurred,
            lineage_safe: row.lineage_safe,
            scored_at: row.scored_at,
        })
        .collect();

    Ok(records)
}

/// Poll behavioral_anomalies since a checkpoint and convert to AnomalyIngestionRecord.
pub(crate) async fn poll_anomalies_once(
    pool: &PgPool,
    since: DateTime<Utc>,
) -> Result<Vec<AnomalyIngestionRecord>, sqlx::Error> {
    #[derive(sqlx::FromRow)]
    struct Row {
        id: Uuid,
        sovereign_id: Uuid,
        anomaly_type: String,
        severity: String,
        event_count: i64,
        window_hours: i64,
        evidence: Option<serde_json::Value>,
        detected_at: DateTime<Utc>,
    }

    let rows = sqlx::query_as::<_, Row>(
        r#"
        SELECT ba.id, ba.sovereign_id, ba.anomaly_type, ba.severity,
               ba.event_count, ba.window_hours, ba.evidence, ba.detected_at
        FROM behavioral_anomalies ba
        WHERE ba.detected_at > $1
        ORDER BY ba.detected_at ASC
        LIMIT 500
        "#,
    )
    .bind(since)
    .fetch_all(pool)
    .await?;

    let records = rows
        .into_iter()
        .map(|row| AnomalyIngestionRecord {
            anomaly_db_id: row.id,
            sovereign_id: row.sovereign_id,
            anomaly_type: row.anomaly_type,
            severity: row.severity,
            event_count: row.event_count,
            window_hours: row.window_hours,
            evidence: row.evidence.unwrap_or_else(|| serde_json::json!({})),
            detected_at: row.detected_at,
        })
        .collect();

    Ok(records)
}

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
    async fn test_poll_behavior_events_once_ingests_new_row() {
        let (_container, pool) = setup_postgres().await;

        // Create tenant and persona
        let tenant_id = crate::repo::node_repo::insert_tenant(&pool, "TestCorp")
            .await
            .expect("insert tenant");
        let persona_id =
            crate::repo::node_repo::insert_persona(&pool, "TestAgent", "ai_agent", tenant_id)
                .await
                .expect("insert persona");

        // Create sovereign
        let sovereign_id = Uuid::new_v4();
        sqlx::query(
            "INSERT INTO sovereigns (id, name, public_key_pem, status) VALUES ($1, $2, $3, $4)",
        )
        .bind(sovereign_id)
        .bind("TestSovereign")
        .bind("-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----")
        .bind("active")
        .execute(&pool)
        .await
        .expect("insert sovereign");

        // Create session with origin_sovereign_id
        let session_id = Uuid::new_v4();
        sqlx::query(
            "INSERT INTO sessions (id, tenant_id, active_persona_id, token_budget, origin_sovereign_id)
             VALUES ($1, $2, $3, $4, $5)"
        )
        .bind(session_id)
        .bind(tenant_id)
        .bind(persona_id)
        .bind(100_000i64)
        .bind(sovereign_id)
        .execute(&pool)
        .await
        .expect("insert session");

        // Insert a behavior event
        let behavior_event_id = Uuid::new_v4();
        let scored_at = Utc::now();
        sqlx::query(
            "INSERT INTO behavior_events (id, session_id, event_type, tier_before, tier_after, tier_delta, cost_incurred, lineage_safe, scored_at)
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)"
        )
        .bind(behavior_event_id)
        .bind(session_id)
        .bind("refresh_success")
        .bind(1i16)
        .bind(2i16)
        .bind(1i16)
        .bind(500i64)
        .bind(true)
        .bind(scored_at)
        .execute(&pool)
        .await
        .expect("insert behavior_event");

        // Poll for events and ingest
        let checkpoint = scored_at - Duration::from_secs(1);
        let records = poll_behavior_events_once(&pool, checkpoint)
            .await
            .expect("poll");

        assert_eq!(records.len(), 1);
        assert_eq!(records[0].behavior_event_id, behavior_event_id);
        assert_eq!(records[0].sovereign_id, sovereign_id);

        // Ingest the record
        let node_id = ingest_agent_action(&pool, &records[0])
            .await
            .expect("ingest");

        // Verify AgentActionNode was created
        let count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities WHERE id = $1 AND label = 'AgentActionNode'",
        )
        .bind(node_id)
        .fetch_one(&pool)
        .await
        .expect("fetch");

        assert_eq!(count.0, 1);
    }

    #[tokio::test]
    async fn test_poll_skips_sessions_without_sovereign_id() {
        let (_container, pool) = setup_postgres().await;

        // Create tenant and persona (no sovereign)
        let tenant_id = crate::repo::node_repo::insert_tenant(&pool, "TestCorp2")
            .await
            .expect("insert tenant");
        let persona_id =
            crate::repo::node_repo::insert_persona(&pool, "TestAgent2", "ai_agent", tenant_id)
                .await
                .expect("insert persona");

        // Create session WITHOUT origin_sovereign_id
        let session_id = Uuid::new_v4();
        sqlx::query(
            "INSERT INTO sessions (id, tenant_id, active_persona_id, token_budget, origin_sovereign_id)
             VALUES ($1, $2, $3, $4, NULL)"
        )
        .bind(session_id)
        .bind(tenant_id)
        .bind(persona_id)
        .bind(100_000i64)
        .execute(&pool)
        .await
        .expect("insert session");

        // Insert a behavior event for this session
        let behavior_event_id = Uuid::new_v4();
        let scored_at = Utc::now();
        sqlx::query(
            "INSERT INTO behavior_events (id, session_id, event_type, tier_before, tier_after, tier_delta, cost_incurred, lineage_safe, scored_at)
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)"
        )
        .bind(behavior_event_id)
        .bind(session_id)
        .bind("delegation_created")
        .bind(2i16)
        .bind(2i16)
        .bind(0i16)
        .bind(1000i64)
        .bind(true)
        .bind(scored_at)
        .execute(&pool)
        .await
        .expect("insert behavior_event");

        // Poll for events
        let checkpoint = scored_at - Duration::from_secs(1);
        let records = poll_behavior_events_once(&pool, checkpoint)
            .await
            .expect("poll");

        // Should skip this record because session has no sovereign_id
        assert_eq!(records.len(), 0);
    }
}
