/// Phase 24 Task 1: Projections Repository Integration Tests
/// Tests for Agent Actions, Anomalies, and Recovery Status projection queries.
///
/// Test-Driven Development (GREEN phase): All tests implemented with testcontainers PostgreSQL.
/// Expected: 7 passing tests

#[cfg(test)]
mod tests {
    use crate::repo::projections_repo::{fetch_agent_actions, fetch_anomalies, fetch_recovery};
    use chrono::{Duration, Utc};
    use serde_json::json;
    use sqlx::PgPool;
    use testcontainers::runners::AsyncRunner;
    use testcontainers::{GenericImage, ImageExt, core::WaitFor};
    use uuid::Uuid;

    async fn setup_test_postgres() -> (
        testcontainers::ContainerAsync<testcontainers::GenericImage>,
        PgPool,
    ) {
        let container = GenericImage::new("postgres", "16")
            .with_wait_for(WaitFor::message_on_stderr(
                "database system is ready to accept connections",
            ))
            .with_env_var("POSTGRES_PASSWORD", "postgres")
            .with_env_var("POSTGRES_DB", "siss_test")
            .start()
            .await
            .expect("postgres started");

        let port = container.get_host_port_ipv4(5432).await.unwrap();
        let url = format!("postgres://postgres:postgres@127.0.0.1:{port}/siss_test");
        let pool = sqlx::PgPool::connect(&url).await.expect("pool connect");
        crate::migrations::run_all(&pool).await.expect("migrations");
        (container, pool)
    }

    // =====================================================================
    // TEST SUITE 1: Agent Actions Projection (Test 1.1)
    // =====================================================================

    #[tokio::test]
    async fn test_fetch_agent_actions_returns_empty_for_nonexistent_sovereign() {
        // GIVEN a sovereign_id that does not exist in graph_entities
        let (_container, pool) = setup_test_postgres().await;
        let nonexistent_id = Uuid::new_v4();

        // WHEN fetch_agent_actions() is called
        let result = fetch_agent_actions(&pool, &nonexistent_id, None, 100)
            .await
            .expect("query should not error");

        // THEN returns AgentActionPageResponse with empty actions[]
        assert_eq!(result.actions.len(), 0, "actions should be empty");
        assert_eq!(result.total_count, 0, "total_count should be 0");
        assert!(!result.has_more, "has_more should be false");
    }

    #[tokio::test]
    async fn test_fetch_agent_actions_returns_recent_actions_only() {
        // GIVEN 3 AgentActionNodes at different timestamps
        let (_container, pool) = setup_test_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let now = Utc::now();
        let recent = now - Duration::hours(1);
        let old = now - Duration::days(2);

        // Insert recent action
        let recent_action_id = Uuid::new_v4();
        sqlx::query(
            "INSERT INTO graph_entities (id, label, properties, created_at) VALUES ($1, 'AgentActionNode', $2, $3)"
        )
        .bind(recent_action_id)
        .bind(json!({
            "behavior_event_id": Uuid::new_v4().to_string(),
            "session_id": Uuid::new_v4().to_string(),
            "persona_id": Uuid::new_v4().to_string(),
            "sovereign_id": sovereign_id.to_string(),
            "event_type": "test",
            "tier_before": 50,
            "tier_after": 45,
            "cost_incurred": 100,
            "lineage_safe": true,
            "scored_at": recent.to_rfc3339(),
        }))
        .bind(recent)
        .execute(&pool)
        .await
        .expect("insert recent");

        // Insert old action
        let _old_action_id = Uuid::new_v4();
        sqlx::query(
            "INSERT INTO graph_entities (id, label, properties, created_at) VALUES ($1, 'AgentActionNode', $2, $3)"
        )
        .bind(Uuid::new_v4())
        .bind(json!({
            "behavior_event_id": Uuid::new_v4().to_string(),
            "session_id": Uuid::new_v4().to_string(),
            "persona_id": Uuid::new_v4().to_string(),
            "sovereign_id": sovereign_id.to_string(),
            "event_type": "test",
            "tier_before": 50,
            "tier_after": 45,
            "cost_incurred": 100,
            "lineage_safe": true,
            "scored_at": old.to_rfc3339(),
        }))
        .bind(old)
        .execute(&pool)
        .await
        .expect("insert old");

        // WHEN fetch_agent_actions with after_timestamp
        let result = fetch_agent_actions(&pool, &sovereign_id, Some(now - Duration::hours(2)), 100)
            .await
            .expect("query should not error");

        // THEN returns only recent action (within timestamp window)
        assert_eq!(result.actions.len(), 1, "should return only recent action");
        assert_eq!(result.total_count, 1);
        assert!(!result.has_more);
    }

