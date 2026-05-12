use chrono::{DateTime, Utc};
use sqlx::{FromRow, PgPool};
use uuid::Uuid;

/// A pair of consecutive AnomalyEventNode entities (different types) for the same sovereign.
#[derive(Debug, Clone, FromRow)]
pub struct AnomalyChainPair {
    pub first_anomaly_id: Uuid,
    pub second_anomaly_id: Uuid,
    pub sovereign_id: Uuid,
    pub first_type: String,
    pub second_type: String,
    pub elapsed_hours: f64,
}

/// Fetch pairs of anomalies (different types, same sovereign) within a time window.
/// Skips pairs that already have a LEADS_TO edge.
pub async fn fetch_anomaly_chain_pairs(
    pool: &PgPool,
    since: DateTime<Utc>,
    window_hours: i64,
) -> Result<Vec<AnomalyChainPair>, sqlx::Error> {
    let pairs: Vec<AnomalyChainPair> = sqlx::query_as(
        "SELECT
            a1.id AS first_anomaly_id,
            a2.id AS second_anomaly_id,
            (a1.properties->>'sovereign_id')::uuid AS sovereign_id,
            a1.properties->>'anomaly_type' AS first_type,
            a2.properties->>'anomaly_type' AS second_type,
            EXTRACT(EPOCH FROM (
                (a2.properties->>'detected_at')::timestamptz -
                (a1.properties->>'detected_at')::timestamptz
            ))::float / 3600.0 AS elapsed_hours
        FROM graph_entities a1
        JOIN graph_entities a2 ON a2.label = 'AnomalyEventNode'
            AND (a2.properties->>'sovereign_id') = (a1.properties->>'sovereign_id')
            AND a2.properties->>'anomaly_type' != a1.properties->>'anomaly_type'
        WHERE a1.label = 'AnomalyEventNode'
          AND (a1.properties->>'detected_at')::timestamptz > $1
          AND (a2.properties->>'detected_at')::timestamptz BETWEEN
              (a1.properties->>'detected_at')::timestamptz
              AND (a1.properties->>'detected_at')::timestamptz + ($2 * INTERVAL '1 hour')
          AND NOT EXISTS (
              SELECT 1 FROM graph_relationships r
              WHERE r.source_entity_id = a1.id
                AND r.target_entity_id = a2.id
                AND r.relationship_type = 'LEADS_TO'
          )
        ORDER BY a1.created_at ASC
        LIMIT 200",
    )
    .bind(since)
    .bind(window_hours)
    .fetch_all(pool)
    .await?;

    Ok(pairs)
}
