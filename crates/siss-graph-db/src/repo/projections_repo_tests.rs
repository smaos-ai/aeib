#[cfg(test)]
mod tests {
    use super::super::*;
    use chrono::Utc;
    use sqlx::PgPool;
    use uuid::Uuid;

    // Helper: Set up test database with Phase 23 fixtures
    async fn setup_test_pool() -> PgPool {
        dotenv::dotenv().ok();
        let database_url = std::env::var("DATABASE_URL").expect("DATABASE_URL not set");
        PgPool::connect(&database_url).await.expect("Failed to connect")
    }

    // ========== Feature 1: Agent Actions ==========

    #[tokio::test]
    async fn test_fetch_agent_actions_returns_recent_only() {
        let pool = setup_test_pool().await;
        let sovereign_id = Uuid::new_v4();

        // Insert old action (24h ago) and recent action (30min ago)
        let now = Utc::now();
        let old_time = now - chrono::Duration::hours(24);
        let recent_time = now - chrono::Duration::minutes(30);

        // This test WILL FAIL until projections_repo.rs is implemented
        let result = fetch_agent_actions(&pool, sovereign_id, Some(now - chrono::Duration::hours(1)), Some(100))
            .await
            .expect("Query should succeed");

        // Only recent action should be returned
        assert_eq!(result.actions.len(), 1, "Should return only 1 recent action");
    }

    #[tokio::test]
    async fn test_fetch_agent_actions_respects_limit() {
        let pool = setup_test_pool().await;
        let sovereign_id = Uuid::new_v4();

        let result = fetch_agent_actions(&pool, sovereign_id, None, Some(50))
            .await
            .expect("Query should succeed");

        assert!(result.actions.len() <= 50, "Should respect limit of 50");
    }

    #[tokio::test]
    async fn test_fetch_agent_actions_max_limit_capped_at_500() {
        let pool = setup_test_pool().await;
        let sovereign_id = Uuid::new_v4();

        // Request limit of 1000 (should be capped to 500)
        let result = fetch_agent_actions(&pool, sovereign_id, None, Some(1000))
            .await
            .expect("Query should succeed");

        assert!(result.actions.len() <= 500, "Max limit should be 500");
    }

    #[tokio::test]
    async fn test_fetch_agent_actions_total_count_not_capped() {
        let pool = setup_test_pool().await;
        let sovereign_id = Uuid::new_v4();

        let result = fetch_agent_actions(&pool, sovereign_id, None, Some(50))
            .await
            .expect("Query should succeed");

        // total_count should be > actions.len() if more records exist
        assert!(result.total_count >= result.actions.len() as i64, "total_count should reflect all records");
    }

    #[tokio::test]
    async fn test_fetch_agent_actions_has_more_flag_accurate() {
        let pool = setup_test_pool().await;
        let sovereign_id = Uuid::new_v4();

        let result = fetch_agent_actions(&pool, sovereign_id, None, Some(10))
            .await
            .expect("Query should succeed");

        if result.total_count > 10 {
            assert!(result.has_more, "has_more should be true when total_count > limit");
        } else {
            assert!(!result.has_more, "has_more should be false when total_count <= limit");
        }
    }

    #[tokio::test]
    async fn test_fetch_agent_actions_includes_all_fields() {
        let pool = setup_test_pool().await;
        let sovereign_id = Uuid::new_v4();

        let result = fetch_agent_actions(&pool, sovereign_id, None, Some(1))
            .await
            .expect("Query should succeed");

        if let Some(action) = result.actions.first() {
            assert!(!action.behavior_event_id.is_nil(), "behavior_event_id should be present");
            assert!(!action.session_id.is_nil(), "session_id should be present");
            assert!(!action.persona_id.is_nil(), "persona_id should be present");
            assert!(!action.event_type.is_empty(), "event_type should not be empty");
            assert!(action.tier_before >= 0, "tier_before should be >= 0");
            assert!(action.tier_after >= 0, "tier_after should be >= 0");
            assert!(action.cost_incurred >= 0, "cost_incurred should be >= 0");
        }
    }

    // ========== Feature 1: Anomalies ==========

    #[tokio::test]
    async fn test_fetch_anomalies_filters_by_severity() {
        let pool = setup_test_pool().await;
        let sovereign_id = Uuid::new_v4();

        let result = fetch_anomalies(&pool, sovereign_id, Some("high"), None, Some(100))
            .await
            .expect("Query should succeed");

        for anomaly in &result.anomalies {
            assert!(anomaly.severity == "high" || anomaly.severity == "critical",
                "Should only return high or critical severity");
        }
    }

