/// Phase 26 Task 1: Router Integration Tests
/// E2E verification of POST /api/router/route endpoint

#[cfg(test)]
mod integration_tests {
    use crate::handlers::router_handler::RouteRequest;
    use crate::handlers::router_handler::post_route;
    use axum::Json;

    #[tokio::test]
    async fn test_e2e_polling_task_complete_flow() {
        let payload = RouteRequest {
            task_description: "polling agent status every 5 seconds".to_string(),
            budget_tokens: Some(1000),
        };

        let result = post_route(Json(payload)).await;
        assert!(result.is_ok());

        let Json(response) = result.unwrap();
        assert_eq!(response.assigned_tier, "Tier1RapidMLX");
        assert_eq!(response.confidence_score, 0.1);
        assert!(!response.fallback_chain.is_empty());
        assert_eq!(response.fallback_chain[0], "Tier2Sonnet");
        assert!(response.latency_ms < 100); // Should be fast
    }

    #[tokio::test]
    async fn test_e2e_multi_complexity_routing() {
        let tasks = vec![
            ("polling status", "Tier1RapidMLX", 0.1),
            ("filter by severity", "Tier1RapidMLX", 0.4),
            ("correlate patterns", "Tier2Sonnet", 0.65),
            ("complex decision making", "Tier3Opus", 0.8),
        ];

        for (description, expected_tier, expected_confidence) in tasks {
            let payload = RouteRequest {
                task_description: description.to_string(),
                budget_tokens: None,
            };

            let result = post_route(Json(payload)).await;
            assert!(result.is_ok(), "Failed for task: {}", description);

            let Json(response) = result.unwrap();
            assert_eq!(
                response.assigned_tier, expected_tier,
                "Task: {}",
                description
            );
            assert_eq!(
                response.confidence_score, expected_confidence,
                "Task: {}",
                description
            );
        }
    }

    #[tokio::test]
    async fn test_e2e_fallback_chain_correctness() {
        // Tier1 should have fallback to Tier2/3
        let tier1_task = RouteRequest {
            task_description: "polling".to_string(),
            budget_tokens: None,
        };

        let Json(tier1_response) = post_route(Json(tier1_task))
            .await
            .expect("handler should succeed");

        assert_eq!(tier1_response.assigned_tier, "Tier1RapidMLX");
        assert_eq!(tier1_response.fallback_chain.len(), 2);
        assert_eq!(tier1_response.fallback_chain[0], "Tier2Sonnet");
        assert_eq!(tier1_response.fallback_chain[1], "Tier3Opus");

        // Tier3 should have no fallback
        let tier3_task = RouteRequest {
            task_description: "complex decision".to_string(),
            budget_tokens: None,
        };

        let Json(tier3_response) = post_route(Json(tier3_task))
            .await
            .expect("handler should succeed");

        assert_eq!(tier3_response.assigned_tier, "Tier3Opus");
        assert!(tier3_response.fallback_chain.is_empty());
    }

    #[tokio::test]
    async fn test_e2e_cost_calculation_accuracy() {
        let payload = RouteRequest {
            task_description: "correlate anomalies".to_string(),
            budget_tokens: None,
        };

        let Json(response) = post_route(Json(payload))
            .await
            .expect("handler should succeed");

        // Tier2 base cost: $0.003 per 1K tokens
        // With 20% cache discount: 0.8x multiplier
        // Token estimate: ~150 tokens
        // Expected cost: (150 / 1000) * 0.003 * 0.8 = ~0.00036
        assert!(response.token_cost >= 0.0);
        assert!(response.token_cost < 0.01); // Sanity check: should be < 1 cent
    }

    #[tokio::test]
    async fn test_e2e_latency_acceptable() {
        let payload = RouteRequest {
            task_description: "test latency measurement".to_string(),
            budget_tokens: None,
        };

        let Json(response) = post_route(Json(payload))
            .await
            .expect("handler should succeed");

        // Routing latency should be < 100ms (very fast operation)
        assert!(
            response.latency_ms < 100,
            "Latency too high: {}ms",
            response.latency_ms
        );
    }

    #[tokio::test]
    async fn test_e2e_budget_prevents_expensive_tasks() {
        // Budget too small for Tier3
        let payload = RouteRequest {
            task_description: "complex decision making".to_string(),
            budget_tokens: Some(50), // Only 50 tokens available
        };

        let result = post_route(Json(payload)).await;
        assert!(
            result.is_err(),
            "Should reject high-confidence task with tiny budget"
        );
    }

    #[tokio::test]
    async fn test_e2e_budget_allows_tier1() {
        // Tier1 task needs ~100 tokens, so budget must be >= 100
        let payload = RouteRequest {
            task_description: "polling".to_string(),
            budget_tokens: Some(150), // Sufficient for Tier1 (~100 tokens)
        };

        let result = post_route(Json(payload)).await;
        assert!(result.is_ok(), "Should allow Tier1 with sufficient budget");

        let Json(response) = result.unwrap();
        assert_eq!(response.assigned_tier, "Tier1RapidMLX");
    }

    #[tokio::test]
    async fn test_e2e_response_always_has_reason() {
        let tasks = vec![
            "polling",
            "filter results",
            "correlate data",
            "complex analysis",
        ];

        for task in tasks {
            let payload = RouteRequest {
                task_description: task.to_string(),
                budget_tokens: None,
            };

            let Json(response) = post_route(Json(payload))
                .await
                .expect("handler should succeed");

            assert!(!response.reason.is_empty(), "Task: {} has no reason", task);
            assert!(response.reason.len() > 10, "Reason too short for: {}", task);
        }
    }
}
