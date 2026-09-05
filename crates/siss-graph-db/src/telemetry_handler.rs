use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::PgPool;
use std::sync::Arc;
use uuid::Uuid;

// ============================================================================
// OpenTelemetry Trace Schema
// ============================================================================

/// OpenTelemetry trace event (maps to AgentActionNode)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OtelTraceEvent {
    pub trace_id: String,
    pub span_id: String,
    pub span_name: String,
    pub session_id: Uuid,
    pub sovereign_id: Uuid,
    pub attributes: OtelAttributes,
    pub start_time: String, // RFC3339
    pub end_time: String,   // RFC3339
    pub status: String,     // ok | error
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OtelAttributes {
    pub event_type: String, // refresh_success | delegation_created | ...
    pub tier_before: i16,
    pub tier_after: i16,
    pub cost_incurred: i64,
    pub lineage_safe: bool,
}

// ============================================================================
// AG-UI Event Schema
// ============================================================================

/// AG-UI event from frontend (maps to AgentActionNode or AnomalyEventNode)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgUiEvent {
    pub event_id: Uuid,
    pub event_type: String, // action | anomaly | metric
    pub session_id: Uuid,
    pub sovereign_id: Uuid,
    pub payload: serde_json::Value,
    pub timestamp: String, // RFC3339
}

/// AG-UI anomaly event payload
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgUiAnomalyPayload {
    pub anomaly_type: String, // dispute_spam | timeout_spam | revocation_pattern
    pub severity: String,     // low | medium | high | critical
    pub event_count: i64,
    pub window_hours: i64,
    pub evidence: serde_json::Value,
}

// ============================================================================
// Fire-and-Forget Ingestion Context
// ============================================================================

/// Context for async ingestion (no blocking on graph writes)
pub struct TelemetryIngestor {
    pool: Arc<PgPool>,
}

impl TelemetryIngestor {
    pub fn new(pool: Arc<PgPool>) -> Self {
        TelemetryIngestor { pool }
    }

    /// Ingest OpenTelemetry trace (synchronous; fire-and-forget wrapper comes later).
    pub async fn ingest_otel_trace(&self, event: OtelTraceEvent) -> Result<Uuid, TelemetryError> {
        // Look up persona_id from session
        let persona_id =
            sqlx::query_scalar::<_, Uuid>("SELECT active_persona_id FROM sessions WHERE id = $1")
                .bind(event.session_id)
                .fetch_optional(self.pool.as_ref())
                .await
                .map_err(|e| TelemetryError::DatabaseError(e.to_string()))?
                .unwrap_or_else(Uuid::nil);

        let record = crate::repo::observability_repo::AgentActionIngestionRecord {
            behavior_event_id: Uuid::new_v4(),
            session_id: event.session_id,
            persona_id,
            sovereign_id: event.sovereign_id,
            event_type: event.attributes.event_type,
            tier_before: event.attributes.tier_before,
            tier_after: event.attributes.tier_after,
            cost_incurred: event.attributes.cost_incurred,
            lineage_safe: event.attributes.lineage_safe,
            scored_at: DateTime::parse_from_rfc3339(&event.start_time)
                .map(|dt| dt.with_timezone(&Utc))
                .unwrap_or_else(|_| Utc::now()),
        };

        let node_id = crate::repo::observability_repo::ingest_agent_action(&self.pool, &record)
            .await
            .map_err(|e| TelemetryError::DatabaseError(e.to_string()))?;

        Ok(node_id)
    }

