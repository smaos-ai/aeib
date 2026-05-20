use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::PgPool;
use uuid::Uuid;

/// Agent action projection for real-time dashboard
#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
pub struct AgentActionProjection {
    pub action_id: Uuid,
    pub behavior_event_id: Uuid,
    pub session_id: Uuid,
    pub persona_id: Uuid,
    pub sovereign_id: Uuid,
    pub event_type: String,
    pub tier_before: i16,
    pub tier_after: i16,
    pub cost_incurred: i64,
    pub lineage_safe: bool,
    pub scored_at: DateTime<Utc>,
}

/// Paginated response for agent actions
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentActionsPageResponse {
    pub actions: Vec<AgentActionProjection>,
    pub total_count: i64,
    pub has_more: bool,
}

/// Fetch recent agent actions paginated
pub async fn fetch_agent_actions(
    pool: &PgPool,
    sovereign_id: Uuid,
    since: Option<DateTime<Utc>>,
    limit: Option<i32>,
) -> Result<AgentActionsPageResponse, sqlx::Error> {
    let since = since.unwrap_or_else(|| Utc::now() - chrono::Duration::hours(1));
    let limit = limit.unwrap_or(100).min(500); // Cap at 500

    // Fetch actions
    let actions = sqlx::query_as::<_, AgentActionProjection>(
        r#"
        SELECT
            ge.id as action_id,
            (ge.properties->>'behavior_event_id')::uuid as behavior_event_id,
            (ge.properties->>'session_id')::uuid as session_id,
            (ge.properties->>'persona_id')::uuid as persona_id,
            (ge.properties->>'sovereign_id')::uuid as sovereign_id,
            (ge.properties->>'event_type') as event_type,
            (ge.properties->>'tier_before')::smallint as tier_before,
            (ge.properties->>'tier_after')::smallint as tier_after,
            (ge.properties->>'cost_incurred')::bigint as cost_incurred,
            (ge.properties->>'lineage_safe')::boolean as lineage_safe,
            (ge.properties->>'scored_at')::timestamptz as scored_at
        FROM graph_entities ge
        WHERE ge.label = 'AgentActionNode'
          AND (ge.properties->>'sovereign_id')::uuid = $1
          AND (ge.properties->>'scored_at')::timestamptz > $2
        ORDER BY ge.created_at DESC
        LIMIT $3
        "#,
    )
    .bind(sovereign_id)
    .bind(since)
    .bind(limit)
    .fetch_all(pool)
    .await?;

    // Get total count (not capped)
    let total_count: i64 = sqlx::query_scalar(
        r#"
        SELECT COUNT(*)
        FROM graph_entities ge
        WHERE ge.label = 'AgentActionNode'
          AND (ge.properties->>'sovereign_id')::uuid = $1
        "#,
    )
    .bind(sovereign_id)
    .fetch_one(pool)
    .await?;

    let has_more = actions.len() as i32 >= limit;

    Ok(AgentActionsPageResponse {
        actions,
        total_count,
        has_more,
    })
}

/// Anomaly projection for real-time dashboard
#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
pub struct AnomalyProjection {
    pub anomaly_id: Uuid,
    pub anomaly_db_id: Uuid,
    pub sovereign_id: Uuid,
    pub persona_id: Option<Uuid>,
    pub anomaly_type: String,
    pub severity: String,
    pub event_count: i64,
    pub window_hours: i64,
    pub evidence: serde_json::Value,
    pub detected_at: DateTime<Utc>,
    pub recovery_triggered: bool,
    pub recovery_tier_impact: Option<i16>,
}

/// Paginated response for anomalies
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnomaliesPageResponse {
    pub anomalies: Vec<AnomalyProjection>,
    pub total_count: i64,
    pub has_more: bool,
    pub active_recovery_count: i32,
}

