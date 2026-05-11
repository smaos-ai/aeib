use chrono::DateTime;
use chrono::Utc;
use sqlx::{FromRow, PgPool};
use uuid::Uuid;

/// A pair of AnomalyEventNode and RecoveryNode entities within a time window for the same sovereign.
#[derive(Debug, Clone, FromRow)]
pub struct AnomalyRecoveryPair {
    pub anomaly_entity_id: Uuid,
    pub recovery_entity_id: Uuid,
    pub sovereign_id: Uuid,
    pub anomaly_type: String,
    pub gap_hours: f64,
}

/// Fetch pairs of anomalies followed by recovery entries within a time window.
/// RecoveryNode lacks sovereign_id in properties; correlation requires a 3-table join
/// through SovereignNode via DEPENDS_ON edge.
/// Skips pairs that already have a PRECEDED_RECOVERY edge.
pub async fn fetch_anomaly_recovery_pairs(
    pool: &PgPool,
    since: DateTime<Utc>,
    window_hours: i64,
) -> Result<Vec<AnomalyRecoveryPair>, sqlx::Error> {
    let pairs: Vec<AnomalyRecoveryPair> = sqlx::query_as(
        "SELECT
            ae.id AS anomaly_entity_id,
            rn.id AS recovery_entity_id,
            (ae.properties->>'sovereign_id')::uuid AS sovereign_id,
            ae.properties->>'anomaly_type' AS anomaly_type,
            EXTRACT(EPOCH FROM (
                (rn.properties->>'timestamp')::timestamptz -
                (ae.properties->>'detected_at')::timestamptz
            ))::float / 3600.0 AS gap_hours
        FROM graph_entities ae
        JOIN graph_entities sov ON sov.label = 'SovereignNode'
            AND sov.properties->>'sovereign_id' = ae.properties->>'sovereign_id'
        JOIN graph_relationships dep ON dep.target_entity_id = sov.id
            AND dep.relationship_type = 'DEPENDS_ON'
        JOIN graph_entities rn ON rn.id = dep.source_entity_id
            AND rn.label = 'RecoveryNode'
        WHERE ae.label = 'AnomalyEventNode'
          AND (ae.properties->>'detected_at')::timestamptz > $1
          AND (rn.properties->>'timestamp')::timestamptz BETWEEN
              (ae.properties->>'detected_at')::timestamptz
              AND (ae.properties->>'detected_at')::timestamptz + ($2 * INTERVAL '1 hour')
          AND NOT EXISTS (
              SELECT 1 FROM graph_relationships gr
              WHERE gr.source_entity_id = ae.id
                AND gr.target_entity_id = rn.id
                AND gr.relationship_type = 'PRECEDED_RECOVERY'
          )
        ORDER BY ae.created_at ASC
        LIMIT 200",
    )
    .bind(since)
    .bind(window_hours)
    .fetch_all(pool)
    .await?;

    Ok(pairs)
}
