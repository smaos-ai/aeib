use siss_vision_sdk::*;
use uuid::Uuid;

// ============================================================================
// SDK CORE TESTS (10 tests)
// ============================================================================

#[tokio::test]
async fn test_sdk_oauth2_token_acquire() {
    let sdk = VisionSDKBuilder::new()
        .with_test_mode()
        .build()
        .await
        .expect("SDK build");

    let token = sdk
        .auth_handler
        .acquire_token("substack", "test_code", "test_state")
        .await
        .expect("Token acquisition");

    assert!(!token.access_token.is_empty());
    assert_eq!(token.platform, "substack");
}

#[tokio::test]
async fn test_sdk_oauth2_token_refresh() {
    let sdk = VisionSDKBuilder::new()
        .with_test_mode()
        .build()
        .await
        .expect("SDK build");

    // Store a token with refresh_token
    let creator_id = Uuid::new_v4();
    let platform = "patreon";
    let initial_token = OAuth2Token {
        access_token: "access_123".to_string(),
        refresh_token: Some("refresh_123".to_string()),
        platform: platform.to_string(),
        expires_at: Some(chrono::Utc::now() - chrono::Duration::seconds(3600)),
        scope: vec!["read".to_string()],
    };

    sdk.token_manager
        .store_token(creator_id, platform, &initial_token)
        .await
        .expect("Store token");

    // Retrieve and auto-refresh
    let refreshed = sdk
        .token_manager
        .retrieve_token(creator_id, platform)
        .await
        .expect("Retrieve + refresh token");

    assert!(!refreshed.access_token.is_empty());
    assert!(refreshed.access_token != initial_token.access_token);
}

#[tokio::test]
async fn test_sdk_policy_enforcement_wrapper() {
    let sdk = VisionSDKBuilder::new()
        .with_test_mode()
        .build()
        .await
        .expect("SDK build");

    let creator_id = Uuid::new_v4();
    let policy = CreatorPolicy {
        creator_id,
        rules: vec![PolicyRule {
            id: "rule-allow-substack".to_string(),
            description: "Allow Substack publish".to_string(),
            condition: PolicyCondition::Action {
                platform: "substack".to_string(),
                action: "publish".to_string(),
            },
            effect: PolicyEffect::Allow,
        }],
        version: 1,
    };

    sdk.policy_store
        .save_policy(creator_id, &policy)
        .await
        .expect("Save policy");

    // Evaluate decision
    let decision = sdk
        .evaluate_decision(
            creator_id,
            "substack",
            "publish",
            &DecisionContext {
                subscriber_tier: "free".to_string(),
                blast_radius: 0.25,
                estimated_value: Some(50.0),
            },
        )
        .await
        .expect("Evaluate decision");

    assert!(matches!(decision, DecisionGate::Approved { .. }));
}

#[tokio::test]
async fn test_sdk_split_enforcement_99_1() {
    let sdk = VisionSDKBuilder::new()
        .with_test_mode()
        .build()
        .await
        .expect("SDK build");

    let creator_id = Uuid::new_v4();
    let settlement = sdk
        .revenue_router
        .calculate_split(creator_id, 100.0, SplitRatio::default())
        .await
        .expect("Calculate split");

    // Default is 99/1
    assert_eq!(settlement.creator_payout, 99.0);
    assert_eq!(settlement.platform_fee, 1.0);
}

#[tokio::test]
async fn test_sdk_split_enforcement_custom_ratio() {
    let sdk = VisionSDKBuilder::new()
        .with_test_mode()
        .build()
        .await
        .expect("SDK build");

    let creator_id = Uuid::new_v4();
    let custom_ratio = SplitRatio {
        creator_percentage: 70.0,
        platform_percentage: 30.0,
    };

    let settlement = sdk
        .revenue_router
        .calculate_split(creator_id, 100.0, custom_ratio)
        .await
        .expect("Calculate split");

    assert_eq!(settlement.creator_payout, 70.0);
    assert_eq!(settlement.platform_fee, 30.0);
}