/// Fetch anomalies with optional filtering
pub async fn fetch_anomalies(
    pool: &PgPool,
    sovereign_id: Uuid,
    severity: Option<&str>,
    anomaly_type: Option<&str>,
    limit: Option<i32>,
) -> Result<AnomaliesPageResponse, sqlx::Error> {
    let limit = limit.unwrap_or(50).min(200); // Cap at 200

    // Base query
    let base_query = r#"
        SELECT
            ge.id as anomaly_id,
            (ge.properties->>'anomaly_db_id')::uuid as anomaly_db_id,
            (ge.properties->>'sovereign_id')::uuid as sovereign_id,
            NULL::uuid as persona_id,
            (ge.properties->>'anomaly_type') as anomaly_type,
            (ge.properties->>'severity') as severity,
            (ge.properties->>'event_count')::bigint as event_count,
            (ge.properties->>'window_hours')::bigint as window_hours,
            ge.properties->'evidence' as evidence,
            (ge.properties->>'detected_at')::timestamptz as detected_at,
            false as recovery_triggered,
            NULL::smallint as recovery_tier_impact
        FROM graph_entities ge
        WHERE ge.label = 'AnomalyEventNode'
          AND (ge.properties->>'sovereign_id')::uuid = $1
          AND (ge.properties->>'detected_at')::timestamptz > NOW() - INTERVAL '7 days'
    "#;

    // Execute with correct parameter binding for each path
    let anomalies = match (severity, anomaly_type) {
        // (None, None) path → 2 params: $1 (sovereign_id), $2 (limit)
        (None, None) => {
            let query_str = format!(
                "{}        ORDER BY ge.created_at DESC\n        LIMIT $2",
                base_query
            );
            sqlx::query_as::<_, AnomalyProjection>(&query_str)
                .bind(sovereign_id)
                .bind(limit)
                .fetch_all(pool)
                .await?
        }
        // (Some(sev), None) path → 3 params: $1, $2 (severity), $3 (limit)
        (Some(sev), None) => {
            let query_str = format!(
                "{}          AND (ge.properties->>'severity') = $2\n        ORDER BY ge.created_at DESC\n        LIMIT $3",
                base_query
            );
            sqlx::query_as::<_, AnomalyProjection>(&query_str)
                .bind(sovereign_id)
                .bind(sev)
                .bind(limit)
                .fetch_all(pool)
                .await?
        }
        // (None, Some(atype)) path → 3 params: $1, $2 (anomaly_type), $3 (limit)
        (None, Some(atype)) => {
            let query_str = format!(
                "{}          AND (ge.properties->>'anomaly_type') = $2\n        ORDER BY ge.created_at DESC\n        LIMIT $3",
                base_query
            );
            sqlx::query_as::<_, AnomalyProjection>(&query_str)
                .bind(sovereign_id)
                .bind(atype)
                .bind(limit)
                .fetch_all(pool)
                .await?
        }
        // (Some(sev), Some(atype)) path → 4 params: $1, $2 (sev), $3 (atype), $4 (limit)
        (Some(sev), Some(atype)) => {
            let query_str = format!(
                "{}          AND (ge.properties->>'severity') = $2\n          AND (ge.properties->>'anomaly_type') = $3\n        ORDER BY ge.created_at DESC\n        LIMIT $4",
                base_query
            );
            sqlx::query_as::<_, AnomalyProjection>(&query_str)
                .bind(sovereign_id)
                .bind(sev)
                .bind(atype)
                .bind(limit)
                .fetch_all(pool)
                .await?
        }
    };

    // Get total count
    let total_count: i64 = sqlx::query_scalar(
        r#"
        SELECT COUNT(*)
        FROM graph_entities ge
        WHERE ge.label = 'AnomalyEventNode'
          AND (ge.properties->>'sovereign_id')::uuid = $1
        "#,
    )
    .bind(sovereign_id)
    .fetch_one(pool)
    .await?;

    // Get active recovery count
    let active_recovery_count: i32 = sqlx::query_scalar(
        "SELECT COUNT(DISTINCT (properties->>'persona_id'))::int FROM behavior_events WHERE status = 'in_recovery'"
    )
    .fetch_optional(pool)
    .await?
    .flatten()
    .unwrap_or(0);

    let has_more = anomalies.len() as i32 >= limit;

    Ok(AnomaliesPageResponse {
        anomalies,
        total_count,
        has_more,
        active_recovery_count,
    })
}

/// Recovery status projection with fail-closed approval lock
#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
pub struct RecoveryProjection {
    pub recovery_id: Uuid,
    pub persona_id: Uuid,
    pub sovereign_id: Uuid,
    pub agent_name: String,
    pub entry_reason: String,
    pub tier_at_entry: i16,
    pub tier_current: i16,
    pub weeks_elapsed: i32,
    pub entry_at: DateTime<Utc>,
    pub expected_exit_at: Option<DateTime<Utc>>,
    pub recovery_status: String,
    pub anomaly_count_in_recovery: i64,
    pub last_tier_increase_at: Option<DateTime<Utc>>,
    pub is_approved: bool, // Fail-closed: false by default until explicit approval
}

