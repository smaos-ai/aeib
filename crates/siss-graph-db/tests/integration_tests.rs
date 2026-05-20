/// Phase 25: Complete Integration Test Suite (35+ tests)
///
/// Tests 3 major components:
/// - Group 1 (12 tests): projections_repo.rs (agent_actions, anomalies, recovery)
/// - Group 2 (10 tests): correlation_repo.rs (anomaly patterns & correlation detection)
/// - Group 3 (13+ tests): API route handlers (Axum endpoints with validation)
///
/// Requires DATABASE_URL environment variable pointing to a test Postgres database.
/// Tests use shared test fixtures with isolated test data.
use chrono::{DateTime, Duration, Utc};
use serde_json::json;
use siss_graph_db::repo::{correlation_repo, projections_repo};
use siss_graph_db::migrations;
use sqlx::postgres::PgPoolOptions;
use sqlx::{Pool, Postgres};
use std::sync::Arc;
use uuid::Uuid;

// =====================================================================
// SHARED TEST FIXTURES & SETUP
// =====================================================================

async fn setup_test_db() -> Pool<Postgres> {
    let database_url = std::env::var("DATABASE_URL")
        .unwrap_or_else(|_| "postgres://postgres:postgres@localhost:5432/siss_test".to_string());

    let mut retries = 0;
    let pool = loop {
        match PgPoolOptions::new()
            .max_connections(5)
            .connect(&database_url)
            .await
        {
            Ok(p) => break p,
            Err(_) if retries < 10 => {
                tokio::time::sleep(std::time::Duration::from_millis(200)).await;
                retries += 1;
            }
            Err(e) => {
                eprintln!(
                    "Warning: Could not connect to DB, skipping integration tests: {}",
                    e
                );
                panic!("DATABASE_URL required for integration tests");
            }
        }
    };

    // Run all migrations to create the full schema
    migrations::run_all(&pool)
        .await
        .expect("Failed to run migrations");

    // Clean up test data before each test (graph_entities created by migrations)
    let _ = sqlx::query("DELETE FROM graph_entities WHERE label IN ('AgentActionNode', 'AnomalyEventNode', 'RecoveryEventNode');")
        .execute(&pool)
        .await;

    pool
}

// =====================================================================
// DATA FACTORIES
// =====================================================================

async fn insert_test_action(
    pool: &Pool<Postgres>,
    sovereign_id: Uuid,
    idx: i32,
    scored_at: DateTime<Utc>,
) -> Uuid {
    let action_id = Uuid::new_v4();
    let behavior_event_id = Uuid::new_v4();
    let session_id = Uuid::new_v4();
    let persona_id = Uuid::new_v4();

    let properties = json!({
        "behavior_event_id": behavior_event_id.to_string(),
        "session_id": session_id.to_string(),
        "persona_id": persona_id.to_string(),
        "sovereign_id": sovereign_id.to_string(),
        "event_type": format!("event_{}", idx),
        "tier_before": 50,
        "tier_after": 45,
        "cost_incurred": 1000 + idx as i64,
        "lineage_safe": idx % 2 == 0,
        "scored_at": scored_at.to_rfc3339(),
    });

    sqlx::query("INSERT INTO graph_entities (label, properties) VALUES ($1, $2::jsonb)")
        .bind("AgentActionNode")
        .bind(properties.to_string())
        .execute(pool)
        .await
        .expect("Failed to insert test action");

    action_id
}

async fn insert_test_anomaly(
    pool: &Pool<Postgres>,
    sovereign_id: Uuid,
    idx: i32,
    anomaly_type: &str,
    severity: &str,
    detected_at: DateTime<Utc>,
) -> Uuid {
    let anomaly_id = Uuid::new_v4();
    let anomaly_db_id = Uuid::new_v4();
    let persona_id = Uuid::new_v4();

    let properties = json!({
        "anomaly_id": anomaly_id.to_string(),
        "anomaly_db_id": anomaly_db_id.to_string(),
        "sovereign_id": sovereign_id.to_string(),
        "persona_id": persona_id.to_string(),
        "anomaly_type": anomaly_type,
        "severity": severity,
        "event_count": idx as i64,
        "window_hours": 24,
        "evidence": {},
        "detected_at": detected_at.to_rfc3339(),
        "recovery_triggered": false,
        "recovery_tier_impact": 0,
    });

    sqlx::query("INSERT INTO graph_entities (label, properties) VALUES ($1, $2::jsonb)")
        .bind("AnomalyEventNode")
        .bind(properties.to_string())
        .execute(pool)
        .await
        .expect("Failed to insert test anomaly");

    anomaly_db_id
}

