use siss_zero_trust::{
    KeyRotationEngine, RotationSchedule, SessionManager, TrustBoundary, TrustContext,
    ZeroTrustConfig,
};
use std::sync::Arc;

// Tests 1-5: Key generation and rotation scheduling
#[tokio::test]
async fn test_1_generate_initial_keypair() {
    let engine = KeyRotationEngine::new().await;
    assert!(engine.current_key_id().await.is_some());
}

#[tokio::test]
async fn test_2_schedule_rotation() {
    let engine = KeyRotationEngine::new().await;
    let schedule = RotationSchedule::daily();
    engine.set_rotation_schedule(schedule).await.unwrap();
    let active = engine.get_rotation_schedule().await;
    assert!(active.is_some());
}

#[tokio::test]
async fn test_3_generate_next_key() {
    let engine = KeyRotationEngine::new().await;
    engine.prepare_next_key().await.unwrap();
    assert!(engine.has_pending_key().await);
}

#[tokio::test]
async fn test_4_key_ids_unique() {
    let engine = KeyRotationEngine::new().await;
    let id1 = engine.current_key_id().await.unwrap();
    engine.prepare_next_key().await.unwrap();
    let id2 = engine.pending_key_id().await.unwrap();
    assert_ne!(id1, id2);
}

#[tokio::test]
async fn test_5_rotation_schedule_formats() {
    let daily = RotationSchedule::daily();
    let hourly = RotationSchedule::hourly();
    let custom = RotationSchedule::custom_interval_secs(3600);

    assert_ne!(daily.interval_secs, hourly.interval_secs);
    assert_eq!(hourly.interval_secs, custom.interval_secs);
}

// Tests 6-10: Live rotation without service interruption
#[tokio::test]
async fn test_6_live_rotation_succeeds() {
    let engine = KeyRotationEngine::new().await;
    let proof = engine.rotate_keys_live().await.unwrap();
    assert!(!proof.rotation_id.is_empty());
    assert!(proof.timestamp > 0);
}

#[tokio::test]
async fn test_7_rotation_transitions_keys() {
    let engine = KeyRotationEngine::new().await;
    let old_id = engine.current_key_id().await.unwrap();
    engine.rotate_keys_live().await.unwrap();
    let new_id = engine.current_key_id().await.unwrap();
    assert_ne!(old_id, new_id);
}

#[tokio::test]
async fn test_8_old_key_remains_accessible() {
    let engine = KeyRotationEngine::new().await;
    let old_id = engine.current_key_id().await.unwrap();
    engine.rotate_keys_live().await.unwrap();

    // Old key should still be accessible for verification
    let can_verify = engine.verify_with_key(&old_id).await.unwrap();
    assert!(can_verify);
}

#[tokio::test]
async fn test_9_concurrent_requests_during_rotation() {
    let engine = Arc::new(KeyRotationEngine::new().await);
    let mut handles = vec![];

    // Spawn multiple concurrent validation requests
    for _ in 0..10 {
        let engine_clone = engine.clone();
        handles.push(tokio::spawn(async move {
            engine_clone.verify_zero_trust().await.unwrap_or(false)
        }));
    }

    // Perform rotation in background
    let rotation_handle = {
        let engine_clone = engine.clone();
        tokio::spawn(async move {
            engine_clone.rotate_keys_live().await
        })
    };

    // All requests should complete successfully
    for handle in handles {
        assert!(handle.await.unwrap());
    }
    rotation_handle.await.unwrap().unwrap();
}

#[tokio::test]
async fn test_10_no_service_interruption_during_rotation() {
    let engine = KeyRotationEngine::new().await;
    let _config = ZeroTrustConfig::default();

    // Measure latency before rotation
    let start = std::time::Instant::now();
    engine.verify_zero_trust().await.unwrap();
    let baseline_latency = start.elapsed();

    // Rotate
    engine.rotate_keys_live().await.unwrap();

    // Measure latency after rotation
    let start = std::time::Instant::now();
    engine.verify_zero_trust().await.unwrap();
    let post_rotation_latency = start.elapsed();

    // Latency should not degrade significantly (within 2x)
    assert!(post_rotation_latency < baseline_latency.mul_f64(2.0));
}

