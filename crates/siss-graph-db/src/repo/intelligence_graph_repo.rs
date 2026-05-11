use chrono::{DateTime, Utc};
use serde_json::json;
use sqlx::PgPool;
use uuid::Uuid;

#[derive(Debug, Clone, sqlx::FromRow)]
pub struct GraphEntity {
    pub id: Uuid,
    pub label: String,
    pub properties: serde_json::Value,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, sqlx::FromRow)]
pub struct GraphRelationship {
    pub id: Uuid,
    pub source_entity_id: Uuid,
    pub target_entity_id: Uuid,
    pub relationship_type: String,
    pub confidence: f64,
    pub evidence: serde_json::Value,
    pub created_at: DateTime<Utc>,
}

/// Write a recovery event to the intelligence graph.
/// Creates a RecoveryNode with properties and links it to the sovereign.
pub async fn write_recovery_event(
    pool: &PgPool,
    sovereign_id: Uuid,
    event_type: &str, // "probation_to_recovery", "recovery_to_active", "recovery_to_quarantine"
    weeks_elapsed: Option<u32>,
    evidence: serde_json::Value,
    confidence: f64,
) -> Result<Uuid, sqlx::Error> {
    let entity_id = Uuid::new_v4();

    let properties = json!({
        "event_type": event_type,
        "weeks_elapsed": weeks_elapsed,
        "timestamp": Utc::now().to_rfc3339(),
        "evidence": evidence
    });

    sqlx::query(
        "INSERT INTO graph_entities (id, label, properties)
         VALUES ($1, $2, $3)",
    )
    .bind(entity_id)
    .bind("RecoveryNode")
    .bind(&properties)
    .execute(pool)
    .await?;

    // Link to sovereign node (DEPENDS_ON relationship)
    let sovereign_node_id = get_or_create_sovereign_node(pool, sovereign_id).await?;

    sqlx::query(
        "INSERT INTO graph_relationships (source_entity_id, target_entity_id, relationship_type, confidence)
         VALUES ($1, $2, $3, $4)"
    )
    .bind(entity_id)
    .bind(sovereign_node_id)
    .bind("DEPENDS_ON")
    .bind(confidence)
    .execute(pool)
    .await?;

    Ok(entity_id)
}

/// Write a scoring decision to the intelligence graph.
/// Creates a ScoringNode with signal breakdown (slash, anomaly, settlement).
pub async fn write_scoring_decision(
    pool: &PgPool,
    sovereign_id: Uuid,
    score: i16,
    weeks_elapsed: u32,
    slash_count: i64,
    anomaly_count: i64,
    settled_count: i64,
    rationale: &str,
) -> Result<Uuid, sqlx::Error> {
    let entity_id = Uuid::new_v4();

    let properties = json!({
        "score": score,
        "weeks_elapsed": weeks_elapsed,
        "slash_count": slash_count,
        "anomaly_count": anomaly_count,
        "settled_count": settled_count,
        "rationale": rationale,
        "timestamp": Utc::now().to_rfc3339()
    });

    sqlx::query(
        "INSERT INTO graph_entities (id, label, properties)
         VALUES ($1, $2, $3)",
    )
    .bind(entity_id)
    .bind("ScoringNode")
    .bind(&properties)
    .execute(pool)
    .await?;

    Ok(entity_id)
}

/// Write a violation quarantine to the intelligence graph.
/// Creates a ViolationNode and links it to causation (recovery event that triggered it).
pub async fn write_violation_quarantine(
    pool: &PgPool,
    sovereign_id: Uuid,
    reason: &str,
    evidence: serde_json::Value,
    recovery_event_id: Option<Uuid>,
) -> Result<Uuid, sqlx::Error> {
    let entity_id = Uuid::new_v4();

    let properties = json!({
        "reason": reason,
        "evidence": evidence,
        "timestamp": Utc::now().to_rfc3339()
    });

    sqlx::query(
        "INSERT INTO graph_entities (id, label, properties)
         VALUES ($1, $2, $3)",
    )
    .bind(entity_id)
    .bind("ViolationNode")
    .bind(&properties)
    .execute(pool)
    .await?;

    // If there's a recovery event that triggered this, link it
    if let Some(recovery_id) = recovery_event_id {
        sqlx::query(
            "INSERT INTO graph_relationships (source_entity_id, target_entity_id, relationship_type, confidence)
             VALUES ($1, $2, $3, $4)"
        )
        .bind(recovery_id)
        .bind(entity_id)
        .bind("TRIGGERS")
        .bind(1.0)
        .execute(pool)
        .await?;
    }

    Ok(entity_id)
}