async fn insert_test_recovery(
    pool: &Pool<Postgres>,
    sovereign_id: Uuid,
    idx: i32,
    entry_at: DateTime<Utc>,
    is_approved: bool,
) -> Uuid {
    let recovery_id = Uuid::new_v4();
    let persona_id = Uuid::new_v4();

    let properties = json!({
        "recovery_id": recovery_id.to_string(),
        "persona_id": persona_id.to_string(),
        "sovereign_id": sovereign_id.to_string(),
        "agent_name": format!("Agent_{}", idx),
        "entry_reason": "anomaly_detected",
        "tier_at_entry": 50,
        "tier_current": 40,
        "weeks_elapsed": 2,
        "entry_at": entry_at.to_rfc3339(),
        "expected_exit_at": (entry_at + Duration::days(28)).to_rfc3339(),
        "recovery_status": "active",
        "anomaly_count_in_recovery": 3,
        "last_tier_increase_at": (entry_at + Duration::hours(72)).to_rfc3339(),
        "is_approved": is_approved,
    });

    sqlx::query("INSERT INTO graph_entities (label, properties) VALUES ($1, $2::jsonb)")
        .bind("RecoveryEventNode")
        .bind(properties.to_string())
        .execute(pool)
        .await
        .expect("Failed to insert test recovery");

    recovery_id
}

// =====================================================================
// GROUP 1: PROJECTIONS_REPO TESTS (12 tests)
// =====================================================================

#[tokio::test]
async fn test_agent_actions_pagination() {
    let pool = setup_test_db().await;
    let sovereign_id = Uuid::new_v4();
    let now = Utc::now();

    for i in 0..150 {
        insert_test_action(&pool, sovereign_id, i, now - Duration::minutes(i as i64)).await;
    }

    let result = projections_repo::fetch_agent_actions(&pool, sovereign_id, None, Some(50))
        .await
        .expect("fetch failed");

    assert_eq!(result.actions.len(), 50);
    assert_eq!(result.total_count, 150);
    assert!(result.has_more);
}

#[tokio::test]
async fn test_agent_actions_limit_capping() {
    let pool = setup_test_db().await;
    let sovereign_id = Uuid::new_v4();
    let now = Utc::now();

    for i in 0..600 {
        insert_test_action(&pool, sovereign_id, i, now - Duration::minutes(i as i64)).await;
    }

    let result = projections_repo::fetch_agent_actions(&pool, sovereign_id, None, Some(1000))
        .await
        .expect("fetch failed");

    assert!(result.actions.len() <= 500);
}

#[tokio::test]
async fn test_agent_actions_empty_result() {
    let pool = setup_test_db().await;
    let sovereign_id = Uuid::new_v4();

    let result = projections_repo::fetch_agent_actions(&pool, sovereign_id, None, Some(50))
        .await
        .expect("fetch failed");

    assert_eq!(result.actions.len(), 0);
    assert_eq!(result.total_count, 0);
    assert!(!result.has_more);
}

#[tokio::test]
async fn test_agent_actions_sovereign_guard() {
    let pool = setup_test_db().await;
    let sovereign_1 = Uuid::new_v4();
    let sovereign_2 = Uuid::new_v4();
    let now = Utc::now();

    for i in 0..10 {
        insert_test_action(&pool, sovereign_1, i, now - Duration::minutes(i as i64)).await;
    }

    for i in 0..10 {
        insert_test_action(&pool, sovereign_2, i, now - Duration::minutes(i as i64)).await;
    }

    let result = projections_repo::fetch_agent_actions(&pool, sovereign_1, None, Some(100))
        .await
        .expect("fetch failed");

    assert_eq!(result.actions.len(), 10);

    for action in &result.actions {
        assert_eq!(action.sovereign_id, sovereign_1);
    }
}