/// Paginated response for recovery status
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecoveryPageResponse {
    pub recoveries: Vec<RecoveryProjection>,
    pub total_count: i64,
    pub has_more: bool,
}

/// Fetch recovery status for agents in a sovereign
pub async fn fetch_recovery(
    pool: &PgPool,
    sovereign_id: Uuid,
    _status: Option<&str>,
    limit: Option<i32>,
) -> Result<RecoveryPageResponse, sqlx::Error> {
    let limit = limit.unwrap_or(25).min(100); // Cap at 100

    // Query recovery events from graph entities with sovereign guard and approval lock
    let recoveries = sqlx::query_as::<_, RecoveryProjection>(
        r#"
        SELECT
            ge.id as recovery_id,
            (ge.properties->>'persona_id')::uuid as persona_id,
            (ge.properties->>'sovereign_id')::uuid as sovereign_id,
            (ge.properties->>'agent_name') as agent_name,
            (ge.properties->>'entry_reason') as entry_reason,
            (ge.properties->>'tier_at_entry')::smallint as tier_at_entry,
            (ge.properties->>'tier_current')::smallint as tier_current,
            EXTRACT(WEEK FROM NOW() - (ge.properties->>'entry_at')::timestamptz)::int as weeks_elapsed,
            (ge.properties->>'entry_at')::timestamptz as entry_at,
            (ge.properties->>'expected_exit_at')::timestamptz as expected_exit_at,
            (ge.properties->>'recovery_status') as recovery_status,
            COALESCE((ge.properties->>'anomaly_count_in_recovery')::bigint, 0) as anomaly_count_in_recovery,
            (ge.properties->>'last_tier_increase_at')::timestamptz as last_tier_increase_at,
            COALESCE((ge.properties->>'is_approved')::boolean, false) as is_approved
        FROM graph_entities ge
        WHERE ge.label = 'RecoveryEventNode'
          AND (ge.properties->>'sovereign_id')::uuid = $1
          AND (ge.properties->>'sovereign_id') IS NOT NULL
          AND ge.created_at > NOW() - INTERVAL '90 days'
        ORDER BY ge.created_at DESC
        LIMIT $2
        "#,
    )
    .bind(sovereign_id)
    .bind(limit)
    .fetch_all(pool)
    .await?;

    // Get total count of active recoveries
    let total_count: i64 = sqlx::query_scalar(
        r#"
        SELECT COUNT(*)
        FROM graph_entities ge
        WHERE ge.label = 'RecoveryEventNode'
          AND (ge.properties->>'sovereign_id')::uuid = $1
          AND (ge.properties->>'sovereign_id') IS NOT NULL
        "#,
    )
    .bind(sovereign_id)
    .fetch_one(pool)
    .await?;

    let has_more = recoveries.len() as i32 >= limit;

    Ok(RecoveryPageResponse {
        recoveries,
        total_count,
        has_more,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    // Placeholder tests — full suite in projections_repo_tests.rs
    #[tokio::test]
    async fn test_agent_actions_projection_structure() {
        // Verify AgentActionProjection has required fields
        let _action = AgentActionProjection {
            action_id: Uuid::new_v4(),
            behavior_event_id: Uuid::new_v4(),
            session_id: Uuid::new_v4(),
            persona_id: Uuid::new_v4(),
            sovereign_id: Uuid::new_v4(),
            event_type: "test".to_string(),
            tier_before: 50,
            tier_after: 45,
            cost_incurred: 100,
            lineage_safe: true,
            scored_at: Utc::now(),
        };
    }

    #[test]
    fn test_anomaly_projection_structure() {
        let _anomaly = AnomalyProjection {
            anomaly_id: Uuid::new_v4(),
            anomaly_db_id: Uuid::new_v4(),
            sovereign_id: Uuid::new_v4(),
            persona_id: Some(Uuid::new_v4()),
            anomaly_type: "dispute_spam".to_string(),
            severity: "high".to_string(),
            event_count: 5,
            window_hours: 1,
            evidence: serde_json::json!({}),
            detected_at: Utc::now(),
            recovery_triggered: false,
            recovery_tier_impact: None,
        };
    }
}
