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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_graph_entity_creation() {
        // Placeholder: integration test would require DB
    }
}