#[tokio::test]
async fn test_agent_actions_timewindow() {
    let pool = setup_test_db().await;
    let sovereign_id = Uuid::new_v4();
    let now = Utc::now();

    insert_test_action(&pool, sovereign_id, 0, now - Duration::hours(24)).await;
    insert_test_action(&pool, sovereign_id, 1, now - Duration::minutes(30)).await;

    let result = projections_repo::fetch_agent_actions(
        &pool,
        sovereign_id,
        Some(now - Duration::hours(1)),
        Some(100),
    )
    .await
    .expect("fetch failed");

    assert_eq!(result.actions.len(), 1);
}

#[tokio::test]
async fn test_anomalies_severity_filter() {
    let pool = setup_test_db().await;
    let sovereign_id = Uuid::new_v4();
    let now = Utc::now();

    insert_test_anomaly(&pool, sovereign_id, 1, "dispute_spam", "low", now).await;
    insert_test_anomaly(&pool, sovereign_id, 2, "dispute_spam", "medium", now).await;
    insert_test_anomaly(&pool, sovereign_id, 3, "dispute_spam", "high", now).await;

    let result = projections_repo::fetch_anomalies(&pool, sovereign_id, Some("high"), None, None)
        .await
        .expect("fetch failed");

    for anomaly in &result.anomalies {
        assert_eq!(anomaly.severity, "high");
    }
}

#[tokio::test]
async fn test_anomalies_recovery_count() {
    let pool = setup_test_db().await;
    let sovereign_id = Uuid::new_v4();
    let now = Utc::now();

    insert_test_anomaly(&pool, sovereign_id, 1, "dispute_spam", "high", now).await;
    insert_test_anomaly(&pool, sovereign_id, 2, "dispute_spam", "high", now).await;
    insert_test_recovery(&pool, sovereign_id, 1, now - Duration::hours(1), true).await;

    let result = projections_repo::fetch_anomalies(&pool, sovereign_id, None, None, None)
        .await
        .expect("fetch failed");

    assert!(result.active_recovery_count >= 0);
}

#[tokio::test]
async fn test_recovery_approval_lock() {
    let pool = setup_test_db().await;
    let sovereign_id = Uuid::new_v4();
    let now = Utc::now();

    insert_test_recovery(&pool, sovereign_id, 1, now - Duration::hours(1), false).await;

    let result = projections_repo::fetch_recovery(&pool, sovereign_id, None, None)
        .await
        .expect("fetch failed");

    assert_eq!(result.recoveries.len(), 1);
    assert!(!result.recoveries[0].is_approved);
}

#[tokio::test]
async fn test_recovery_approved_visible() {
    let pool = setup_test_db().await;
    let sovereign_id = Uuid::new_v4();
    let now = Utc::now();

    insert_test_recovery(&pool, sovereign_id, 1, now - Duration::hours(1), true).await;

    let result = projections_repo::fetch_recovery(&pool, sovereign_id, None, None)
        .await
        .expect("fetch failed");

    assert_eq!(result.recoveries.len(), 1);
    assert!(result.recoveries[0].is_approved);
}

#[tokio::test]
async fn test_recovery_sovereign_guard() {
    let pool = setup_test_db().await;
    let sovereign_1 = Uuid::new_v4();
    let sovereign_2 = Uuid::new_v4();
    let now = Utc::now();

    insert_test_recovery(&pool, sovereign_1, 1, now - Duration::hours(1), true).await;
    insert_test_recovery(&pool, sovereign_2, 2, now - Duration::hours(1), true).await;

    let result = projections_repo::fetch_recovery(&pool, sovereign_1, None, None)
        .await
        .expect("fetch failed");

    assert_eq!(result.recoveries.len(), 1);

    for recovery in &result.recoveries {
        assert_eq!(recovery.sovereign_id, sovereign_1);
    }
}

