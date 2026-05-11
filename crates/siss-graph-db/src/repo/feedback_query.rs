use chrono::{DateTime, Utc};
use sqlx::{FromRow, PgPool};
use uuid::Uuid;

/// A single feedback row for aggregation.
#[derive(Debug, Clone, FromRow)]
pub struct FeedbackRow {
    pub feedback_node_id: Uuid,
    pub prediction_node_id: Uuid,
    pub sovereign_id: Uuid,
    pub predicted_anomaly_type: String,
    pub matched: bool,
    pub prediction_risk_score: f64,
    pub created_at: DateTime<Utc>,
}

/// Fetch all unprocessed feedback created since a given timestamp.
pub async fn fetch_unprocessed_feedback(
    pool: &PgPool,
    since: DateTime<Utc>,
) -> Result<Vec<FeedbackRow>, sqlx::Error> {
    let rows = sqlx::query_as(
        "SELECT
            id AS feedback_node_id,
            (properties->>'prediction_node_id')::uuid AS prediction_node_id,
            (properties->>'sovereign_id')::uuid AS sovereign_id,
            properties->>'predicted_anomaly_type' AS predicted_anomaly_type,
            (properties->>'matched')::boolean AS matched,
            (properties->>'prediction_risk_score')::float AS prediction_risk_score,
            (properties->>'created_at')::timestamptz AS created_at
         FROM graph_entities
         WHERE label = 'FeedbackNode'
         AND (properties->>'created_at')::timestamptz > $1
         ORDER BY (properties->>'created_at')::timestamptz ASC",
    )
    .bind(since)
    .fetch_all(pool)
    .await?;

    Ok(rows)
}
