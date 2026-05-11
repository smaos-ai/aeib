use chrono::{DateTime, Utc};
use sqlx::{FromRow, PgPool};
use uuid::Uuid;

/// A single signal row — one signal node per row. Aggregated in Rust by sovereign and signal type.
#[derive(Debug, Clone, FromRow)]
pub struct SignalRow {
    pub sovereign_id: Uuid,
    pub signal_type: String, // "AnomalyChainNode" | "CorrelationPatternNode" | "RecoveryCorrelationNode"
    pub confidence: f64,
    pub chain_type: Option<String>, // "dispute_spam→timeout_spam" (AnomalyChainNode only)
    pub anomaly_type: Option<String>, // anomaly type (RecoveryCorrelationNode only)
    pub last_seen_at: DateTime<Utc>, // For decay calculation
    pub acceleration_mode: bool,    // true if signal is in acceleration mode (decays faster)
}

/// Fetch all signals for all sovereigns: AnomalyChainNode, CorrelationPatternNode, RecoveryCorrelationNode.
/// Returns signal rows ordered by sovereign and confidence (descending) to allow Rust aggregation.
pub async fn fetch_sovereign_signals(pool: &PgPool) -> Result<Vec<SignalRow>, sqlx::Error> {
    let signals: Vec<SignalRow> = sqlx::query_as(
        "SELECT
            (properties->>'sovereign_id')::uuid AS sovereign_id,
            label AS signal_type,
            (properties->>'confidence')::float AS confidence,
            properties->>'chain_type' AS chain_type,
            properties->>'anomaly_type' AS anomaly_type,
            (properties->>'last_seen_at')::timestamptz AS last_seen_at,
            COALESCE((properties->>'acceleration_mode')::boolean, false) AS acceleration_mode
        FROM graph_entities
        WHERE label IN ('AnomalyChainNode', 'CorrelationPatternNode', 'RecoveryCorrelationNode')
          AND (properties->>'confidence')::float > 0.0
        ORDER BY (properties->>'sovereign_id')::uuid, (properties->>'confidence')::float DESC",
    )
    .fetch_all(pool)
    .await?;

    Ok(signals)
}