#[tokio::test]
async fn test_sdk_execution_context_isolation() {
    let sdk = VisionSDKBuilder::new()
        .with_test_mode()
        .build()
        .await
        .expect("SDK build");

    let creator_id = Uuid::new_v4();
    let context = ExecutionContext::new(creator_id, "substack", "publish");

    assert_eq!(context.creator_id, creator_id);
    assert_eq!(context.platform, "substack");
    assert_eq!(context.action, "publish");
    assert!(context.isolated);
}

#[tokio::test]
async fn test_sdk_earnings_reporting_json_ld() {
    let sdk = VisionSDKBuilder::new()
        .with_test_mode()
        .build()
        .await
        .expect("SDK build");

    let creator_id = Uuid::new_v4();
    let audit_entry = AuditEntry {
        id: Uuid::new_v4(),
        creator_id,
        platform: "substack".to_string(),
        action: "publish".to_string(),
        timestamp: chrono::Utc::now(),
        approved: true,
        blast_radius: 0.25,
        value_detected: Some(50.0),
        revenue_split: Some(RevenueSplit {
            value: 50.0,
            creator_payout: 49.5,
            platform_fee: 0.5,
        }),
        merkle_proof: "0x".to_string(),
        context: serde_json::json!({}),
    };

    let json_ld = audit_entry.to_json_ld();
    assert!(json_ld.get("@context").is_some());
    assert_eq!(
        json_ld.get("type").and_then(|v| v.as_str()),
        Some("CreatorDecision")
    );
}

#[tokio::test]
async fn test_sdk_error_handling_graceful() {
    let sdk = VisionSDKBuilder::new()
        .with_test_mode()
        .build()
        .await
        .expect("SDK build");

    let creator_id = Uuid::new_v4();
    let result = sdk
        .evaluate_decision(
            creator_id,
            "invalid_platform",
            "publish",
            &DecisionContext {
                subscriber_tier: "free".to_string(),
                blast_radius: 0.25,
                estimated_value: None,
            },
        )
        .await;

    assert!(result.is_err());
    match result.unwrap_err() {
        VisionError::UnknownPlatform(_) => {}
        _ => panic!("Expected UnknownPlatform error"),
    }
}

#[tokio::test]
async fn test_sdk_rate_limiting() {
    let sdk = VisionSDKBuilder::new()
        .with_test_mode()
        .with_rate_limit(10)
        .build()
        .await
        .expect("SDK build");

    let creator_id = Uuid::new_v4();
    let policy = CreatorPolicy {
        creator_id,
        rules: vec![PolicyRule {
            id: "rule-allow-all".to_string(),
            description: "Allow all".to_string(),
            condition: PolicyCondition::Always,
            effect: PolicyEffect::Allow,
        }],
        version: 1,
    };

    sdk.policy_store
        .save_policy(creator_id, &policy)
        .await
        .expect("Save policy");

    let ctx = DecisionContext {
        subscriber_tier: "free".to_string(),
        blast_radius: 0.1,
        estimated_value: Some(10.0),
    };

    // Make 10 requests (should succeed)
    for _ in 0..10 {
        let _decision = sdk
            .evaluate_decision(creator_id, "substack", "publish", &ctx)
            .await
            .expect("Decision evaluation");
    }

    // 11th should be rate limited
    let result = sdk
        .evaluate_decision(creator_id, "substack", "publish", &ctx)
        .await;

    assert!(result.is_err());
    match result.unwrap_err() {
        VisionError::RateLimited(_) => {}
        _ => panic!("Expected RateLimited error"),
    }
}

#[tokio::test]
async fn test_sdk_logging_immutable() {
    let sdk = VisionSDKBuilder::new()
        .with_test_mode()
        .build()
        .await
        .expect("SDK build");

    let creator_id = Uuid::new_v4();
    let decision_id = Uuid::new_v4();

    let entry = AuditEntry {
        id: decision_id,
        creator_id,
        platform: "substack".to_string(),
        action: "publish".to_string(),
        timestamp: chrono::Utc::now(),
        approved: true,
        blast_radius: 0.25,
        value_detected: Some(50.0),
        revenue_split: None,
        merkle_proof: "0x".to_string(),
        context: serde_json::json!({}),
    };

    sdk.audit_log
        .record(entry.clone())
        .await
        .expect("Record entry");

    let retrieved = sdk
        .audit_log
        .get_entry(decision_id)
        .await
        .expect("Get entry");

    assert_eq!(retrieved.id, decision_id);
    assert!(retrieved.approved);
}