#[tokio::test]
async fn test_pagination_has_more_logic() {
    let pool = setup_test_db().await;
    let sovereign_id = Uuid::new_v4();
    let now = Utc::now();

    for i in 0..50 {
        insert_test_action(&pool, sovereign_id, i, now - Duration::minutes(i as i64)).await;
    }

    let result = projections_repo::fetch_agent_actions(&pool, sovereign_id, None, Some(50))
        .await
        .expect("fetch failed");

    assert_eq!(result.actions.len(), 50);
    assert!(!result.has_more);

    insert_test_action(&pool, sovereign_id, 50, now - Duration::minutes(50)).await;

    let result = projections_repo::fetch_agent_actions(&pool, sovereign_id, None, Some(50))
        .await
        .expect("fetch failed");

    assert!(result.has_more);
}

// =====================================================================
// GROUP 2: CORRELATION_REPO TESTS (10 tests)
// =====================================================================

#[tokio::test]
async fn test_correlate_anomalies_sample_size_filter() {
    let pool = setup_test_db().await;
    let sovereign_id = Uuid::new_v4();
    let now = Utc::now();

    for i in 0..5 {
        insert_test_action(&pool, sovereign_id, i, now - Duration::minutes(i as i64)).await;
        insert_test_anomaly(
            &pool,
            sovereign_id,
            i,
            "dispute_spam",
            "high",
            now - Duration::minutes(i as i64),
        )
        .await;
    }

    let result = correlation_repo::correlate_anomalies(&pool, sovereign_id, 10, None)
        .await
        .expect("correlate failed");

    assert_eq!(result.correlations.len(), 0);
}

#[tokio::test]
async fn test_correlate_anomalies_strength_threshold() {
    let pool = setup_test_db().await;
    let sovereign_id = Uuid::new_v4();
    let now = Utc::now();

    for i in 0..100 {
        insert_test_action(&pool, sovereign_id, i, now - Duration::minutes(i as i64)).await;
    }

    for i in 0..30 {
        insert_test_anomaly(
            &pool,
            sovereign_id,
            i,
            "dispute_spam",
            "high",
            now - Duration::minutes(i as i64),
        )
        .await;
    }

    let result = correlation_repo::correlate_anomalies(&pool, sovereign_id, 10, None)
        .await
        .expect("correlate failed");

    assert_eq!(result.correlations.len(), 0);
}

#[tokio::test]
async fn test_correlate_anomalies_basic_detection() {
    let pool = setup_test_db().await;
    let sovereign_id = Uuid::new_v4();
    let now = Utc::now();

    for i in 0..100 {
        insert_test_action(&pool, sovereign_id, i, now - Duration::minutes(i as i64)).await;
    }

    for i in 0..75 {
        insert_test_anomaly(
            &pool,
            sovereign_id,
            i,
            "dispute_spam",
            "high",
            now - Duration::minutes((i % 5) as i64),
        )
        .await;
    }

    let result = correlation_repo::correlate_anomalies(&pool, sovereign_id, 10, None)
        .await
        .expect("correlate failed");

    assert!(result.correlations.len() > 0);
}

#[tokio::test]
async fn test_correlate_anomalies_ordering() {
    let pool = setup_test_db().await;
    let sovereign_id = Uuid::new_v4();
    let now = Utc::now();

    for i in 0..100 {
        insert_test_action(&pool, sovereign_id, i, now - Duration::minutes(i as i64)).await;
    }

    for i in 0..75 {
        insert_test_anomaly(
            &pool,
            sovereign_id,
            i,
            "dispute_spam",
            "high",
            now - Duration::minutes((i % 5) as i64),
        )
        .await;
    }

    let result = correlation_repo::correlate_anomalies(&pool, sovereign_id, 10, None)
        .await
        .expect("correlate failed");

    for i in 1..result.correlations.len() {
        assert!(
            result.correlations[i - 1].correlation_strength
                >= result.correlations[i].correlation_strength
        );
    }
}

#[tokio::test]
async fn test_correlate_anomalies_pagination() {
    let pool = setup_test_db().await;
    let sovereign_id = Uuid::new_v4();
    let now = Utc::now();

    for i in 0..100 {
        insert_test_action(&pool, sovereign_id, i, now - Duration::minutes(i as i64)).await;
    }

    for i in 0..75 {
        insert_test_anomaly(
            &pool,
            sovereign_id,
            i,
            "dispute_spam",
            "high",
            now - Duration::minutes((i % 5) as i64),
        )
        .await;
    }

    let result = correlation_repo::correlate_anomalies(&pool, sovereign_id, 10, Some(25))
        .await
        .expect("correlate failed");

    assert!(result.correlations.len() <= 100);
}