/// Write a trust relationship to the intelligence graph.
/// Creates a TrustNetworkNode and links source and target sovereigns.
pub async fn write_trust_relationship(
    pool: &PgPool,
    source_id: Uuid,
    target_id: Uuid,
    trust_score: i16,
    evidence: serde_json::Value,
    confidence: f64,
) -> Result<Uuid, sqlx::Error> {
    let entity_id = Uuid::new_v4();

    let properties = json!({
        "trust_score": trust_score,
        "confidence": confidence,
        "source_sovereign_id": source_id.to_string(),
        "target_sovereign_id": target_id.to_string(),
        "evidence": evidence,
        "timestamp": Utc::now().to_rfc3339()
    });

    sqlx::query(
        "INSERT INTO graph_entities (id, label, properties)
         VALUES ($1, $2, $3)",
    )
    .bind(entity_id)
    .bind("TrustNetworkNode")
    .bind(&properties)
    .execute(pool)
    .await?;

    let source_node = get_or_create_sovereign_node(pool, source_id).await?;
    let target_node = get_or_create_sovereign_node(pool, target_id).await?;

    sqlx::query(
        "INSERT INTO graph_relationships (source_entity_id, target_entity_id, relationship_type, confidence, evidence)
         VALUES ($1, $2, $3, $4, $5)"
    )
    .bind(source_node)
    .bind(entity_id)
    .bind("TRUSTS")
    .bind(confidence)
    .bind(&evidence)
    .execute(pool)
    .await?;

    sqlx::query(
        "INSERT INTO graph_relationships (source_entity_id, target_entity_id, relationship_type, confidence, evidence)
         VALUES ($1, $2, $3, $4, $5)"
    )
    .bind(entity_id)
    .bind(target_node)
    .bind("EXPLAINS")
    .bind(confidence)
    .bind(&evidence)
    .execute(pool)
    .await?;

    Ok(entity_id)
}

/// Query the full decision lineage for a sovereign.
/// Returns all entities and relationships related to their recovery/probation history.
pub async fn query_entity_lineage(
    pool: &PgPool,
    sovereign_id: Uuid,
) -> Result<Vec<(GraphEntity, Vec<GraphRelationship>)>, sqlx::Error> {
    let sovereign_node_id = get_or_create_sovereign_node(pool, sovereign_id).await?;

    // Fetch all entities linked to this sovereign
    let entities: Vec<GraphEntity> = sqlx::query_as(
        "SELECT id, label, properties, created_at
         FROM graph_entities
         WHERE id IN (
           SELECT source_entity_id FROM graph_relationships WHERE target_entity_id = $1
           UNION
           SELECT target_entity_id FROM graph_relationships WHERE source_entity_id = $1
         )
         ORDER BY created_at DESC",
    )
    .bind(sovereign_node_id)
    .fetch_all(pool)
    .await?;

    let mut result = Vec::new();
    for entity in entities {
        let relationships: Vec<GraphRelationship> = sqlx::query_as(
            "SELECT id, source_entity_id, target_entity_id, relationship_type, confidence, evidence, created_at
             FROM graph_relationships
             WHERE source_entity_id = $1 OR target_entity_id = $1"
        )
        .bind(entity.id)
        .fetch_all(pool)
        .await?;

        result.push((entity, relationships));
    }

    Ok(result)
}

/// Get or create a sovereign node in the intelligence graph.
async fn get_or_create_sovereign_node(
    pool: &PgPool,
    sovereign_id: Uuid,
) -> Result<Uuid, sqlx::Error> {
    // Check if node already exists
    if let Some(node_id) = sqlx::query_scalar::<_, Uuid>(
        "SELECT id FROM graph_entities WHERE label = 'SovereignNode' AND properties->>'sovereign_id' = $1"
    )
    .bind(sovereign_id.to_string())
    .fetch_optional(pool)
    .await?
    {
        return Ok(node_id);
    }

    // Create new sovereign node
    let node_id = Uuid::new_v4();
    let properties = json!({
        "sovereign_id": sovereign_id.to_string(),
        "created_at": Utc::now().to_rfc3339()
    });

    sqlx::query(
        "INSERT INTO graph_entities (id, label, properties)
         VALUES ($1, $2, $3)",
    )
    .bind(node_id)
    .bind("SovereignNode")
    .bind(&properties)
    .execute(pool)
    .await?;

    Ok(node_id)
}

