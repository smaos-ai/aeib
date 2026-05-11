use chrono::{DateTime, Utc};
use sqlx::{FromRow, PgPool};
use uuid::Uuid;

/// A pair of AgentActionNode and AnomalyEventNode entities within a time window.
#[derive(Debug, Clone, FromRow)]
pub struct ActionAnomalyPair {
    pub action_entity_id: Uuid,
    pub anomaly_entity_id: Uuid,
    pub sovereign_id: Uuid,
    pub gap_seconds: f64,
    pub action_cost: i64,
    pub action_event_type: String,
}

/// Fetch pairs of high-cost actions followed by anomalies within a time window for the same sovereign.
/// Skips pairs that already have a PRECEDES edge.
pub async fn fetch_action_anomaly_pairs(
    pool: &PgPool,
    since: DateTime<Utc>,
    window_hours: i64,
    cost_threshold: i64,
) -> Result<Vec<ActionAnomalyPair>, sqlx::Error> {
    let pairs: Vec<ActionAnomalyPair> = sqlx::query_as(
        "SELECT
            a.id AS action_entity_id,
            an.id AS anomaly_entity_id,
            (a.properties->>'sovereign_id')::uuid AS sovereign_id,
            EXTRACT(EPOCH FROM (
                (an.properties->>'detected_at')::timestamptz -
                (a.properties->>'scored_at')::timestamptz
            ))::float AS gap_seconds,
            (a.properties->>'cost_incurred')::bigint AS action_cost,
            a.properties->>'event_type' AS action_event_type
        FROM graph_entities a
        JOIN graph_entities an ON an.label = 'AnomalyEventNode'
            AND (an.properties->>'sovereign_id') = (a.properties->>'sovereign_id')
        WHERE a.label = 'AgentActionNode'
          AND (a.properties->>'scored_at')::timestamptz > $1
          AND (a.properties->>'cost_incurred')::bigint > $2
          AND (an.properties->>'detected_at')::timestamptz BETWEEN
              (a.properties->>'scored_at')::timestamptz
              AND (a.properties->>'scored_at')::timestamptz + ($3 * INTERVAL '1 hour')
          AND NOT EXISTS (
              SELECT 1 FROM graph_relationships r
              WHERE r.source_entity_id = a.id
                AND r.target_entity_id = an.id
                AND r.relationship_type = 'PRECEDES'
          )
        ORDER BY a.created_at ASC
        LIMIT 200",
    )
    .bind(since)
    .bind(cost_threshold)
    .bind(window_hours)
    .fetch_all(pool)
    .await?;

    Ok(pairs)
}

/// A pair of SystemMetricNode and AnomalyEventNode entities within a time window.
#[derive(Debug, Clone, FromRow)]
pub struct MetricAnomalyPair {
    pub metric_entity_id: Uuid,
    pub anomaly_entity_id: Uuid,
    pub sovereign_id: Uuid,
    pub gap_seconds: f64,
    pub utilization_pct: f64,
}

/// Fetch pairs of high utilization metrics followed by anomalies within a time window.
/// Skips pairs that already have a COINCIDES_WITH edge.
pub async fn fetch_metric_anomaly_pairs(
    pool: &PgPool,
    since: DateTime<Utc>,
    window_hours: i64,
    utilization_threshold: f64,
) -> Result<Vec<MetricAnomalyPair>, sqlx::Error> {
    let pairs: Vec<MetricAnomalyPair> = sqlx::query_as(
        "SELECT
            m.id AS metric_entity_id,
            an.id AS anomaly_entity_id,
            (m.properties->>'sovereign_id')::uuid AS sovereign_id,
            EXTRACT(EPOCH FROM (
                (an.properties->>'detected_at')::timestamptz -
                (m.properties->>'snapshot_at')::timestamptz
            ))::float AS gap_seconds,
            (m.properties->>'budget_utilization_pct')::float AS utilization_pct
        FROM graph_entities m
        JOIN graph_entities an ON an.label = 'AnomalyEventNode'
            AND (an.properties->>'sovereign_id') = (m.properties->>'sovereign_id')
        WHERE m.label = 'SystemMetricNode'
          AND (m.properties->>'snapshot_at')::timestamptz > $1
          AND (m.properties->>'budget_utilization_pct')::float > $2
          AND (an.properties->>'detected_at')::timestamptz BETWEEN
              (m.properties->>'snapshot_at')::timestamptz
              AND (m.properties->>'snapshot_at')::timestamptz + ($3 * INTERVAL '1 hour')
          AND NOT EXISTS (
              SELECT 1 FROM graph_relationships r
              WHERE r.source_entity_id = m.id
                AND r.target_entity_id = an.id
                AND r.relationship_type = 'COINCIDES_WITH'
          )
        ORDER BY m.created_at ASC
        LIMIT 200",
    )
    .bind(since)
    .bind(utilization_threshold)
    .bind(window_hours)
    .fetch_all(pool)
    .await?;

    Ok(pairs)
}