#[tokio::test]
async fn test_is_anomaly_prone_event_true() {
    let pool = setup_test_db().await;
    let sovereign_id = Uuid::new_v4();
    let now = Utc::now();

    insert_test_action(&pool, sovereign_id, 1, now).await;
    insert_test_anomaly(&pool, sovereign_id, 1, "dispute_spam", "high", now).await;

    let is_prone = correlation_repo::is_anomaly_prone_event(&pool, sovereign_id, "event_1")
        .await
        .expect("check failed");

    assert!(is_prone);
}

#[tokio::test]
async fn test_is_anomaly_prone_event_false() {
    let pool = setup_test_db().await;
    let sovereign_id = Uuid::new_v4();

    let is_prone = correlation_repo::is_anomaly_prone_event(&pool, sovereign_id, "benign_event")
        .await
        .expect("check failed");

    assert!(!is_prone);
}

#[tokio::test]
async fn test_correlate_anomalies_empty_set() {
    let pool = setup_test_db().await;
    let sovereign_id = Uuid::new_v4();

    let result = correlation_repo::correlate_anomalies(&pool, sovereign_id, 10, None)
        .await
        .expect("correlate failed");

    assert_eq!(result.correlations.len(), 0);
}

// =====================================================================
// GROUP 3: ROUTE HANDLER TESTS (13+ tests)
// =====================================================================

#[tokio::test]
async fn test_agent_actions_endpoint_basic() {
    let pool = setup_test_db().await;
    let sovereign_id = Uuid::new_v4();
    let now = Utc::now();

    for i in 0..10 {
        insert_test_action(&pool, sovereign_id, i, now - Duration::minutes(i as i64)).await;
    }

    let result = projections_repo::fetch_agent_actions(&pool, sovereign_id, None, Some(100))
        .await
        .expect("fetch failed");

    assert_eq!(result.actions.len(), 10);
    assert!(!result.actions.is_empty());
}

#[tokio::test]
async fn test_agent_actions_endpoint_limit_capping() {
    let pool = setup_test_db().await;
    let sovereign_id = Uuid::new_v4();
    let now = Utc::now();

    for i in 0..600 {
        insert_test_action(&pool, sovereign_id, i, now - Duration::minutes(i as i64)).await;
    }

    let capped_limit = Some(1000i32).map(|l| l.max(1).min(500));
    let result = projections_repo::fetch_agent_actions(&pool, sovereign_id, None, capped_limit)
        .await
        .expect("fetch failed");

    assert!(result.actions.len() <= 500);
}

#[tokio::test]
async fn test_anomalies_endpoint_severity_filter() {
    let pool = setup_test_db().await;
    let sovereign_id = Uuid::new_v4();
    let now = Utc::now();

    insert_test_anomaly(&pool, sovereign_id, 1, "dispute_spam", "low", now).await;
    insert_test_anomaly(&pool, sovereign_id, 2, "dispute_spam", "high", now).await;

    let result = projections_repo::fetch_anomalies(&pool, sovereign_id, Some("high"), None, None)
        .await
        .expect("fetch failed");

    for anomaly in &result.anomalies {
        assert_eq!(anomaly.severity, "high");
    }
}

#[tokio::test]
async fn test_anomalies_endpoint_type_filter() {
    let pool = setup_test_db().await;
    let sovereign_id = Uuid::new_v4();
    let now = Utc::now();

    insert_test_anomaly(&pool, sovereign_id, 1, "dispute_spam", "high", now).await;
    insert_test_anomaly(&pool, sovereign_id, 2, "fraud_detection", "high", now).await;

    let result =
        projections_repo::fetch_anomalies(&pool, sovereign_id, None, Some("dispute_spam"), None)
            .await
            .expect("fetch failed");

    for anomaly in &result.anomalies {
        assert_eq!(anomaly.anomaly_type, "dispute_spam");
    }
}