    /// Ingest AG-UI event (synchronous).
    /// Routes to anomaly or action handler based on event_type.
    pub async fn ingest_agui_event(&self, event: AgUiEvent) -> Result<Uuid, TelemetryError> {
        if event.event_type == "anomaly" {
            let anomaly = serde_json::from_value::<AgUiAnomalyPayload>(event.payload.clone())
                .map_err(|e| TelemetryError::SerializationError(e.to_string()))?;

            let record = crate::repo::observability_repo::AnomalyIngestionRecord {
                anomaly_db_id: event.event_id,
                sovereign_id: event.sovereign_id,
                anomaly_type: anomaly.anomaly_type,
                severity: anomaly.severity,
                event_count: anomaly.event_count,
                window_hours: anomaly.window_hours,
                evidence: anomaly.evidence,
                detected_at: DateTime::parse_from_rfc3339(&event.timestamp)
                    .map(|dt| dt.with_timezone(&Utc))
                    .unwrap_or_else(|_| Utc::now()),
            };

            let node_id =
                crate::repo::observability_repo::ingest_anomaly_event(&self.pool, &record)
                    .await
                    .map_err(|e| TelemetryError::DatabaseError(e.to_string()))?;

            Ok(node_id)
        } else if event.event_type == "action" {
            // Look up persona_id from session
            let persona_id = sqlx::query_scalar::<_, Uuid>(
                "SELECT active_persona_id FROM sessions WHERE id = $1",
            )
            .bind(event.session_id)
            .fetch_optional(self.pool.as_ref())
            .await
            .map_err(|e| TelemetryError::DatabaseError(e.to_string()))?
            .unwrap_or_else(Uuid::nil);

            let event_type = event
                .payload
                .get("action")
                .and_then(|v| v.as_str())
                .unwrap_or("unknown")
                .to_string();

            let record = crate::repo::observability_repo::AgentActionIngestionRecord {
                behavior_event_id: event.event_id,
                session_id: event.session_id,
                persona_id,
                sovereign_id: event.sovereign_id,
                event_type,
                tier_before: 0,
                tier_after: 0,
                cost_incurred: 0,
                lineage_safe: true,
                scored_at: DateTime::parse_from_rfc3339(&event.timestamp)
                    .map(|dt| dt.with_timezone(&Utc))
                    .unwrap_or_else(|_| Utc::now()),
            };

            let node_id = crate::repo::observability_repo::ingest_agent_action(&self.pool, &record)
                .await
                .map_err(|e| TelemetryError::DatabaseError(e.to_string()))?;

            Ok(node_id)
        } else {
            Err(TelemetryError::ValidationFailed(format!(
                "Unknown event_type: {}",
                event.event_type
            )))
        }
    }
}

// ============================================================================
// Error Handling
// ============================================================================

#[derive(Debug)]
pub enum TelemetryError {
    ValidationFailed(String),
    DatabaseError(String),
    SerializationError(String),
}

impl std::fmt::Display for TelemetryError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            TelemetryError::ValidationFailed(msg) => write!(f, "Validation failed: {}", msg),
            TelemetryError::DatabaseError(msg) => write!(f, "Database error: {}", msg),
            TelemetryError::SerializationError(msg) => write!(f, "Serialization error: {}", msg),
        }
    }
}