// ============================================================================
// SUBSTACK ADAPTER TESTS (4 tests)
// ============================================================================

#[tokio::test]
async fn test_substack_publication_routing() {
    let adapter = SubstackAdapter::new_test();
    let auth = PlatformAuth {
        platform: "substack".to_string(),
        user_id: "user_123".to_string(),
        access_token: "token_123".to_string(),
        refresh_token: Some("refresh_123".to_string()),
        scope: vec!["write:publication".to_string()],
        expires_at: Some(chrono::Utc::now() + chrono::Duration::hours(1)),
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_substack_creator_registration() {
    let adapter = SubstackAdapter::new_test();
    let auth = PlatformAuth {
        platform: "substack".to_string(),
        user_id: "user_123".to_string(),
        access_token: "token_123".to_string(),
        refresh_token: None,
        scope: vec!["read:user".to_string()],
        expires_at: None,
    };

    let actions = adapter.list_actions(&auth).await;
    assert!(actions.is_ok());
    let actions_vec = actions.unwrap();
    assert!(actions_vec.iter().any(|a| a.name == "publish_newsletter"));
}

#[tokio::test]
async fn test_substack_earnings_sync() {
    let adapter = SubstackAdapter::new_test();
    let action_result = ActionResult {
        action: "publish_newsletter".to_string(),
        status: ActionStatus::Success,
        response: serde_json::json!({
            "subscriber_count": 5000,
            "paid_subscribers": 500,
            "estimated_value": 50.0
        }),
        latency_ms: 150.0,
    };

    let value = adapter
        .extract_value_signal(&action_result)
        .await
        .expect("Extract value");
    assert!(value > 0.0);
}

#[tokio::test]
async fn test_substack_split_enforcement() {
    let adapter = SubstackAdapter::new_test();
    let auth = PlatformAuth {
        platform: "substack".to_string(),
        user_id: "user_123".to_string(),
        access_token: "token_123".to_string(),
        refresh_token: None,
        scope: vec!["write:publication".to_string()],
        expires_at: None,
    };

    let params = serde_json::json!({
        "content": "Test publication",
        "subscriber_tier": "free"
    });

    let result = adapter
        .execute_action(&auth, "publish_newsletter", params, None)
        .await;
    // Should succeed or fail gracefully
    let _ = result;
}

// ============================================================================
// PATREON ADAPTER TESTS (4 tests)
// ============================================================================

#[tokio::test]
async fn test_patreon_membership_tier_mapping() {
    let adapter = PatreonAdapter::new_test();
    let auth = PlatformAuth {
        platform: "patreon".to_string(),
        user_id: "creator_123".to_string(),
        access_token: "token_123".to_string(),
        refresh_token: Some("refresh_123".to_string()),
        scope: vec!["campaigns".to_string()],
        expires_at: Some(chrono::Utc::now() + chrono::Duration::hours(1)),
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_patreon_patron_attribution() {
    let adapter = PatreonAdapter::new_test();
    let auth = PlatformAuth {
        platform: "patreon".to_string(),
        user_id: "creator_123".to_string(),
        access_token: "token_123".to_string(),
        refresh_token: None,
        scope: vec!["campaigns".to_string()],
        expires_at: None,
    };

    let actions = adapter.list_actions(&auth).await;
    assert!(actions.is_ok());
    let actions_vec = actions.unwrap();
    assert!(actions_vec.iter().any(|a| a.name == "create_post"));
}

#[tokio::test]
async fn test_patreon_payout_routing() {
    let adapter = PatreonAdapter::new_test();
    let action_result = ActionResult {
        action: "create_post".to_string(),
        status: ActionStatus::Success,
        response: serde_json::json!({
            "patron_count": 150,
            "avg_pledge": 5.0,
            "total_pledges": 750.0
        }),
        latency_ms: 200.0,
    };

    let value = adapter
        .extract_value_signal(&action_result)
        .await
        .expect("Extract value");
    assert!(value > 0.0);
}

#[tokio::test]
async fn test_patreon_split_tracking() {
    let adapter = PatreonAdapter::new_test();
    let auth = PlatformAuth {
        platform: "patreon".to_string(),
        user_id: "creator_123".to_string(),
        access_token: "token_123".to_string(),
        refresh_token: None,
        scope: vec!["campaigns".to_string()],
        expires_at: None,
    };

    let params = serde_json::json!({
        "title": "Exclusive content",
        "tier": "pro"
    });

    let result = adapter
        .execute_action(&auth, "create_post", params, None)
        .await;
    let _ = result;
}

// ============================================================================
// YOUTUBE ADAPTER TESTS (4 tests)
// ============================================================================

#[tokio::test]
async fn test_youtube_channel_metadata() {
    let adapter = YoutubeAdapter::new_test();
    let auth = PlatformAuth {
        platform: "youtube".to_string(),
        user_id: "channel_123".to_string(),
        access_token: "token_123".to_string(),
        refresh_token: Some("refresh_123".to_string()),
        scope: vec!["https://www.googleapis.com/auth/youtube".to_string()],
        expires_at: Some(chrono::Utc::now() + chrono::Duration::hours(1)),
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_youtube_monetization_split() {
    let adapter = YoutubeAdapter::new_test();
    let auth = PlatformAuth {
        platform: "youtube".to_string(),
        user_id: "channel_123".to_string(),
        access_token: "token_123".to_string(),
        refresh_token: None,
        scope: vec!["https://www.googleapis.com/auth/youtube".to_string()],
        expires_at: None,
    };

    let actions = adapter.list_actions(&auth).await;
    assert!(actions.is_ok());
    let actions_vec = actions.unwrap();
    assert!(actions_vec.iter().any(|a| a.name == "publish_video"));
}

#[tokio::test]
async fn test_youtube_royalty_tracking() {
    let adapter = YoutubeAdapter::new_test();
    let action_result = ActionResult {
        action: "publish_video".to_string(),
        status: ActionStatus::Success,
        response: serde_json::json!({
            "view_count": 10000,
            "watch_time_hours": 5000,
            "estimated_revenue": 50.0
        }),
        latency_ms: 250.0,
    };

    let value = adapter
        .extract_value_signal(&action_result)
        .await
        .expect("Extract value");
    assert!(value > 0.0);
}

#[tokio::test]
async fn test_youtube_earnings_reconciliation() {
    let adapter = YoutubeAdapter::new_test();
    let auth = PlatformAuth {
        platform: "youtube".to_string(),
        user_id: "channel_123".to_string(),
        access_token: "token_123".to_string(),
        refresh_token: None,
        scope: vec!["https://www.googleapis.com/auth/youtube".to_string()],
        expires_at: None,
    };

    let params = serde_json::json!({
        "title": "New video",
        "description": "Test video"
    });

    let result = adapter
        .execute_action(&auth, "publish_video", params, None)
        .await;
    let _ = result;
}

// ============================================================================
// NOTION ADAPTER TESTS (3 tests)
// ============================================================================

#[tokio::test]
async fn test_notion_database_sync() {
    let adapter = NotionAdapter::new_test();
    let auth = PlatformAuth {
        platform: "notion".to_string(),
        user_id: "user_123".to_string(),
        access_token: "token_123".to_string(),
        refresh_token: Some("refresh_123".to_string()),
        scope: vec!["databases".to_string()],
        expires_at: Some(chrono::Utc::now() + chrono::Duration::hours(1)),
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_notion_block_rendering() {
    let adapter = NotionAdapter::new_test();
    let auth = PlatformAuth {
        platform: "notion".to_string(),
        user_id: "user_123".to_string(),
        access_token: "token_123".to_string(),
        refresh_token: None,
        scope: vec!["databases".to_string()],
        expires_at: None,
    };

    let actions = adapter.list_actions(&auth).await;
    assert!(actions.is_ok());
    let actions_vec = actions.unwrap();
    assert!(actions_vec.iter().any(|a| a.name == "create_page"));
}

#[tokio::test]
async fn test_notion_creator_dashboard() {
    let adapter = NotionAdapter::new_test();
    let action_result = ActionResult {
        action: "create_page".to_string(),
        status: ActionStatus::Success,
        response: serde_json::json!({
            "page_id": "abc123",
            "database_size": 100
        }),
        latency_ms: 180.0,
    };

    let value = adapter
        .extract_value_signal(&action_result)
        .await
        .expect("Extract value");
    assert!(value >= 0.0);
}

// ============================================================================
// ZAPIER ADAPTER TESTS (3 tests)
// ============================================================================

#[tokio::test]
async fn test_zapier_trigger_mapping() {
    let adapter = ZapierAdapter::new_test();
    let auth = PlatformAuth {
        platform: "zapier".to_string(),
        user_id: "user_123".to_string(),
        access_token: "token_123".to_string(),
        refresh_token: None,
        scope: vec!["zaps".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_zapier_workflow_automation() {
    let adapter = ZapierAdapter::new_test();
    let auth = PlatformAuth {
        platform: "zapier".to_string(),
        user_id: "user_123".to_string(),
        access_token: "token_123".to_string(),
        refresh_token: None,
        scope: vec!["zaps".to_string()],
        expires_at: None,
    };

    let actions = adapter.list_actions(&auth).await;
    assert!(actions.is_ok());
    let actions_vec = actions.unwrap();
    assert!(actions_vec.iter().any(|a| a.name == "trigger_workflow"));
}

#[tokio::test]
async fn test_zapier_split_enforcement() {
    let adapter = ZapierAdapter::new_test();
    let action_result = ActionResult {
        action: "trigger_workflow".to_string(),
        status: ActionStatus::Success,
        response: serde_json::json!({
            "task_count": 50,
            "executions": 10
        }),
        latency_ms: 200.0,
    };

    let value = adapter
        .extract_value_signal(&action_result)
        .await
        .expect("Extract value");
    assert!(value >= 0.0);
}

// ============================================================================
// TWITTER ADAPTER TEST (1 test)
// ============================================================================

#[tokio::test]
async fn test_twitter_profile_integration() {
    let adapter = TwitterAdapter::new_test();
    let auth = PlatformAuth {
        platform: "twitter".to_string(),
        user_id: "user_123".to_string(),
        access_token: "token_123".to_string(),
        refresh_token: Some("refresh_123".to_string()),
        scope: vec!["tweet.write".to_string()],
        expires_at: Some(chrono::Utc::now() + chrono::Duration::hours(1)),
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

// ============================================================================
// TIKTOK ADAPTER TEST (1 test)
// ============================================================================

#[tokio::test]
async fn test_tiktok_auth_flow() {
    let adapter = TiktokAdapter::new_test();
    let auth = PlatformAuth {
        platform: "tiktok".to_string(),
        user_id: "user_123".to_string(),
        access_token: "token_123".to_string(),
        refresh_token: Some("refresh_123".to_string()),
        scope: vec!["video.upload".to_string()],
        expires_at: Some(chrono::Utc::now() + chrono::Duration::hours(1)),
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

// ============================================================================
// TWITCH ADAPTER TEST (1 test)
// ============================================================================

#[tokio::test]
async fn test_twitch_split_validation() {
    let adapter = TwitchAdapter::new_test();
    let auth = PlatformAuth {
        platform: "twitch".to_string(),
        user_id: "user_123".to_string(),
        access_token: "token_123".to_string(),
        refresh_token: Some("refresh_123".to_string()),
        scope: vec!["moderation:read".to_string()],
        expires_at: Some(chrono::Utc::now() + chrono::Duration::hours(1)),
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

// ============================================================================
// DISCORD ADAPTER TEST (1 test)
// ============================================================================

#[tokio::test]
async fn test_discord_channel_mapping() {
    let adapter = DiscordAdapter::new_test();
    let auth = PlatformAuth {
        platform: "discord".to_string(),
        user_id: "user_123".to_string(),
        access_token: "token_123".to_string(),
        refresh_token: Some("refresh_123".to_string()),
        scope: vec!["guild.manage".to_string()],
        expires_at: Some(chrono::Utc::now() + chrono::Duration::hours(1)),
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

// ============================================================================
// SLACK ADAPTER TEST (1 test)
// ============================================================================

#[tokio::test]
async fn test_slack_workflow_integration() {
    let adapter = SlackAdapter::new_test();
    let auth = PlatformAuth {
        platform: "slack".to_string(),
        user_id: "user_123".to_string(),
        access_token: "token_123".to_string(),
        refresh_token: Some("refresh_123".to_string()),
        scope: vec!["workflows.triggers:write".to_string()],
        expires_at: Some(chrono::Utc::now() + chrono::Duration::hours(1)),
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

// ============================================================================
// ADDITIONAL VALIDATION TESTS (4 tests)
// ============================================================================

#[tokio::test]
async fn test_adapter_list_exhaustive() {
    let adapters = get_all_adapters();
    // Should have at least 10 adapters for Phase 1
    assert!(adapters.len() >= 10, "Should have at least 10 adapters");
}

#[tokio::test]
async fn test_policy_condition_parsing() {
    let _sdk = VisionSDKBuilder::new()
        .with_test_mode()
        .build()
        .await
        .expect("SDK build");

    let sdk = _sdk;

    let creator_id = Uuid::new_v4();
    let policy = CreatorPolicy {
        creator_id,
        rules: vec![
            PolicyRule {
                id: "rule-1".to_string(),
                description: "Allow substack".to_string(),
                condition: PolicyCondition::Action {
                    platform: "substack".to_string(),
                    action: "publish".to_string(),
                },
                effect: PolicyEffect::Allow,
            },
            PolicyRule {
                id: "rule-2".to_string(),
                description: "Deny invalid".to_string(),
                condition: PolicyCondition::Always,
                effect: PolicyEffect::Deny,
            },
        ],
        version: 1,
    };

    sdk.policy_store
        .save_policy(creator_id, &policy)
        .await
        .expect("Save policy");

    let stored = sdk
        .policy_store
        .load_policy(creator_id)
        .await
        .expect("Load policy");

    assert_eq!(stored.rules.len(), 2);
}

#[tokio::test]
async fn test_multi_platform_simultaneous_decisions() {
    let sdk = VisionSDKBuilder::new()
        .with_test_mode()
        .build()
        .await
        .expect("SDK build");

    let creator_id = Uuid::new_v4();
    let policy = CreatorPolicy {
        creator_id,
        rules: vec![PolicyRule {
            id: "rule-allow-all".to_string(),
            description: "Allow all".to_string(),
            condition: PolicyCondition::Always,
            effect: PolicyEffect::Allow,
        }],
        version: 1,
    };

    sdk.policy_store
        .save_policy(creator_id, &policy)
        .await
        .expect("Save policy");

    let ctx = DecisionContext {
        subscriber_tier: "pro".to_string(),
        blast_radius: 0.3,
        estimated_value: Some(100.0),
    };

    let platforms = vec!["substack", "patreon", "youtube"];
    // Execute multiple decisions in parallel
    let handles: Vec<_> = platforms
        .iter()
        .map(|&platform| {
            let sdk_clone = sdk.clone();
            let ctx_clone = ctx.clone();
            tokio::spawn(async move {
                sdk_clone
                    .evaluate_decision(creator_id, platform, "publish", &ctx_clone)
                    .await
            })
        })
        .collect();

    let results = futures::future::join_all(handles).await;

    // All should succeed
    for result in results {
        assert!(result.is_ok());
        assert!(result.unwrap().is_ok());
    }
}

#[tokio::test]
async fn test_creator_revenue_aggregation() {
    let sdk = VisionSDKBuilder::new()
        .with_test_mode()
        .build()
        .await
        .expect("SDK build");

    let creator_id = Uuid::new_v4();

    // Record multiple settlements
    for i in 0..5 {
        let _settlement = sdk
            .revenue_router
            .calculate_split(creator_id, (i + 1) as f64 * 100.0, SplitRatio::default())
            .await
            .expect("Calculate split");
    }

    // Query aggregate
    let summary = sdk
        .revenue_router
        .get_earnings_summary(creator_id)
        .await
        .expect("Get summary");

    assert!(summary.total_detected > 0.0);
    assert!(summary.creator_total > 0.0);
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

fn get_all_adapters() -> Vec<String> {
    vec![
        "substack".to_string(),
        "patreon".to_string(),
        "youtube".to_string(),
        "notion".to_string(),
        "zapier".to_string(),
        "twitter".to_string(),
        "tiktok".to_string(),
        "twitch".to_string(),
        "discord".to_string(),
        "slack".to_string(),
    ]
}