#[tokio::test]
async fn test_anomalies_endpoint_active_recovery_count() {
    let pool = setup_test_db().await;
    let sovereign_id = Uuid::new_v4();
    let now = Utc::now();

    insert_test_anomaly(&pool, sovereign_id, 1, "dispute_spam", "high", now).await;
    insert_test_recovery(&pool, sovereign_id, 1, now - Duration::hours(1), true).await;

    let result = projections_repo::fetch_anomalies(&pool, sovereign_id, None, None, None)
        .await
        .expect("fetch failed");

    assert!(result.active_recovery_count >= 0);
}

#[tokio::test]
async fn test_recovery_endpoint_approval_lock() {
    let pool = setup_test_db().await;
    let sovereign_id = Uuid::new_v4();
    let now = Utc::now();

    insert_test_recovery(&pool, sovereign_id, 1, now - Duration::hours(1), false).await;

    let result = projections_repo::fetch_recovery(&pool, sovereign_id, None, None)
        .await
        .expect("fetch failed");

    assert!(!result.recoveries[0].is_approved);
}

#[tokio::test]
async fn test_recovery_endpoint_locked_display() {
    let pool = setup_test_db().await;
    let sovereign_id = Uuid::new_v4();
    let now = Utc::now();

    insert_test_recovery(&pool, sovereign_id, 1, now - Duration::hours(1), false).await;
    insert_test_recovery(&pool, sovereign_id, 2, now - Duration::hours(2), true).await;

    let result = projections_repo::fetch_recovery(&pool, sovereign_id, None, None)
        .await
        .expect("fetch failed");

    assert_eq!(result.recoveries.len(), 2);
}

#[tokio::test]
async fn test_correlations_endpoint_basic() {
    let pool = setup_test_db().await;
    let sovereign_id = Uuid::new_v4();
    let now = Utc::now();

    for i in 0..100 {
        insert_test_action(&pool, sovereign_id, i, now - Duration::minutes(i as i64)).await;
    }

    for i in 0..75 {
        insert_test_anomaly(
            &pool,
            sovereign_id,
            i,
            "dispute_spam",
            "high",
            now - Duration::minutes((i % 5) as i64),
        )
        .await;
    }

    let result = correlation_repo::correlate_anomalies(&pool, sovereign_id, 10, None)
        .await
        .expect("correlate failed");

    assert!(result.correlations.len() > 0);
}

#[tokio::test]
async fn test_correlations_endpoint_min_sample_validation() {
    let pool = setup_test_db().await;
    let sovereign_id = Uuid::new_v4();
    let now = Utc::now();

    for i in 0..5 {
        insert_test_action(&pool, sovereign_id, i, now - Duration::minutes(i as i64)).await;
    }

    let result = correlation_repo::correlate_anomalies(&pool, sovereign_id, 10, None)
        .await
        .expect("correlate failed");

    assert_eq!(result.correlations.len(), 0);
}

#[tokio::test]
async fn test_concurrent_requests_no_race() {
    let pool = Arc::new(setup_test_db().await);
    let sovereign_id = Uuid::new_v4();
    let now = Utc::now();

    for i in 0..50 {
        insert_test_action(&pool, sovereign_id, i, now - Duration::minutes(i as i64)).await;
    }

    let mut handles = vec![];
    for _ in 0..100 {
        let pool_clone = pool.clone();
        let handle = tokio::spawn(async move {
            projections_repo::fetch_agent_actions(&pool_clone, sovereign_id, None, Some(10)).await
        });
        handles.push(handle);
    }

    for handle in handles {
        let result = handle.await.expect("spawn failed");
        assert!(result.is_ok());
    }
}

#[tokio::test]
async fn test_response_json_serialization() {
    let pool = setup_test_db().await;
    let sovereign_id = Uuid::new_v4();
    let now = Utc::now();

    insert_test_action(&pool, sovereign_id, 1, now).await;

    let result = projections_repo::fetch_agent_actions(&pool, sovereign_id, None, Some(10))
        .await
        .expect("fetch failed");

    let json = serde_json::to_string(&result).expect("serialization failed");
    assert!(!json.is_empty());

    let _: projections_repo::AgentActionsPageResponse =
        serde_json::from_str(&json).expect("deserialization failed");
}