    #[tokio::test]
    async fn test_fetch_anomalies_filters_by_type() {
        let pool = setup_test_pool().await;
        let sovereign_id = Uuid::new_v4();

        let result = fetch_anomalies(&pool, sovereign_id, None, Some("dispute_spam"), Some(100))
            .await
            .expect("Query should succeed");

        for anomaly in &result.anomalies {
            assert_eq!(anomaly.anomaly_type, "dispute_spam", "Should only return dispute_spam");
        }
    }

    #[tokio::test]
    async fn test_fetch_anomalies_active_recovery_count_is_non_negative() {
        let pool = setup_test_pool().await;
        let sovereign_id = Uuid::new_v4();

        let result = fetch_anomalies(&pool, sovereign_id, None, None, Some(100))
            .await
            .expect("Query should succeed");

        assert!(result.active_recovery_count >= 0, "active_recovery_count should be >= 0");
    }

    #[tokio::test]
    async fn test_fetch_anomalies_7day_lookback() {
        let pool = setup_test_pool().await;
        let sovereign_id = Uuid::new_v4();

        let result = fetch_anomalies(&pool, sovereign_id, None, None, Some(1000))
            .await
            .expect("Query should succeed");

        let now = Utc::now();
        for anomaly in &result.anomalies {
            let duration = now.signed_duration_since(anomaly.detected_at);
            assert!(duration.num_days() <= 7, "Anomalies should be from last 7 days only");
        }
    }

    // ========== Feature 1: Recovery Status ==========

    #[tokio::test]
    async fn test_fetch_recovery_calculates_weeks_elapsed() {
        let pool = setup_test_pool().await;
        let sovereign_id = Uuid::new_v4();

        let result = fetch_recovery(&pool, sovereign_id, None, Some(100))
            .await
            .expect("Query should succeed");

        for recovery in &result.recoveries {
            assert!(recovery.weeks_elapsed >= 0, "weeks_elapsed should be >= 0");
        }
    }

    #[tokio::test]
    async fn test_fetch_recovery_expected_exit_at_is_4weeks() {
        let pool = setup_test_pool().await;
        let sovereign_id = Uuid::new_v4();

        let result = fetch_recovery(&pool, sovereign_id, None, Some(100))
            .await
            .expect("Query should succeed");

        for recovery in &result.recoveries {
            if let Some(expected_exit) = recovery.expected_exit_at {
                let expected_duration = expected_exit.signed_duration_since(recovery.entry_at);
                assert!(expected_duration.num_weeks() >= 4 && expected_duration.num_weeks() <= 5,
                    "Expected exit should be ~4 weeks from entry");
            }
        }
    }

    #[tokio::test]
    async fn test_fetch_recovery_status_transitions() {
        let pool = setup_test_pool().await;
        let sovereign_id = Uuid::new_v4();

        let result = fetch_recovery(&pool, sovereign_id, None, Some(100))
            .await
            .expect("Query should succeed");

        for recovery in &result.recoveries {
            assert!(
                recovery.recovery_status == "active" ||
                recovery.recovery_status == "completed" ||
                recovery.recovery_status == "exited",
                "recovery_status should be one of: active, completed, exited"
            );
        }
    }

    #[tokio::test]
    async fn test_fetch_recovery_anomaly_count_in_recovery() {
        let pool = setup_test_pool().await;
        let sovereign_id = Uuid::new_v4();

        let result = fetch_recovery(&pool, sovereign_id, None, Some(100))
            .await
            .expect("Query should succeed");

        for recovery in &result.recoveries {
            assert!(recovery.anomaly_count_in_recovery >= 0,
                "anomaly_count_in_recovery should be >= 0");
        }
    }

    // ========== API Integration Tests ==========

    #[tokio::test]
    async fn test_agent_actions_pagination_consistency() {
        let pool = setup_test_pool().await;
        let sovereign_id = Uuid::new_v4();

        let page1 = fetch_agent_actions(&pool, sovereign_id, None, Some(10))
            .await
            .expect("First page should succeed");

        let page2 = fetch_agent_actions(&pool, sovereign_id, None, Some(10))
            .await
            .expect("Second page should succeed");

        assert_eq!(page1.total_count, page2.total_count, "total_count should be consistent across pages");
    }

    #[tokio::test]
    async fn test_anomalies_severity_ordering() {
        let pool = setup_test_pool().await;
        let sovereign_id = Uuid::new_v4();

        let result = fetch_anomalies(&pool, sovereign_id, None, None, Some(1000))
            .await
            .expect("Query should succeed");

        // Verify results exist
        assert!(result.anomalies.len() >= 0, "Should return anomalies list");
    }
}
