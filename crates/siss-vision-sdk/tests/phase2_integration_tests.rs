use siss_vision_sdk::*;
use uuid::Uuid;

// ============================================================================
// PHASE 2: 40 ADDITIONAL PLATFORMS (Tests 38-77)
// ============================================================================

#[tokio::test]
async fn test_medium_platform_adapter() {
    let adapter = MediumAdapter::new_test();
    let auth = PlatformAuth {
        platform: "medium".to_string(),
        user_id: "user_medium_001".to_string(),
        access_token: "token_medium".to_string(),
        refresh_token: Some("refresh_medium".to_string()),
        scope: vec!["write_article".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_medium_article_publishing() {
    let adapter = MediumAdapter::new_test();
    let auth = PlatformAuth {
        platform: "medium".to_string(),
        user_id: "user_medium_001".to_string(),
        access_token: "token_medium".to_string(),
        refresh_token: None,
        scope: vec!["write_article".to_string()],
        expires_at: None,
    };

    let actions = adapter.list_actions(&auth).await;
    assert!(actions.is_ok());
    let actions_vec = actions.unwrap();
    assert!(actions_vec.iter().any(|a| a.name == "publish_article"));
}

#[tokio::test]
async fn test_medium_member_earnings() {
    let adapter = MediumAdapter::new_test();
    let action_result = ActionResult {
        action: "publish_article".to_string(),
        status: ActionStatus::Success,
        response: serde_json::json!({
            "article_id": "abc123",
            "claps": 2500,
            "estimated_earnings": 75.50,
            "member_earnings_pool_pct": 15.5
        }),
        latency_ms: 200.0,
    };

    let value = adapter.extract_value_signal(&action_result).await;
    assert!(value.is_ok());
    assert!(value.unwrap() > 0.0);
}

#[tokio::test]
async fn test_linkedin_platform_adapter() {
    let adapter = LinkedinAdapter::new_test();
    let auth = PlatformAuth {
        platform: "linkedin".to_string(),
        user_id: "linkedin_user_123".to_string(),
        access_token: "linkedin_token".to_string(),
        refresh_token: Some("linkedin_refresh".to_string()),
        scope: vec!["w_member_social".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_bluesky_platform_adapter() {
    let adapter = BlueskyAdapter::new_test();
    let auth = PlatformAuth {
        platform: "bluesky".to_string(),
        user_id: "did:plc:bsky123".to_string(),
        access_token: "bsky_token".to_string(),
        refresh_token: Some("bsky_refresh".to_string()),
        scope: vec!["create:posts".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_threads_platform_adapter() {
    let adapter = ThreadsAdapter::new_test();
    let auth = PlatformAuth {
        platform: "threads".to_string(),
        user_id: "threads_user_456".to_string(),
        access_token: "threads_token".to_string(),
        refresh_token: None,
        scope: vec!["threads_basic_access".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_mastodon_platform_adapter() {
    let adapter = MastodonAdapter::new_test();
    let auth = PlatformAuth {
        platform: "mastodon".to_string(),
        user_id: "mastodon@example.com".to_string(),
        access_token: "mastodon_token".to_string(),
        refresh_token: Some("mastodon_refresh".to_string()),
        scope: vec!["write".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_gumroad_platform_adapter() {
    let adapter = GumroadAdapter::new_test();
    let auth = PlatformAuth {
        platform: "gumroad".to_string(),
        user_id: "gumroad_creator".to_string(),
        access_token: "gumroad_token".to_string(),
        refresh_token: None,
        scope: vec!["products:write".to_string()],
        expires_at: None,
    };

    let actions = adapter.list_actions(&auth).await;
    assert!(actions.is_ok());
}

#[tokio::test]
async fn test_convertkit_platform_adapter() {
    let adapter = ConvertKitAdapter::new_test();
    let auth = PlatformAuth {
        platform: "convertkit".to_string(),
        user_id: "ck_creator_123".to_string(),
        access_token: "ck_token".to_string(),
        refresh_token: Some("ck_refresh".to_string()),
        scope: vec!["subscriber:write".to_string()],
        expires_at: None,
    };

    let actions = adapter.list_actions(&auth).await;
    assert!(actions.is_ok());
}

#[tokio::test]
async fn test_ghost_platform_adapter() {
    let adapter = GhostAdapter::new_test();
    let auth = PlatformAuth {
        platform: "ghost".to_string(),
        user_id: "ghost_001".to_string(),
        access_token: "ghost_api_key".to_string(),
        refresh_token: None,
        scope: vec!["posts:write".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_mirror_protocol_adapter() {
    let adapter = MirrorAdapter::new_test();
    let auth = PlatformAuth {
        platform: "mirror".to_string(),
        user_id: "0x1234567890".to_string(),
        access_token: "mirror_token".to_string(),
        refresh_token: None,
        scope: vec!["write:publication".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_farcaster_platform_adapter() {
    let adapter = FarcasterAdapter::new_test();
    let auth = PlatformAuth {
        platform: "farcaster".to_string(),
        user_id: "fc_user_789".to_string(),
        access_token: "fc_token".to_string(),
        refresh_token: None,
        scope: vec!["casts:write".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_lens_protocol_adapter() {
    let adapter = LensProtocolAdapter::new_test();
    let auth = PlatformAuth {
        platform: "lens".to_string(),
        user_id: "0x9999".to_string(),
        access_token: "lens_token".to_string(),
        refresh_token: None,
        scope: vec!["post:create".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_pixelfed_platform_adapter() {
    let adapter = PixelfedAdapter::new_test();
    let auth = PlatformAuth {
        platform: "pixelfed".to_string(),
        user_id: "pixelfed_user".to_string(),
        access_token: "pixelfed_token".to_string(),
        refresh_token: None,
        scope: vec!["write:media".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_peertube_platform_adapter() {
    let adapter = PeertubeAdapter::new_test();
    let auth = PlatformAuth {
        platform: "peertube".to_string(),
        user_id: "pt_user".to_string(),
        access_token: "pt_token".to_string(),
        refresh_token: Some("pt_refresh".to_string()),
        scope: vec!["videos:write".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_telegram_platform_adapter() {
    let adapter = TelegramAdapter::new_test();
    let auth = PlatformAuth {
        platform: "telegram".to_string(),
        user_id: "tg_user_123".to_string(),
        access_token: "tg_bot_token".to_string(),
        refresh_token: None,
        scope: vec!["chat:write".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_signal_platform_adapter() {
    let adapter = SignalAdapter::new_test();
    let auth = PlatformAuth {
        platform: "signal".to_string(),
        user_id: "signal_user".to_string(),
        access_token: "signal_token".to_string(),
        refresh_token: None,
        scope: vec!["message:write".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_wechat_platform_adapter() {
    let adapter = WechatAdapter::new_test();
    let auth = PlatformAuth {
        platform: "wechat".to_string(),
        user_id: "wechat_openid".to_string(),
        access_token: "wechat_access_token".to_string(),
        refresh_token: Some("wechat_refresh".to_string()),
        scope: vec!["message:send".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_viber_platform_adapter() {
    let adapter = ViberAdapter::new_test();
    let auth = PlatformAuth {
        platform: "viber".to_string(),
        user_id: "viber_user_id".to_string(),
        access_token: "viber_token".to_string(),
        refresh_token: None,
        scope: vec!["message:send".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_line_platform_adapter() {
    let adapter = LineAdapter::new_test();
    let auth = PlatformAuth {
        platform: "line".to_string(),
        user_id: "line_user_id".to_string(),
        access_token: "line_channel_token".to_string(),
        refresh_token: None,
        scope: vec!["message:send".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_kick_platform_adapter() {
    let adapter = KickAdapter::new_test();
    let auth = PlatformAuth {
        platform: "kick".to_string(),
        user_id: "kick_creator_123".to_string(),
        access_token: "kick_token".to_string(),
        refresh_token: Some("kick_refresh".to_string()),
        scope: vec!["stream:write".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_rumble_platform_adapter() {
    let adapter = RumbleAdapter::new_test();
    let auth = PlatformAuth {
        platform: "rumble".to_string(),
        user_id: "rumble_user".to_string(),
        access_token: "rumble_token".to_string(),
        refresh_token: None,
        scope: vec!["video:upload".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_odysee_platform_adapter() {
    let adapter = OdyseeAdapter::new_test();
    let auth = PlatformAuth {
        platform: "odysee".to_string(),
        user_id: "odysee_channel".to_string(),
        access_token: "odysee_token".to_string(),
        refresh_token: None,
        scope: vec!["channel:publish".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_amazon_live_platform_adapter() {
    let adapter = AmazonLiveAdapter::new_test();
    let auth = PlatformAuth {
        platform: "amazon_live".to_string(),
        user_id: "amzn_merchant".to_string(),
        access_token: "amzn_token".to_string(),
        refresh_token: Some("amzn_refresh".to_string()),
        scope: vec!["live:broadcast".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_tiktok_shop_platform_adapter() {
    let adapter = TiktokShopAdapter::new_test();
    let auth = PlatformAuth {
        platform: "tiktok_shop".to_string(),
        user_id: "tiktok_shop_id".to_string(),
        access_token: "tiktok_shop_token".to_string(),
        refresh_token: Some("tiktok_shop_refresh".to_string()),
        scope: vec!["shop:manage".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_activecampaign_platform_adapter() {
    let adapter = ActiveCampaignAdapter::new_test();
    let auth = PlatformAuth {
        platform: "activecampaign".to_string(),
        user_id: "ac_user".to_string(),
        access_token: "ac_api_token".to_string(),
        refresh_token: None,
        scope: vec!["contacts:write".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_hubspot_platform_adapter() {
    let adapter = HubspotAdapter::new_test();
    let auth = PlatformAuth {
        platform: "hubspot".to_string(),
        user_id: "hs_user".to_string(),
        access_token: "hs_private_app_token".to_string(),
        refresh_token: None,
        scope: vec!["contacts.write".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_mailchimp_platform_adapter() {
    let adapter = MailchimpAdapter::new_test();
    let auth = PlatformAuth {
        platform: "mailchimp".to_string(),
        user_id: "mc_user".to_string(),
        access_token: "mc_api_key".to_string(),
        refresh_token: None,
        scope: vec!["lists:write".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_brevo_platform_adapter() {
    let adapter = BrevoAdapter::new_test();
    let auth = PlatformAuth {
        platform: "brevo".to_string(),
        user_id: "brevo_user".to_string(),
        access_token: "brevo_api_key".to_string(),
        refresh_token: None,
        scope: vec!["contacts:write".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_getresponse_platform_adapter() {
    let adapter = GetResponseAdapter::new_test();
    let auth = PlatformAuth {
        platform: "getresponse".to_string(),
        user_id: "gr_user".to_string(),
        access_token: "gr_api_key".to_string(),
        refresh_token: None,
        scope: vec!["contacts.write".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_unbounce_platform_adapter() {
    let adapter = UnbounceAdapter::new_test();
    let auth = PlatformAuth {
        platform: "unbounce".to_string(),
        user_id: "ub_user".to_string(),
        access_token: "ub_api_token".to_string(),
        refresh_token: None,
        scope: vec!["pages:write".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_leadpages_platform_adapter() {
    let adapter = LeadpagesAdapter::new_test();
    let auth = PlatformAuth {
        platform: "leadpages".to_string(),
        user_id: "lp_user".to_string(),
        access_token: "lp_api_token".to_string(),
        refresh_token: None,
        scope: vec!["pages:write".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_funnelytics_platform_adapter() {
    let adapter = FunnelyticsAdapter::new_test();
    let auth = PlatformAuth {
        platform: "funnelytics".to_string(),
        user_id: "fn_user".to_string(),
        access_token: "fn_token".to_string(),
        refresh_token: None,
        scope: vec!["analytics:read".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_strava_platform_adapter() {
    let adapter = StravaAdapter::new_test();
    let auth = PlatformAuth {
        platform: "strava".to_string(),
        user_id: "strava_user_123".to_string(),
        access_token: "strava_token".to_string(),
        refresh_token: Some("strava_refresh".to_string()),
        scope: vec!["activity:write".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_patreon_enterprise_adapter() {
    let adapter = PatreonEnterpriseAdapter::new_test();
    let auth = PlatformAuth {
        platform: "patreon_enterprise".to_string(),
        user_id: "patreon_ent_123".to_string(),
        access_token: "patreon_ent_token".to_string(),
        refresh_token: Some("patreon_ent_refresh".to_string()),
        scope: vec!["campaigns:read".to_string(), "members:write".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_flodesk_platform_adapter() {
    let adapter = FlodeskAdapter::new_test();
    let auth = PlatformAuth {
        platform: "flodesk".to_string(),
        user_id: "flodesk_001".to_string(),
        access_token: "flodesk_api_key".to_string(),
        refresh_token: None,
        scope: vec!["email:write".to_string()],
        expires_at: None,
    };

    let result = adapter.authenticate(&auth.access_token).await;
    assert!(result.is_ok());
}

// ============================================================================
// PHASE 2 INTEGRATION TESTS (5 tests)
// ============================================================================

#[tokio::test]
async fn test_phase2_adapter_list_complete() {
    let sdk = VisionSDKBuilder::new()
        .with_test_mode()
        .build()
        .await
        .expect("SDK build");

    let adapters = sdk.list_all_adapters().await.expect("List adapters");
    assert!(adapters.len() >= 50, "Expected at least 50 total adapters, got {}", adapters.len());
}

#[tokio::test]
async fn test_phase2_multi_platform_earnings_sync() {
    let sdk = VisionSDKBuilder::new()
        .with_test_mode()
        .build()
        .await
        .expect("SDK build");

    let creator_id = Uuid::new_v4();
    let platforms = vec!["medium", "linkedin", "bluesky", "gumroad", "convertkit"];

    for platform in platforms {
        let decision = sdk
            .evaluate_decision(
                creator_id,
                platform,
                "publish",
                &DecisionContext {
                    subscriber_tier: "premium".to_string(),
                    blast_radius: 0.3,
                    estimated_value: Some(100.0),
                },
            )
            .await;

        assert!(decision.is_ok(), "Failed to evaluate {} decision", platform);
    }
}

#[tokio::test]
async fn test_phase2_token_refresh_across_platforms() {
    let sdk = VisionSDKBuilder::new()
        .with_test_mode()
        .build()
        .await
        .expect("SDK build");

    let creator_id = Uuid::new_v4();
    let platforms = vec!["linkedin", "bluesky", "gumroad", "hubspot"];

    for platform in platforms {
        let token = OAuth2Token {
            access_token: format!("token_{}", platform),
            refresh_token: Some(format!("refresh_{}", platform)),
            platform: platform.to_string(),
            expires_at: Some(chrono::Utc::now() - chrono::Duration::seconds(3600)),
            scope: vec!["write".to_string()],
        };

        sdk.token_manager
            .store_token(creator_id, platform, &token)
            .await
            .expect("Store token");

        let refreshed = sdk
            .token_manager
            .retrieve_token(creator_id, platform)
            .await
            .expect("Retrieve + auto-refresh");

        assert!(!refreshed.access_token.is_empty());
    }
}

#[tokio::test]
async fn test_phase2_policy_enforcement_multi_platform() {
    let sdk = VisionSDKBuilder::new()
        .with_test_mode()
        .build()
        .await
        .expect("SDK build");

    let creator_id = Uuid::new_v4();
    let policy = CreatorPolicy {
        creator_id,
        rules: vec![
            PolicyRule {
                id: "rule-tier1".to_string(),
                description: "Allow content platforms".to_string(),
                condition: PolicyCondition::Action {
                    platform: "medium".to_string(),
                    action: "publish".to_string(),
                },
                effect: PolicyEffect::Allow,
            },
        ],
        version: 1,
    };

    sdk.policy_store
        .save_policy(creator_id, &policy)
        .await
        .expect("Save policy");

    let medium_decision = sdk
        .evaluate_decision(
            creator_id,
            "medium",
            "publish",
            &DecisionContext {
                subscriber_tier: "free".to_string(),
                blast_radius: 0.2,
                estimated_value: Some(50.0),
            },
        )
        .await;

    assert!(medium_decision.is_ok());
}

#[tokio::test]
async fn test_phase2_json_ld_compliance_all_platforms() {
    let platforms = vec![
        "medium", "linkedin", "bluesky", "gumroad", "telegram",
        "hubspot", "brevo", "kick", "rumble", "mirror"
    ];

    for platform in platforms {
        let entry = AuditEntry {
            id: Uuid::new_v4(),
            creator_id: Uuid::new_v4(),
            platform: platform.to_string(),
            action: "publish".to_string(),
            timestamp: chrono::Utc::now(),
            approved: true,
            blast_radius: 0.3,
            value_detected: Some(100.0),
            revenue_split: Some(RevenueSplit {
                value: 100.0,
                creator_payout: 99.0,
                platform_fee: 1.0,
            }),
            merkle_proof: "0x".to_string(),
            context: serde_json::json!({
                "platform_tier": "phase2"
            }),
        };

        let json_ld = entry.to_json_ld();
        assert!(json_ld.get("@context").is_some(), "Missing @context for {}", platform);
        assert_eq!(
            json_ld.get("type").and_then(|v| v.as_str()),
            Some("CreatorDecision"),
            "Invalid type for {}", platform
        );
    }
}
