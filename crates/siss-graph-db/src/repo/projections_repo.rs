use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;
use sqlx::PgPool;

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
pub struct AgentActionPageResponse {
    pub actions: Vec<AgentActionProjection>,
    pub total_count: i64,
    pub has_more: bool,
    pub generated_at: String,
}

/// Fetch recent agent actions paginated
pub async fn fetch_agent_actions(
    pool: &PgPool,
    sovereign_id: &Uuid,
    after_timestamp: Option<DateTime<Utc>>,
    limit: i32,
) -> Result<AgentActionPageResponse, sqlx::Error> {
    let limit = limit.min(500); // Cap at 500
    let generated_at = chrono::Utc::now().to_rfc3339();

    // First, count total matching records
    let total_count: (i64,) = if let Some(ts) = after_timestamp {
        sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities
             WHERE label = 'AgentActionNode'
             AND properties->>'sovereign_id' = $1
             AND created_at > $2
             AND properties->>'sovereign_id' IS NOT NULL"
        )
        .bind(sovereign_id.to_string())
        .bind(ts)
        .fetch_one(pool)
        .await?
    } else {
        sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities
             WHERE label = 'AgentActionNode'
             AND properties->>'sovereign_id' = $1
             AND properties->>'sovereign_id' IS NOT NULL"
        )
        .bind(sovereign_id.to_string())
        .fetch_one(pool)
        .await?
    };

    // Fetch the paginated results
    let rows = if let Some(ts) = after_timestamp {
        sqlx::query_as::<_, (Uuid, serde_json::Value, DateTime<Utc>)>(
            "SELECT id, properties, created_at FROM graph_entities
             WHERE label = 'AgentActionNode'
             AND properties->>'sovereign_id' = $1
             AND created_at > $2
             AND properties->>'sovereign_id' IS NOT NULL
             ORDER BY created_at DESC
             LIMIT $3"
        )
        .bind(sovereign_id.to_string())
        .bind(ts)
        .bind(limit as i64)
        .fetch_all(pool)
        .await?
    } else {
        sqlx::query_as::<_, (Uuid, serde_json::Value, DateTime<Utc>)>(
            "SELECT id, properties, created_at FROM graph_entities
             WHERE label = 'AgentActionNode'
             AND properties->>'sovereign_id' = $1
             AND properties->>'sovereign_id' IS NOT NULL
             ORDER BY created_at DESC
             LIMIT $2"
        )
        .bind(sovereign_id.to_string())
        .bind(limit as i64)
        .fetch_all(pool)
        .await?
    };

    // Deserialize rows into AgentActionProjection
    let actions: Vec<AgentActionProjection> = rows
        .into_iter()
        .filter_map(|(id, properties, _created_at)| {
            let behavior_event_id = properties.get("behavior_event_id")
                .and_then(|v| v.as_str())
                .and_then(|s| Uuid::parse_str(s).ok())?;
            let session_id = properties.get("session_id")
                .and_then(|v| v.as_str())
                .and_then(|s| Uuid::parse_str(s).ok())?;
            let persona_id = properties.get("persona_id")
                .and_then(|v| v.as_str())
                .and_then(|s| Uuid::parse_str(s).ok())?;
            let event_type = properties.get("event_type")
                .and_then(|v| v.as_str())
                .unwrap_or("unknown")
                .to_string();
            let tier_before = properties.get("tier_before")
                .and_then(|v| v.as_i64())
                .unwrap_or(0) as i16;
            let tier_after = properties.get("tier_after")
                .and_then(|v| v.as_i64())
                .unwrap_or(0) as i16;
            let cost_incurred = properties.get("cost_incurred")
                .and_then(|v| v.as_i64())
                .unwrap_or(0);
            let lineage_safe = properties.get("lineage_safe")
                .and_then(|v| v.as_bool())
                .unwrap_or(false);
            let scored_at = properties.get("scored_at")
                .and_then(|v| v.as_str())
                .and_then(|s| DateTime::parse_from_rfc3339(s).ok())
                .map(|dt| dt.with_timezone(&Utc))?;

            Some(AgentActionProjection {
                action_id: id,
                behavior_event_id,
                session_id,
                persona_id,
                sovereign_id: *sovereign_id,
                event_type,
                tier_before,
                tier_after,
                cost_incurred,
                lineage_safe,
                scored_at,
            })
        })
        .collect();

    let has_more = total_count.0 > limit as i64;

    Ok(AgentActionPageResponse {
        actions,
        total_count: total_count.0,
        has_more,
        generated_at,
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
pub struct AnomalyPageResponse {
    pub anomalies: Vec<AnomalyProjection>,
    pub total_count: i64,
    pub has_more: bool,
    pub active_recovery_count: i32,
    pub generated_at: String,
}

/// Fetch anomalies with optional filtering
pub async fn fetch_anomalies(
    pool: &PgPool,
    sovereign_id: &Uuid,
    severity: Option<&str>,
    anomaly_type: Option<&str>,
    limit: i32,
) -> Result<AnomalyPageResponse, sqlx::Error> {
    let limit = limit.min(500); // Cap at 500
    let generated_at = chrono::Utc::now().to_rfc3339();
    // Include records from the last 7 days (add 1 second buffer for clock skew)
    let seven_days_ago = Utc::now() - chrono::Duration::days(7) - chrono::Duration::seconds(1);

    // Build base WHERE clause
    let mut where_clause = "label = 'AnomalyEventNode' AND properties->>'sovereign_id' = $1 AND created_at > $2".to_string();

    // Severity filter: high or critical
    if let Some(sev) = severity {
        let sev_lower = sev.to_lowercase();
        if sev_lower == "high" || sev_lower == "critical" {
            where_clause.push_str(" AND (properties->>'severity' = 'high' OR properties->>'severity' = 'critical')");
        }
    }

    // Anomaly type filter
    if anomaly_type.is_some() {
        where_clause.push_str(" AND properties->>'anomaly_type' = $3");
    }

    // Count total
    let count_query = format!("SELECT COUNT(*) FROM graph_entities WHERE {}", where_clause);
    let total_count: (i64,) = if anomaly_type.is_some() {
        sqlx::query_as(&count_query)
            .bind(sovereign_id.to_string())
            .bind(seven_days_ago)
            .bind(anomaly_type)
            .fetch_one(pool)
            .await?
    } else {
        sqlx::query_as(&count_query)
            .bind(sovereign_id.to_string())
            .bind(seven_days_ago)
            .fetch_one(pool)
            .await?
    };

    // Fetch paginated results
    let fetch_query = format!(
        "SELECT id, properties, created_at FROM graph_entities WHERE {} ORDER BY created_at DESC LIMIT {}",
        where_clause, limit
    );
    let rows: Vec<(Uuid, serde_json::Value, DateTime<Utc>)> = if anomaly_type.is_some() {
        sqlx::query_as(&fetch_query)
            .bind(sovereign_id.to_string())
            .bind(seven_days_ago)
            .bind(anomaly_type)
            .fetch_all(pool)
            .await?
    } else {
        sqlx::query_as(&fetch_query)
            .bind(sovereign_id.to_string())
            .bind(seven_days_ago)
            .fetch_all(pool)
            .await?
    };

    // Deserialize rows
    let anomalies: Vec<AnomalyProjection> = rows
        .into_iter()
        .filter_map(|(id, properties, _)| {
            let anomaly_db_id = properties.get("anomaly_db_id")
                .and_then(|v| v.as_str())
                .and_then(|s| Uuid::parse_str(s).ok())?;
            let anom_type = properties.get("anomaly_type")
                .and_then(|v| v.as_str())
                .unwrap_or("unknown")
                .to_string();
            let sev = properties.get("severity")
                .and_then(|v| v.as_str())
                .unwrap_or("advisory")
                .to_string();
            let event_count = properties.get("event_count")
                .and_then(|v| v.as_i64())
                .unwrap_or(0);
            let window_hours = properties.get("window_hours")
                .and_then(|v| v.as_i64())
                .unwrap_or(1);
            let evidence = properties.get("evidence")
                .cloned()
                .unwrap_or_else(|| serde_json::json!({}));
            let detected_at = properties.get("detected_at")
                .and_then(|v| v.as_str())
                .and_then(|s| DateTime::parse_from_rfc3339(s).ok())
                .map(|dt| dt.with_timezone(&Utc))?;
            let recovery_triggered = properties.get("recovery_triggered")
                .and_then(|v| v.as_bool())
                .unwrap_or(false);
            let recovery_tier_impact = properties.get("recovery_tier_impact")
                .and_then(|v| v.as_i64())
                .map(|n| n as i16);

            Some(AnomalyProjection {
                anomaly_id: id,
                anomaly_db_id,
                sovereign_id: *sovereign_id,
                persona_id: None,
                anomaly_type: anom_type,
                severity: sev,
                event_count,
                window_hours,
                evidence,
                detected_at,
                recovery_triggered,
                recovery_tier_impact,
            })
        })
        .collect();

    // Count active recovery (recovery_triggered = true)
    let active_recovery_count: (i64,) = sqlx::query_as(
        "SELECT COUNT(*) FROM graph_entities
         WHERE label = 'AnomalyEventNode'
         AND properties->>'sovereign_id' = $1
         AND properties->>'recovery_triggered' = 'true'
         AND created_at > $2"
    )
    .bind(sovereign_id.to_string())
    .bind(seven_days_ago)
    .fetch_one(pool)
    .await?;

    let has_more = total_count.0 > limit as i64;

    Ok(AnomalyPageResponse {
        anomalies,
        total_count: total_count.0,
        has_more,
        active_recovery_count: active_recovery_count.0 as i32,
        generated_at,
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
    pub generated_at: String,
}

/// Fetch recovery status for agents in a sovereign
pub async fn fetch_recovery(
    pool: &PgPool,
    sovereign_id: &Uuid,
    limit: i32,
) -> Result<RecoveryPageResponse, sqlx::Error> {
    let limit = limit.min(200); // Cap at 200 for recovery
    let generated_at = chrono::Utc::now().to_rfc3339();
    // Include records from the last 90 days (add 1 second buffer for clock skew)
    let ninety_days_ago = Utc::now() - chrono::Duration::days(90) - chrono::Duration::seconds(1);

    // Count total recovery records
    let total_count: (i64,) = sqlx::query_as(
        "SELECT COUNT(*) FROM graph_entities
         WHERE label = 'RecoveryNode'
         AND properties->>'sovereign_id' = $1
         AND created_at > $2"
    )
    .bind(sovereign_id.to_string())
    .bind(ninety_days_ago)
    .fetch_one(pool)
    .await?;

    // Fetch recovery nodes
    let rows: Vec<(Uuid, serde_json::Value)> = sqlx::query_as(
        "SELECT id, properties FROM graph_entities
         WHERE label = 'RecoveryNode'
         AND properties->>'sovereign_id' = $1
         AND created_at > $2
         ORDER BY created_at DESC
         LIMIT $3"
    )
    .bind(sovereign_id.to_string())
    .bind(ninety_days_ago)
    .bind(limit as i64)
    .fetch_all(pool)
    .await?;

    // Deserialize rows
    let recoveries: Vec<RecoveryProjection> = rows
        .into_iter()
        .filter_map(|(id, properties)| {
            let entry_at = properties.get("entry_at")
                .and_then(|v| v.as_str())
                .and_then(|s| DateTime::parse_from_rfc3339(s).ok())
                .map(|dt| dt.with_timezone(&Utc))?;

            // Calculate weeks elapsed
            let now = Utc::now();
            let duration = now.signed_duration_since(entry_at);
            let weeks_elapsed = (duration.num_seconds() / (7 * 24 * 3600)) as i32;

            // Expected exit is 4 weeks from entry
            let expected_exit_at = Some(entry_at + chrono::Duration::weeks(4));

            let tier_at_entry = properties.get("tier_at_entry")
                .and_then(|v| v.as_i64())
                .unwrap_or(0) as i16;

            let tier_current = properties.get("tier_current")
                .and_then(|v| v.as_i64())
                .map(|n| n as i16)
                .or_else(|| properties.get("current_tier")
                    .and_then(|v| v.as_i64())
                    .map(|n| n as i16))
                .unwrap_or(tier_at_entry);

            let event_type = properties.get("event_type")
                .and_then(|v| v.as_str())
                .unwrap_or("probation_to_recovery");

            // Determine recovery status
            let recovery_status = match event_type {
                "probation_to_recovery" => "in_progress".to_string(),
                "recovery_to_active" => "success".to_string(),
                "recovery_to_quarantine" => "failed".to_string(),
                _ => "unknown".to_string(),
            };

            Some(RecoveryProjection {
                recovery_id: id,
                persona_id: Uuid::new_v4(), // Placeholder until we have proper tracking
                sovereign_id: *sovereign_id,
                agent_name: "Agent".to_string(), // Placeholder until we have proper tracking
                entry_reason: "Recovery entry".to_string(),
                tier_at_entry,
                tier_current,
                weeks_elapsed,
                entry_at,
                expected_exit_at,
                recovery_status,
                anomaly_count_in_recovery: 0,
                last_tier_increase_at: None,
                is_approved: false, // Fail-closed
            })
        })
        .collect();

    let has_more = total_count.0 > limit as i64;

    Ok(RecoveryPageResponse {
        recoveries,
        total_count: total_count.0,
        has_more,
        generated_at,
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

    // All integration tests moved to projections_repo_integration_tests.rs
    // Unit tests only: structure verification
}