    #[tokio::test]
    async fn test_e2e_agent_actions_with_phase23_ingestion() {
        // GIVEN a sovereign with 150 AgentActionNodes
        let (_container, pool) = setup_test_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let now = Utc::now();

        // Insert 150 AgentActionNodes
        for i in 0..150 {
            let node_id = Uuid::new_v4();
            let ts = now - Duration::seconds(i as i64);
            sqlx::query(
                "INSERT INTO graph_entities (id, label, properties, created_at) VALUES ($1, 'AgentActionNode', $2, $3)"
            )
            .bind(node_id)
            .bind(json!({
                "behavior_event_id": Uuid::new_v4().to_string(),
                "session_id": Uuid::new_v4().to_string(),
                "persona_id": Uuid::new_v4().to_string(),
                "sovereign_id": sovereign_id.to_string(),
                "event_type": "delegation",
                "tier_before": 50,
                "tier_after": 45,
                "cost_incurred": 100 * i as i64,
                "lineage_safe": true,
                "scored_at": ts.to_rfc3339(),
            }))
            .bind(ts)
            .execute(&pool)
            .await
            .expect("insert action");
        }

        // WHEN fetch with limit=100
        let result = fetch_agent_actions(&pool, &sovereign_id, None, 100)
            .await
            .expect("query should not error");

        // THEN returns exactly 100 actions, total=150, has_more=true
        assert_eq!(result.actions.len(), 100);
        assert_eq!(result.total_count, 150);
        assert!(result.has_more);
    }

    #[tokio::test]
    async fn test_fetch_agent_actions_caps_limit_at_500() {
        // GIVEN a sovereign with 600 actions
        let (_container, pool) = setup_test_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let now = Utc::now();

        for i in 0..600 {
            let node_id = Uuid::new_v4();
            let ts = now - Duration::seconds(i as i64);
            sqlx::query(
                "INSERT INTO graph_entities (id, label, properties, created_at) VALUES ($1, 'AgentActionNode', $2, $3)"
            )
            .bind(node_id)
            .bind(json!({
                "behavior_event_id": Uuid::new_v4().to_string(),
                "session_id": Uuid::new_v4().to_string(),
                "persona_id": Uuid::new_v4().to_string(),
                "sovereign_id": sovereign_id.to_string(),
                "event_type": "test",
                "tier_before": 50,
                "tier_after": 45,
                "cost_incurred": 100,
                "lineage_safe": true,
                "scored_at": ts.to_rfc3339(),
            }))
            .bind(ts)
            .execute(&pool)
            .await
            .expect("insert");
        }

        // WHEN fetch with limit=1000
        let result = fetch_agent_actions(&pool, &sovereign_id, None, 1000)
            .await
            .expect("query should not error");

        // THEN limit is clamped to 500
        assert_eq!(result.actions.len(), 500);
        assert_eq!(result.total_count, 600);
        assert!(result.has_more);
    }

    // =====================================================================
    // TEST SUITE 2: Anomaly Alerts Projection (Test 2.1)
    // =====================================================================

    #[tokio::test]
    async fn test_fetch_anomalies_returns_empty_for_nonexistent_sovereign() {
        // GIVEN sovereign_id that does not exist
        let (_container, pool) = setup_test_postgres().await;
        let nonexistent_id = Uuid::new_v4();

        // WHEN fetch_anomalies(sovereign_id, limit=100)
        let result = fetch_anomalies(
            &pool,
            &nonexistent_id,
            None, // severity
            None, // anomaly_type
            100,  // limit
        )
        .await
        .expect("query should not error");

        // THEN returns AnomalyPageResponse with empty anomalies[]
        assert_eq!(result.anomalies.len(), 0);
        assert_eq!(result.active_recovery_count, 0);
        assert_eq!(result.total_count, 0);
    }

