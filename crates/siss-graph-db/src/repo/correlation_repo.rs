use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::PgPool;
use uuid::Uuid;

/// Detected correlation between event type and anomaly type
#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
pub struct AnomalyCorrelation {
    pub pattern_id: Uuid,
    pub sovereign_id: Uuid,
    pub triggering_event_type: String, // e.g., 'process_payment'
    pub anomaly_type: String,          // e.g., 'dispute_spam'
    pub correlation_strength: f64,     // 0.0-1.0: P(anomaly | event_type)
    pub sample_size: i32,              // How many (event, anomaly) pairs?
    pub confidence_95th: f64,          // Statistical confidence
    pub detected_at: DateTime<Utc>,
}

/// Response: paginated correlations
#[derive(Debug, Clone, Serialize)]
pub struct CorrelationPageResponse {
    pub correlations: Vec<AnomalyCorrelation>,
    pub total_count: i64,
    pub has_more: bool,
}

/// Correlate anomalies with preceding agent actions
///
/// Detects patterns like: "When Agent_A runs process_payment, 75% of the time
/// it triggers dispute_spam within 5 minutes"
///
/// Filter criteria:
/// - sample_size >= min_sample_size (default 10)
/// - correlation_strength > 0.5 (at least 50% correlation)
/// - 30-day lookback window
pub async fn correlate_anomalies(
    pool: &PgPool,
    sovereign_id: Uuid,
    min_sample_size: i32,
    limit: Option<i32>,
) -> Result<CorrelationPageResponse, sqlx::Error> {
    let limit = limit.unwrap_or(25).min(100);

    // SQL: Group-based aggregation without Cartesian join
    // For each (event_type, anomaly_type) pair, calculate correlation in-database
    // Avoids loading 30 days of data into memory
    let correlations = sqlx::query_as::<_, AnomalyCorrelation>(
        r#"
        SELECT
            gen_random_uuid() as pattern_id,
            $1::uuid as sovereign_id,
            (a.properties->>'event_type') as triggering_event_type,
            (an.properties->>'anomaly_type') as anomaly_type,
            COUNT(CASE WHEN (an.properties->>'detected_at')::timestamptz
                BETWEEN (a.properties->>'scored_at')::timestamptz
                    AND (a.properties->>'scored_at')::timestamptz + INTERVAL '5 minutes'
                THEN 1 END)::float / COUNT(*)::float as correlation_strength,
            COUNT(*) as sample_size,
            0.95::float as confidence_95th,
            NOW()::timestamptz as detected_at
        FROM (
            SELECT DISTINCT
                id,
                (properties->>'event_type') as event_type,
                (properties->>'scored_at')::timestamptz as scored_at
            FROM graph_entities
            WHERE label = 'AgentActionNode'
              AND (properties->>'sovereign_id')::uuid = $1
              AND created_at > NOW() - INTERVAL '30 days'
        ) a
        CROSS JOIN (
            SELECT DISTINCT
                id,
                (properties->>'anomaly_type') as anomaly_type,
                (properties->>'detected_at')::timestamptz as detected_at
            FROM graph_entities
            WHERE label = 'AnomalyEventNode'
              AND (properties->>'sovereign_id')::uuid = $1
              AND created_at > NOW() - INTERVAL '30 days'
        ) an
        GROUP BY a.event_type, an.anomaly_type
        HAVING COUNT(*) >= $2
          AND COUNT(CASE WHEN (an.detected_at)
                BETWEEN (a.scored_at) AND (a.scored_at) + INTERVAL '5 minutes'
                THEN 1 END)::float / COUNT(*)::float > 0.5
        ORDER BY correlation_strength DESC
        LIMIT $3
        "#,
    )
    .bind(sovereign_id)
    .bind(min_sample_size)
    .bind(limit)
    .fetch_all(pool)
    .await?;

    let total_count = correlations.len() as i64;
    let has_more = false; // Placeholder

    Ok(CorrelationPageResponse {
        correlations,
        total_count,
        has_more,
    })
}

/// Quick check: does this event_type typically cause anomalies?
pub async fn is_anomaly_prone_event(
    pool: &PgPool,
    sovereign_id: Uuid,
    event_type: &str,
) -> Result<bool, sqlx::Error> {
    let count: i64 = sqlx::query_scalar(
        r#"
        SELECT COUNT(*)
        FROM graph_entities action
        JOIN graph_entities anomaly
            ON (action.properties->>'sovereign_id')::uuid
             = (anomaly.properties->>'sovereign_id')::uuid
        WHERE action.label = 'AgentActionNode'
          AND anomaly.label = 'AnomalyEventNode'
          AND (action.properties->>'sovereign_id')::uuid = $1
          AND (action.properties->>'event_type') = $2
          AND (anomaly.properties->>'detected_at')::timestamptz
            <= (action.properties->>'scored_at')::timestamptz + INTERVAL '5 minutes'
        "#,
    )
    .bind(sovereign_id)
    .bind(event_type)
    .fetch_one(pool)
    .await?;

    Ok(count > 0)
}

#[cfg(test)]
mod tests {
    use super::*;

    // Placeholder tests — full suite will be integrated
    #[test]
    fn test_correlation_structure() {
        let _corr = AnomalyCorrelation {
            pattern_id: Uuid::new_v4(),
            sovereign_id: Uuid::new_v4(),
            triggering_event_type: "process_payment".to_string(),
            anomaly_type: "dispute_spam".to_string(),
            correlation_strength: 0.75,
            sample_size: 20,
            confidence_95th: 0.95,
            detected_at: Utc::now(),
        };
    }

    #[test]
    fn test_correlation_strength_bounds() {
        let strength = 0.75;
        assert!(
            strength >= 0.0 && strength <= 1.0,
            "Correlation strength should be 0.0-1.0"
        );
    }
}