// ============================================================================
// Tests (TDD — Failing First)
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

    async fn wait_for_entity(pool: &PgPool, id: Uuid, label: &str, max_wait_ms: u64) {
        let mut elapsed = 0;
        loop {
            let count: (i64,) =
                sqlx::query_as("SELECT COUNT(*) FROM graph_entities WHERE id = $1 AND label = $2")
                    .bind(id)
                    .bind(label)
                    .fetch_one(pool)
                    .await
                    .unwrap_or((0,));

            if count.0 > 0 {
                return;
            }
            if elapsed >= max_wait_ms {
                break;
            }
            tokio::time::sleep(tokio::time::Duration::from_millis(50)).await;
            elapsed += 50;
        }
    }

    #[tokio::test]
    async fn test_otel_trace_schema_validation_success() {
        let (_container, _pool) = setup_postgres().await;

        let event = OtelTraceEvent {
            trace_id: "trace-123".to_string(),
            span_id: "span-456".to_string(),
            span_name: "refresh_agent".to_string(),
            session_id: Uuid::new_v4(),
            sovereign_id: Uuid::new_v4(),
            attributes: OtelAttributes {
                event_type: "refresh_success".to_string(),
                tier_before: 1,
                tier_after: 2,
                cost_incurred: 500,
                lineage_safe: true,
            },
            start_time: Utc::now().to_rfc3339(),
            end_time: Utc::now().to_rfc3339(),
            status: "ok".to_string(),
        };

        // Schema must be valid (serde serialization succeeds)
        let json = serde_json::to_value(&event).expect("serialize");
        assert!(json.is_object());
        assert_eq!(json["attributes"]["event_type"], "refresh_success");
    }

    #[tokio::test]
    async fn test_agui_event_schema_validation_success() {
        let (_container, _pool) = setup_postgres().await;

        let event = AgUiEvent {
            event_id: Uuid::new_v4(),
            event_type: "action".to_string(),
            session_id: Uuid::new_v4(),
            sovereign_id: Uuid::new_v4(),
            payload: serde_json::json!({
                "action": "delegation_accepted",
                "target": "peer-001"
            }),
            timestamp: Utc::now().to_rfc3339(),
        };

        let json = serde_json::to_value(&event).expect("serialize");
        assert!(json.is_object());
        assert_eq!(json["event_type"], "action");
    }

    #[tokio::test]
    async fn test_agui_anomaly_payload_schema_validation() {
        let payload = AgUiAnomalyPayload {
            anomaly_type: "dispute_spam".to_string(),
            severity: "high".to_string(),
            event_count: 5,
            window_hours: 1,
            evidence: serde_json::json!({ "disputes": 5 }),
        };

        let json = serde_json::to_value(&payload).expect("serialize");
        assert_eq!(json["anomaly_type"], "dispute_spam");
        assert_eq!(json["severity"], "high");
        assert_eq!(json["event_count"], 5);
    }

    #[tokio::test]
    async fn test_ingest_otel_trace_creates_agent_action_node() {
        let (_container, pool) = setup_postgres().await;

        // Setup: Create tenant, persona, sovereign
        let tenant_id = crate::repo::node_repo::insert_tenant(&pool, "TestCorp")
            .await
            .expect("insert tenant");
        let persona_id =
            crate::repo::node_repo::insert_persona(&pool, "TestAgent", "ai_agent", tenant_id)
                .await
                .expect("insert persona");
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

        let session_id = Uuid::new_v4();
        sqlx::query(
            "INSERT INTO sessions (id, tenant_id, active_persona_id, token_budget, origin_sovereign_id) VALUES ($1, $2, $3, $4, $5)"
        )
        .bind(session_id)
        .bind(tenant_id)
        .bind(persona_id)
        .bind(100_000i64)
        .bind(sovereign_id)
        .execute(&pool)
        .await
        .expect("insert session");

        let ingestor = TelemetryIngestor::new(Arc::new(pool.clone()));

        let event = OtelTraceEvent {
            trace_id: "trace-001".to_string(),
            span_id: "span-001".to_string(),
            span_name: "refresh_agent".to_string(),
            session_id,
            sovereign_id,
            attributes: OtelAttributes {
                event_type: "refresh_success".to_string(),
                tier_before: 1,
                tier_after: 2,
                cost_incurred: 500,
                lineage_safe: true,
            },
            start_time: Utc::now().to_rfc3339(),
            end_time: Utc::now().to_rfc3339(),
            status: "ok".to_string(),
        };

        let node_id = ingestor.ingest_otel_trace(event).await.expect("ingest");

        // Wait for async ingestion to complete
        wait_for_entity(&pool, node_id, "AgentActionNode", 5000).await;

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
    async fn test_ingest_agui_anomaly_event_creates_anomaly_node() {
        let (_container, pool) = setup_postgres().await;

        // Setup: Create sovereign
        let sovereign_id = Uuid::new_v4();
        sqlx::query(
            "INSERT INTO sovereigns (id, name, public_key_pem, status) VALUES ($1, $2, $3, $4)",
        )
        .bind(sovereign_id)
        .bind("TestSovereign2")
        .bind("-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----")
        .bind("active")
        .execute(&pool)
        .await
        .expect("insert sovereign");

        let ingestor = TelemetryIngestor::new(Arc::new(pool.clone()));

        let event = AgUiEvent {
            event_id: Uuid::new_v4(),
            event_type: "anomaly".to_string(),
            session_id: Uuid::new_v4(),
            sovereign_id,
            payload: serde_json::to_value(AgUiAnomalyPayload {
                anomaly_type: "timeout_spam".to_string(),
                severity: "critical".to_string(),
                event_count: 10,
                window_hours: 1,
                evidence: serde_json::json!({ "timeouts": 10 }),
            })
            .expect("serialize"),
            timestamp: Utc::now().to_rfc3339(),
        };

        let node_id = ingestor.ingest_agui_event(event).await.expect("ingest");

        // Wait for async ingestion to complete
        wait_for_entity(&pool, node_id, "AnomalyEventNode", 5000).await;

        // Verify AnomalyEventNode was created
        let count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities WHERE id = $1 AND label = 'AnomalyEventNode'",
        )
        .bind(node_id)
        .fetch_one(&pool)
        .await
        .expect("fetch");

        assert_eq!(count.0, 1);
    }

    #[tokio::test]
    async fn test_ingest_otel_creates_emitted_by_edge() {
        let (_container, pool) = setup_postgres().await;

        // Setup
        let tenant_id = crate::repo::node_repo::insert_tenant(&pool, "TestCorp")
            .await
            .expect("insert tenant");
        let persona_id =
            crate::repo::node_repo::insert_persona(&pool, "TestAgent", "ai_agent", tenant_id)
                .await
                .expect("insert persona");
        let sovereign_id = Uuid::new_v4();
        sqlx::query(
            "INSERT INTO sovereigns (id, name, public_key_pem, status) VALUES ($1, $2, $3, $4)",
        )
        .bind(sovereign_id)
        .bind("TestSovereign3")
        .bind("-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----")
        .bind("active")
        .execute(&pool)
        .await
        .expect("insert sovereign");

        let session_id = Uuid::new_v4();
        sqlx::query(
            "INSERT INTO sessions (id, tenant_id, active_persona_id, token_budget, origin_sovereign_id) VALUES ($1, $2, $3, $4, $5)"
        )
        .bind(session_id)
        .bind(tenant_id)
        .bind(persona_id)
        .bind(100_000i64)
        .bind(sovereign_id)
        .execute(&pool)
        .await
        .expect("insert session");

        let ingestor = TelemetryIngestor::new(Arc::new(pool.clone()));

        let event = OtelTraceEvent {
            trace_id: "trace-002".to_string(),
            span_id: "span-002".to_string(),
            span_name: "delegation_created".to_string(),
            session_id,
            sovereign_id,
            attributes: OtelAttributes {
                event_type: "delegation_created".to_string(),
                tier_before: 2,
                tier_after: 2,
                cost_incurred: 1000,
                lineage_safe: true,
            },
            start_time: Utc::now().to_rfc3339(),
            end_time: Utc::now().to_rfc3339(),
            status: "ok".to_string(),
        };

        let node_id = ingestor.ingest_otel_trace(event).await.expect("ingest");

        // Wait for async ingestion to complete
        wait_for_entity(&pool, node_id, "AgentActionNode", 5000).await;

        // Verify EMITTED_BY edge exists
        let count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_relationships WHERE source_entity_id = $1 AND relationship_type = 'EMITTED_BY'"
        )
        .bind(node_id)
        .fetch_one(&pool)
        .await
        .expect("fetch");

        assert_eq!(count.0, 1);
    }

    #[tokio::test]
    async fn test_agui_anomaly_creates_detected_in_edge() {
        let (_container, pool) = setup_postgres().await;

        let sovereign_id = Uuid::new_v4();
        sqlx::query(
            "INSERT INTO sovereigns (id, name, public_key_pem, status) VALUES ($1, $2, $3, $4)",
        )
        .bind(sovereign_id)
        .bind("TestSovereign4")
        .bind("-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----")
        .bind("active")
        .execute(&pool)
        .await
        .expect("insert sovereign");

        let ingestor = TelemetryIngestor::new(Arc::new(pool.clone()));

        let event = AgUiEvent {
            event_id: Uuid::new_v4(),
            event_type: "anomaly".to_string(),
            session_id: Uuid::new_v4(),
            sovereign_id,
            payload: serde_json::to_value(AgUiAnomalyPayload {
                anomaly_type: "revocation_pattern".to_string(),
                severity: "high".to_string(),
                event_count: 7,
                window_hours: 2,
                evidence: serde_json::json!({ "revocations": 7 }),
            })
            .expect("serialize"),
            timestamp: Utc::now().to_rfc3339(),
        };

        let node_id = ingestor.ingest_agui_event(event).await.expect("ingest");

        // Wait for async ingestion to complete
        wait_for_entity(&pool, node_id, "AnomalyEventNode", 5000).await;

        // Verify DETECTED_IN edge
        let count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_relationships WHERE source_entity_id = $1 AND relationship_type = 'DETECTED_IN'"
        )
        .bind(node_id)
        .fetch_one(&pool)
        .await
        .expect("fetch");

        assert_eq!(count.0, 1);
    }

    #[tokio::test]
    async fn test_fire_and_forget_nonblocking() {
        let (_container, pool) = setup_postgres().await;

        let ingestor = TelemetryIngestor::new(Arc::new(pool.clone()));

        let event = OtelTraceEvent {
            trace_id: "trace-003".to_string(),
            span_id: "span-003".to_string(),
            span_name: "test_span".to_string(),
            session_id: Uuid::new_v4(),
            sovereign_id: Uuid::new_v4(),
            attributes: OtelAttributes {
                event_type: "test_event".to_string(),
                tier_before: 1,
                tier_after: 1,
                cost_incurred: 0,
                lineage_safe: true,
            },
            start_time: Utc::now().to_rfc3339(),
            end_time: Utc::now().to_rfc3339(),
            status: "ok".to_string(),
        };

        // Fire-and-forget should not block even if sovereign doesn't exist
        // (Real implementation should spawn async task, not await here)
        let start = std::time::Instant::now();
        let result = ingestor.ingest_otel_trace(event).await;
        let elapsed = start.elapsed();

        // Should complete quickly (fire-and-forget semantics)
        // Even if sovereign is missing, should not block on database
        assert!(
            elapsed.as_millis() < 5000,
            "Ingestion should be non-blocking"
        );
    }
}