    #[tokio::test]
    async fn test_e2e_anomalies_with_severity_filtering() {
        // GIVEN anomalies with mixed severities
        let (_container, pool) = setup_test_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let now = Utc::now();

        // Insert anomalies with different severities
        for (i, severity) in ["low", "medium", "high", "critical"].iter().enumerate() {
            let node_id = Uuid::new_v4();
            let ts = now - Duration::hours(i as i64);
            sqlx::query(
                "INSERT INTO graph_entities (id, label, properties, created_at) VALUES ($1, 'AnomalyEventNode', $2, $3)"
            )
            .bind(node_id)
            .bind(json!({
                "anomaly_db_id": Uuid::new_v4().to_string(),
                "sovereign_id": sovereign_id.to_string(),
                "anomaly_type": "test_anomaly",
                "severity": severity,
                "event_count": 5,
                "window_hours": 1,
                "evidence": {},
                "detected_at": ts.to_rfc3339(),
                "recovery_triggered": false,
            }))
            .bind(ts)
            .execute(&pool)
            .await
            .expect("insert");
        }

        // WHEN fetch_anomalies with severity="high"
        let result = fetch_anomalies(&pool, &sovereign_id, Some("high"), None, 100)
            .await
            .expect("query should not error");

        // THEN returns ONLY high and critical anomalies
        assert_eq!(
            result.anomalies.len(),
            2,
            "should return high and critical anomalies"
        );
    }

    #[tokio::test]
    async fn test_e2e_anomalies_with_type_filtering() {
        // GIVEN anomalies with mixed types
        let (_container, pool) = setup_test_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let now = Utc::now();

        // Insert 4 anomalies: 2 dispute_spam, 1 timeout_spam, 1 revocation_pattern
        for (i, atype) in vec![
            "dispute_spam",
            "dispute_spam",
            "timeout_spam",
            "revocation_pattern",
        ]
        .iter()
        .enumerate()
        {
            let node_id = Uuid::new_v4();
            let ts = now - Duration::hours(i as i64);
            sqlx::query(
                "INSERT INTO graph_entities (id, label, properties, created_at) VALUES ($1, 'AnomalyEventNode', $2, $3)"
            )
            .bind(node_id)
            .bind(json!({
                "anomaly_db_id": Uuid::new_v4().to_string(),
                "sovereign_id": sovereign_id.to_string(),
                "anomaly_type": atype,
                "severity": "high",
                "event_count": 5,
                "window_hours": 1,
                "evidence": {},
                "detected_at": ts.to_rfc3339(),
                "recovery_triggered": false,
            }))
            .bind(ts)
            .execute(&pool)
            .await
            .expect("insert");
        }

        // WHEN fetch_anomalies with type="dispute_spam"
        let result = fetch_anomalies(&pool, &sovereign_id, None, Some("dispute_spam"), 100)
            .await
            .expect("query should not error");

        // THEN returns exactly 2 dispute_spam anomalies
        assert_eq!(result.anomalies.len(), 2);
    }

    #[tokio::test]
    async fn test_fetch_anomalies_respects_7day_window() {
        // GIVEN anomalies at different timestamps
        let (_container, pool) = setup_test_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let now = Utc::now();

        // Insert anomalies at: 1 day ago, 7 days ago, 8 days ago, 30 days ago
        for (_i, days_offset) in vec![1, 7, 8, 30].iter().enumerate() {
            let node_id = Uuid::new_v4();
            let ts = now - Duration::days(*days_offset);
            sqlx::query(
                "INSERT INTO graph_entities (id, label, properties, created_at) VALUES ($1, 'AnomalyEventNode', $2, $3)"
            )
            .bind(node_id)
            .bind(json!({
                "anomaly_db_id": Uuid::new_v4().to_string(),
                "sovereign_id": sovereign_id.to_string(),
                "anomaly_type": "test",
                "severity": "high",
                "event_count": 5,
                "window_hours": 1,
                "evidence": {},
                "detected_at": ts.to_rfc3339(),
                "recovery_triggered": false,
            }))
            .bind(ts)
            .execute(&pool)
            .await
            .expect("insert");
        }

        // WHEN fetch_anomalies()
        let result = fetch_anomalies(&pool, &sovereign_id, None, None, 100)
            .await
            .expect("query should not error");

        // THEN returns only 1 and 7 day old anomalies (within 7-day window)
        assert_eq!(
            result.anomalies.len(),
            2,
            "should return only anomalies within 7 days"
        );
    }