// Tests 11-15: Session key validation and replay attack prevention
#[tokio::test]
async fn test_11_session_key_generation() {
    let manager = SessionManager::new(ZeroTrustConfig::default());
    let session_key = manager.generate_session_key().await.unwrap();
    assert!(session_key.is_valid());
}

#[tokio::test]
async fn test_12_session_token_creation() {
    let manager = SessionManager::new(ZeroTrustConfig::default());
    let session_key = manager.generate_session_key().await.unwrap();
    let token = manager.create_token(&session_key).await.unwrap();
    assert!(!token.is_empty());
}

#[tokio::test]
async fn test_13_session_token_validation() {
    let manager = SessionManager::new(ZeroTrustConfig::default());
    let session_key = manager.generate_session_key().await.unwrap();
    let token = manager.create_token(&session_key).await.unwrap();

    let is_valid = manager.validate_token(&token).await.unwrap();
    assert!(is_valid);
}

#[tokio::test]
async fn test_14_replay_attack_prevention() {
    let manager = SessionManager::new(ZeroTrustConfig::default());
    let session_key = manager.generate_session_key().await.unwrap();
    let token = manager.create_token(&session_key).await.unwrap();

    // First use should succeed
    assert!(manager.validate_token(&token).await.unwrap());

    // Reusing same nonce should fail
    let is_replay = manager.is_replay_attack(&token).await.unwrap();
    assert!(is_replay);
}

#[tokio::test]
async fn test_15_session_expiration() {
    let mut config = ZeroTrustConfig::default();
    config.session_timeout_secs = 1; // 1 second timeout
    let manager = SessionManager::new(config);

    let session_key = manager.generate_session_key().await.unwrap();
    let token = manager.create_token(&session_key).await.unwrap();

    assert!(manager.validate_token(&token).await.unwrap());

    // Wait for expiration
    tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;

    let is_expired = manager.is_expired(&token).await.unwrap();
    assert!(is_expired);
}

// Tests 16-20: Trust boundary enforcement and access control
#[tokio::test]
async fn test_16_trust_context_creation() {
    let context = TrustContext::new("user_123".to_string(), "agent_456".to_string());
    assert_eq!(context.user_id, "user_123");
    assert_eq!(context.agent_id, "agent_456");
}

#[tokio::test]
async fn test_17_trust_boundary_deny_by_default() {
    let boundary = TrustBoundary::default();
    let context = TrustContext::new("user_123".to_string(), "agent_456".to_string());

    let decision = boundary.evaluate(&context).unwrap();
    assert_eq!(decision, siss_zero_trust::AccessDecision::Deny);
}

#[tokio::test]
async fn test_18_trust_boundary_allow_with_policy() {
    let mut boundary = TrustBoundary::default();
    boundary
        .add_trust_policy("user_123".to_string(), "agent_456".to_string())
        .unwrap();

    let context = TrustContext::new("user_123".to_string(), "agent_456".to_string());
    let decision = boundary.evaluate_with_policies(&context).unwrap();

    assert_eq!(decision, siss_zero_trust::AccessDecision::Allow);
}

#[tokio::test]
async fn test_19_all_requests_validated_zero_trust() {
    let engine = KeyRotationEngine::new().await;
    let result = engine.verify_zero_trust().await;
    assert!(result.is_ok());
    assert!(result.unwrap());
}

#[tokio::test]
async fn test_20_trust_boundary_enforced_post_rotation() {
    let engine = KeyRotationEngine::new().await;
    let mut boundary = TrustBoundary::default();
    boundary
        .add_trust_policy("user_123".to_string(), "agent_456".to_string())
        .unwrap();

    // Rotate keys
    engine.rotate_keys_live().await.unwrap();

    // Trust boundary should still be enforced
    let context = TrustContext::new("user_789".to_string(), "agent_999".to_string());
    let decision = boundary.evaluate_with_policies(&context).unwrap();
    assert_eq!(decision, siss_zero_trust::AccessDecision::Deny);
}