/// Write a trust anomaly pattern node to the intelligence graph.
/// Idempotent: same source_id triggers an upsert (update, not duplicate).
/// Creates a TrustAnomalyPatternNode and links it to the source sovereign via EXHIBITS edge.
pub async fn write_trust_anomaly_pattern(
    pool: &PgPool,
    source_id: Uuid,
    target_id: Uuid,
    latest_score: i16,
    dominant_cause: &str,
    occurrence_count: usize,
    first_detected: chrono::DateTime<chrono::Utc>,
    last_detected: chrono::DateTime<chrono::Utc>,
) -> Result<Uuid, sqlx::Error> {
    let properties = serde_json::json!({
        "source_id": source_id.to_string(),
        "target_id": target_id.to_string(),
        "occurrence_count": occurrence_count,
        "latest_score": latest_score,
        "dominant_cause": dominant_cause,
        "first_detected": first_detected.to_rfc3339(),
        "last_detected": last_detected.to_rfc3339(),
    });

    // 1. Upsert TrustAnomalyPatternNode
    let pattern_id: Uuid = sqlx::query_scalar(
        "INSERT INTO graph_entities (id, label, properties) \
         VALUES ($1, 'TrustAnomalyPatternNode', $2) \
         ON CONFLICT ((properties->>'source_id')) \
         WHERE label = 'TrustAnomalyPatternNode' \
         DO UPDATE SET properties = EXCLUDED.properties, updated_at = NOW() \
         RETURNING id",
    )
    .bind(Uuid::new_v4())
    .bind(&properties)
    .fetch_one(pool)
    .await?;

    // 2. Get or create SovereignNode for source
    let sovereign_node_id = get_or_create_sovereign_node(pool, source_id).await?;

    // 3. Insert EXHIBITS edge (idempotent)
    sqlx::query(
        "INSERT INTO graph_relationships \
         (source_entity_id, target_entity_id, relationship_type, confidence) \
         VALUES ($1, $2, 'EXHIBITS', 1.0) \
         ON CONFLICT (source_entity_id, target_entity_id, relationship_type) \
         DO NOTHING",
    )
    .bind(sovereign_node_id)
    .bind(pattern_id)
    .execute(pool)
    .await?;

    Ok(pattern_id)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_graph_entity_creation() {
        // Placeholder: integration test would require DB
    }

    // Helper to set up test PostgreSQL container
    async fn setup_test_postgres() -> (
        testcontainers::ContainerAsync<testcontainers::GenericImage>,
        sqlx::PgPool,
    ) {
        use testcontainers::runners::AsyncRunner;
        use testcontainers::{GenericImage, ImageExt, core::WaitFor};

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
        (container, pool)
    }

    #[tokio::test]
    async fn test_write_trust_anomaly_pattern_creates_entity() {
        // Setup: testcontainers postgres, run all migrations including 035
        let (_container, pool) = setup_test_postgres().await;
        crate::migrations::run_all(&pool).await.expect("migrations");

        let source_id = uuid::Uuid::new_v4();
        let target_id = uuid::Uuid::new_v4();

        // Action: write_trust_anomaly_pattern
        let result = write_trust_anomaly_pattern(
            &pool,
            source_id,
            target_id,
            42,
            "decay_collapse",
            3,
            chrono::Utc::now(),
            chrono::Utc::now(),
        )
        .await;

        assert!(result.is_ok(), "write_trust_anomaly_pattern should succeed");

        // Assert: entity exists in graph_entities
        let count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities WHERE label = 'TrustAnomalyPatternNode' \
             AND properties->>'source_id' = $1",
        )
        .bind(source_id.to_string())
        .fetch_one(&pool)
        .await
        .expect("query");

        assert_eq!(count.0, 1, "Should have exactly 1 TrustAnomalyPatternNode");
    }

    #[tokio::test]
    async fn test_write_trust_anomaly_pattern_idempotent() {
        // Setup
        let (_container, pool) = setup_test_postgres().await;
        crate::migrations::run_all(&pool).await.expect("migrations");

        let source_id = uuid::Uuid::new_v4();
        let target_id = uuid::Uuid::new_v4();
        let now = chrono::Utc::now();

        // Action: call twice with same source_id, different occurrence_count
        let _result1 = write_trust_anomaly_pattern(
            &pool,
            source_id,
            target_id,
            42,
            "decay_collapse",
            3,
            now,
            now,
        )
        .await;
        let _result2 = write_trust_anomaly_pattern(
            &pool,
            source_id,
            target_id,
            50,
            "decay_collapse",
            5,
            now,
            now,
        )
        .await;

        // Assert: count still 1 (updated, not duplicated)
        let count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities WHERE label = 'TrustAnomalyPatternNode' \
             AND properties->>'source_id' = $1",
        )
        .bind(source_id.to_string())
        .fetch_one(&pool)
        .await
        .expect("query");

        assert_eq!(
            count.0, 1,
            "Should still have exactly 1 node (updated, not duplicated)"
        );

        // Assert: occurrence_count updated to 5
        let properties: serde_json::Value = sqlx::query_scalar(
            "SELECT properties FROM graph_entities WHERE label = 'TrustAnomalyPatternNode' \
             AND properties->>'source_id' = $1",
        )
        .bind(source_id.to_string())
        .fetch_one(&pool)
        .await
        .expect("query");

        assert_eq!(
            properties["occurrence_count"].as_i64(),
            Some(5),
            "occurrence_count should be updated to 5"
        );
    }

    #[tokio::test]
    async fn test_write_trust_anomaly_pattern_creates_exhibits_edge() {
        // Setup
        let (_container, pool) = setup_test_postgres().await;
        crate::migrations::run_all(&pool).await.expect("migrations");

        let source_id = uuid::Uuid::new_v4();
        let target_id = uuid::Uuid::new_v4();

        // Action: write_trust_anomaly_pattern
        let _result = write_trust_anomaly_pattern(
            &pool,
            source_id,
            target_id,
            42,
            "decay_collapse",
            3,
            chrono::Utc::now(),
            chrono::Utc::now(),
        )
        .await;

        // Assert: EXHIBITS edge exists
        let count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_relationships WHERE relationship_type = 'EXHIBITS'",
        )
        .fetch_one(&pool)
        .await
        .expect("query");

        assert_eq!(count.0, 1, "Should have exactly 1 EXHIBITS edge");
    }
}