    #[tokio::test]
    async fn test_fetch_anomalies_counts_active_recovery() {
        // GIVEN 3 AnomalyEventNodes with mixed recovery_triggered
        let (_container, pool) = setup_test_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let now = Utc::now();

        // Insert 3 anomalies: 2 with recovery_triggered=true, 1 with false
        for i in 0..3 {
            let node_id = Uuid::new_v4();
            let ts = now - Duration::hours(i as i64);
            let recovery_triggered = i < 2;
            sqlx::query(
                "INSERT INTO graph_entities (id, label, properties, created_at) VALUES ($1, 'AnomalyEventNode', $2, $3)"
            )
            .bind(node_id)
            .bind(json!({
                "anomaly_db_id": Uuid::new_v4().to_string(),
                "sovereign_id": sovereign_id.to_string(),
                "anomaly_type": "test",
                "severity": "high",
                "event_count": 5,
                "window_hours": 1,
                "evidence": {},
                "detected_at": ts.to_rfc3339(),
                "recovery_triggered": recovery_triggered,
            }))
            .bind(ts)
            .execute(&pool)
            .await
            .expect("insert");
        }

        // WHEN fetch_anomalies()
        let result = fetch_anomalies(&pool, &sovereign_id, None, None, 100)
            .await
            .expect("query should not error");

        // THEN active_recovery_count = 2
        assert_eq!(result.active_recovery_count, 2);
    }

    // =====================================================================
    // TEST SUITE 3: Recovery Status Projection (Test 3.1)
    // =====================================================================

    #[tokio::test]
    async fn test_fetch_recovery_returns_empty_for_nonexistent_sovereign() {
        // GIVEN nonexistent sovereign_id
        let (_container, pool) = setup_test_postgres().await;
        let nonexistent_id = Uuid::new_v4();

        // WHEN fetch_recovery(sovereign_id)
        let result = fetch_recovery(&pool, &nonexistent_id, 100)
            .await
            .expect("query should not error");

        // THEN returns RecoveryPageResponse with empty recoveries[]
        assert_eq!(result.recoveries.len(), 0);
        assert_eq!(result.total_count, 0);
    }

    #[tokio::test]
    async fn test_fetch_recovery_calculates_weeks_elapsed() {
        // GIVEN RecoveryNode entry_at = NOW() - 2 weeks
        let (_container, pool) = setup_test_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let now = Utc::now();
        let entry_at = now - Duration::weeks(2);

        let node_id = Uuid::new_v4();
        sqlx::query(
            "INSERT INTO graph_entities (id, label, properties, created_at) VALUES ($1, 'RecoveryNode', $2, $3)"
        )
        .bind(node_id)
        .bind(json!({
            "sovereign_id": sovereign_id.to_string(),
            "entry_at": entry_at.to_rfc3339(),
            "event_type": "probation_to_recovery",
            "tier_at_entry": 50,
            "tier_current": 45,
        }))
        .bind(entry_at)
        .execute(&pool)
        .await
        .expect("insert");

        // WHEN fetch_recovery()
        let result = fetch_recovery(&pool, &sovereign_id, 100)
            .await
            .expect("query should not error");

        // THEN weeks_elapsed = 2
        assert_eq!(result.recoveries.len(), 1);
        assert_eq!(result.recoveries[0].weeks_elapsed, 2);
    }

    #[tokio::test]
    async fn test_fetch_recovery_calculates_expected_exit_at_4weeks() {
        // GIVEN entry_at = NOW() - 1 week
        let (_container, pool) = setup_test_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let now = Utc::now();
        let entry_at = now - Duration::weeks(1);

        let node_id = Uuid::new_v4();
        sqlx::query(
            "INSERT INTO graph_entities (id, label, properties, created_at) VALUES ($1, 'RecoveryNode', $2, $3)"
        )
        .bind(node_id)
        .bind(json!({
            "sovereign_id": sovereign_id.to_string(),
            "entry_at": entry_at.to_rfc3339(),
            "event_type": "probation_to_recovery",
            "tier_at_entry": 50,
            "tier_current": 45,
        }))
        .bind(entry_at)
        .execute(&pool)
        .await
        .expect("insert");

        // WHEN fetch_recovery()
        let result = fetch_recovery(&pool, &sovereign_id, 100)
            .await
            .expect("query should not error");

        // THEN expected_exit_at = entry_at + 4 weeks
        assert_eq!(result.recoveries.len(), 1);
        let expected_exit = entry_at + Duration::weeks(4);
        assert_eq!(
            result.recoveries[0].expected_exit_at,
            Some(expected_exit),
            "expected_exit_at should be entry_at + 4 weeks"
        );
    }

    #[tokio::test]
    async fn test_e2e_recovery_with_state_transitions() {
        // GIVEN recovery events with different state transitions
        let (_container, pool) = setup_test_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let now = Utc::now();

        // Insert 3 recovery records with different event types
        for (i, event_type) in vec![
            "probation_to_recovery",
            "recovery_to_active",
            "recovery_to_quarantine",
        ]
        .iter()
        .enumerate()
        {
            let node_id = Uuid::new_v4();
            let entry_at = now - Duration::days(30 + i as i64);
            sqlx::query(
                "INSERT INTO graph_entities (id, label, properties, created_at) VALUES ($1, 'RecoveryNode', $2, $3)"
            )
            .bind(node_id)
            .bind(json!({
                "sovereign_id": sovereign_id.to_string(),
                "entry_at": entry_at.to_rfc3339(),
                "event_type": event_type,
                "tier_at_entry": 50,
                "tier_current": 45,
            }))
            .bind(entry_at)
            .execute(&pool)
            .await
            .expect("insert");
        }

        // WHEN fetch_recovery()
        let result = fetch_recovery(&pool, &sovereign_id, 100)
            .await
            .expect("query should not error");

        // THEN recovery_status correctly populated
        assert_eq!(result.recoveries.len(), 3);
        assert!(
            result
                .recoveries
                .iter()
                .any(|r| r.recovery_status == "in_progress"),
            "should have in_progress status"
        );
        assert!(
            result
                .recoveries
                .iter()
                .any(|r| r.recovery_status == "success"),
            "should have success status"
        );
        assert!(
            result
                .recoveries
                .iter()
                .any(|r| r.recovery_status == "failed"),
            "should have failed status"
        );
    }

    #[tokio::test]
    async fn test_fetch_recovery_respects_90day_lookback() {
        // GIVEN recoveries at: 30 days ago, 90 days ago, 91 days ago
        let (_container, pool) = setup_test_postgres().await;
        let sovereign_id = Uuid::new_v4();
        let now = Utc::now();

        for days_offset in vec![30, 90, 91].iter() {
            let node_id = Uuid::new_v4();
            let entry_at = now - Duration::days(*days_offset);
            sqlx::query(
                "INSERT INTO graph_entities (id, label, properties, created_at) VALUES ($1, 'RecoveryNode', $2, $3)"
            )
            .bind(node_id)
            .bind(json!({
                "sovereign_id": sovereign_id.to_string(),
                "entry_at": entry_at.to_rfc3339(),
                "event_type": "probation_to_recovery",
                "tier_at_entry": 50,
                "tier_current": 45,
            }))
            .bind(entry_at)
            .execute(&pool)
            .await
            .expect("insert");
        }

        // WHEN fetch_recovery()
        let result = fetch_recovery(&pool, &sovereign_id, 100)
            .await
            .expect("query should not error");

        // THEN returns only 30 and 90 day old records (within 90-day window)
        assert_eq!(
            result.recoveries.len(),
            2,
            "should return only anomalies within 90 days"
        );
    }
}
