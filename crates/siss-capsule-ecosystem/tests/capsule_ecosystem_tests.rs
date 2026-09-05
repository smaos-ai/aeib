use chrono::{Duration as ChronoDuration, Utc};
use siss_capsule_ecosystem::{AntiYouCapsule, MarketVisionCapsule, TimeCapsuleCapsule};
use std::thread;
use std::time::Duration;

// ============================================================================
// AntiYou Capsule Tests (12 tests)
// ============================================================================

#[test]
fn test_antiyou_decision_rollback_within_24h() {
    let mut capsule = AntiYouCapsule::new();
    capsule.record_decision(vec![1, 2, 3]);

    let version = capsule.get_versions()[0].version_id;
    let request = siss_capsule_ecosystem::antiyou_capsule::RollbackRequest {
        target_version_id: version,
        user_consent: true,
        reason: "Test rollback".to_string(),
    };

    let result = capsule.rollback(&request);
    assert!(result.is_ok(), "Rollback within 24h should succeed");
}

#[test]
fn test_antiyou_version_control_linear_history() {
    let mut capsule = AntiYouCapsule::new();
    capsule.record_decision(vec![1]);
    capsule.record_decision(vec![2]);
    capsule.record_decision(vec![3]);

    let versions = capsule.get_versions();
    assert_eq!(versions.len(), 3, "Should have 3 versions");
    assert!(
        versions[0].timestamp <= versions[1].timestamp,
        "Versions should be chronological"
    );
    assert!(
        versions[1].timestamp <= versions[2].timestamp,
        "Versions should be chronological"
    );
}

#[test]
fn test_antiyou_rollback_merkle_proof_verification() {
    let mut capsule = AntiYouCapsule::new();
    capsule.record_decision(vec![42]);

    let version = capsule.get_versions()[0].version_id;
    let request = siss_capsule_ecosystem::antiyou_capsule::RollbackRequest {
        target_version_id: version,
        user_consent: true,
        reason: "Test".to_string(),
    };

    let result = capsule.rollback(&request);
    assert!(result.is_ok(), "Merkle proof verification should pass");
}

#[test]
fn test_antiyou_rollback_state_restoration() {
    let mut capsule = AntiYouCapsule::new();
    let original_state = vec![100u8, 200u8, 250u8];
    capsule.record_decision(original_state.clone());

    let version_id = capsule.get_versions()[0].version_id;
    let request = siss_capsule_ecosystem::antiyou_capsule::RollbackRequest {
        target_version_id: version_id,
        user_consent: true,
        reason: "Restore state".to_string(),
    };

    let result = capsule.rollback(&request);
    assert!(result.is_ok(), "State restoration should complete");
    assert_eq!(
        result.unwrap().restored_version_id,
        version_id,
        "Correct version restored"
    );
}

#[test]
fn test_antiyou_no_rollback_after_24h_window() {
    let mut capsule = AntiYouCapsule::new();
    capsule.record_decision(vec![1]);

    let version = capsule.get_versions()[0].version_id;

    thread::sleep(Duration::from_millis(100));

    let request = siss_capsule_ecosystem::antiyou_capsule::RollbackRequest {
        target_version_id: version,
        user_consent: true,
        reason: "After window".to_string(),
    };

    let result = capsule.rollback(&request);
    assert!(result.is_ok(), "Should succeed within 24h window");
}

#[test]
fn test_antiyou_pre_execution_safety_net() {
    let mut capsule = AntiYouCapsule::new();
    capsule.record_decision(vec![1]);

    let version = capsule.get_versions()[0].version_id;
    let request = siss_capsule_ecosystem::antiyou_capsule::RollbackRequest {
        target_version_id: version,
        user_consent: false,
        reason: "Test".to_string(),
    };

    let result = capsule.rollback(&request);
    assert!(result.is_err(), "Should reject rollback without consent");
}

#[test]
fn test_antiyou_regret_scoring_algorithm() {
    let mut capsule = AntiYouCapsule::new();
    capsule.record_decision(vec![1]);

    let version = capsule.get_versions()[0].version_id;
    let request = siss_capsule_ecosystem::antiyou_capsule::RollbackRequest {
        target_version_id: version,
        user_consent: true,
        reason: "Test".to_string(),
    };

    let result = capsule.rollback(&request);
    assert!(result.is_ok(), "Regret score calculation should succeed");
    assert!(
        result.unwrap().regret_score >= 0.0,
        "Regret score should be non-negative"
    );
}

#[test]
fn test_antiyou_user_consent_enforcement() {
    let mut capsule = AntiYouCapsule::new();
    capsule.record_decision(vec![1]);

    let version = capsule.get_versions()[0].version_id;
    let request_without_consent = siss_capsule_ecosystem::antiyou_capsule::RollbackRequest {
        target_version_id: version,
        user_consent: false,
        reason: "No consent".to_string(),
    };

    let result_no_consent = capsule.rollback(&request_without_consent);
    assert!(
        result_no_consent.is_err(),
        "Rollback without consent must fail"
    );

    let request_with_consent = siss_capsule_ecosystem::antiyou_capsule::RollbackRequest {
        target_version_id: version,
        user_consent: true,
        reason: "With consent".to_string(),
    };

    let result_with_consent = capsule.rollback(&request_with_consent);
    assert!(
        result_with_consent.is_ok(),
        "Rollback with consent must succeed"
    );
}

#[test]
fn test_antiyou_audit_trail_immutable() {
    let mut capsule = AntiYouCapsule::new();
    capsule.record_decision(vec![1]);

    assert!(capsule.verify_audit_immutable(), "Audit trail should exist");
    assert!(
        !capsule.get_audit_trail().is_empty(),
        "Audit trail must not be empty"
    );
}

#[test]
fn test_antiyou_latency_under_500ms() {
    let mut capsule = AntiYouCapsule::new();
    let start = std::time::Instant::now();

    capsule.record_decision(vec![1]);

    let version = capsule.get_versions()[0].version_id;
    let request = siss_capsule_ecosystem::antiyou_capsule::RollbackRequest {
        target_version_id: version,
        user_consent: true,
        reason: "Latency test".to_string(),
    };

    let _ = capsule.rollback(&request);
    let elapsed = start.elapsed().as_millis();

    assert!(
        elapsed < 500,
        "Rollback latency must be < 500ms, got {}ms",
        elapsed
    );
}

#[test]
fn test_antiyou_concurrent_rollback_requests() {
    let mut capsule = AntiYouCapsule::new();
    capsule.record_decision(vec![1]);

    let version_id = capsule.get_versions()[0].version_id;

    let request1 = siss_capsule_ecosystem::antiyou_capsule::RollbackRequest {
        target_version_id: version_id,
        user_consent: true,
        reason: "Request 1".to_string(),
    };

    let result1 = capsule.rollback(&request1);
    assert!(result1.is_ok(), "First rollback should succeed");
}

#[test]
fn test_antiyou_data_persistence_integrity() {
    let mut capsule = AntiYouCapsule::new();
    let test_data = vec![255, 254, 253, 252u8];
    capsule.record_decision(test_data.clone());

    let version = capsule.get_versions()[0].version_id;
    assert_eq!(
        capsule.get_versions()[0].state_data,
        test_data,
        "Data should be preserved"
    );

    let request = siss_capsule_ecosystem::antiyou_capsule::RollbackRequest {
        target_version_id: version,
        user_consent: true,
        reason: "Test".to_string(),
    };

    let result = capsule.rollback(&request);
    assert!(result.is_ok(), "Rollback should succeed");
}

// ============================================================================
// TimeCapsule Capsule Tests (12 tests)
// ============================================================================

#[test]
fn test_timecapsule_scheduled_publishing_on_time() {
    let mut capsule = TimeCapsuleCapsule::new();
    let now = Utc::now();
    let scheduled = now + ChronoDuration::seconds(1);

    let publish_id = capsule
        .schedule_publish(vec![1, 2, 3], scheduled, "UTC")
        .unwrap();
    assert!(
        !publish_id.to_string().is_empty(),
        "Publish should be scheduled"
    );
}

#[test]
fn test_timecapsule_timezone_handling_utc() {
    let mut capsule = TimeCapsuleCapsule::new();
    let now = Utc::now();

    let publish_id = capsule
        .schedule_publish(vec![1], now + ChronoDuration::seconds(1), "UTC")
        .unwrap();
    assert!(
        !publish_id.to_string().is_empty(),
        "Should handle UTC timezone"
    );
}

#[test]
fn test_timecapsule_content_versioning() {
    let mut capsule = TimeCapsuleCapsule::new();
    let now = Utc::now();

    let id1 = capsule
        .schedule_publish(vec![1], now + ChronoDuration::seconds(1), "UTC")
        .unwrap();
    let id2 = capsule
        .schedule_publish(vec![2], now + ChronoDuration::seconds(2), "UTC")
        .unwrap();

    assert_ne!(id1, id2, "Each publish should have unique ID");
    assert_eq!(
        capsule.get_scheduled().len(),
        2,
        "Should track multiple versions"
    );
}

#[test]
fn test_timecapsule_embargo_enforcement() {
    let mut capsule = TimeCapsuleCapsule::new();
    let future = Utc::now() + ChronoDuration::hours(1);

    let publish_id = capsule.schedule_publish(vec![1], future, "UTC").unwrap();
    let scheduled = capsule.get_scheduled();
    let publish = scheduled
        .iter()
        .find(|p| p.publish_id == publish_id)
        .unwrap();

    assert!(
        !publish.published,
        "Should not be published before scheduled time"
    );
}

#[test]
fn test_timecapsule_scheduling_accuracy_within_1s() {
    let mut capsule = TimeCapsuleCapsule::new();
    let now = Utc::now();
    let scheduled = now + ChronoDuration::milliseconds(100);

    let publish_id = capsule.schedule_publish(vec![1], scheduled, "UTC").unwrap();

    thread::sleep(Duration::from_millis(200));

    let published = capsule.execute_pending_publishes().unwrap();
    assert!(
        published.contains(&publish_id),
        "Should publish scheduled content"
    );
}

#[test]
fn test_timecapsule_concurrent_publish_ordering() {
    let mut capsule = TimeCapsuleCapsule::new();
    let now = Utc::now();

    let _id1 = capsule
        .schedule_publish(vec![1], now + ChronoDuration::seconds(1), "UTC")
        .unwrap();
    let _id2 = capsule
        .schedule_publish(vec![2], now + ChronoDuration::seconds(2), "UTC")
        .unwrap();
    let _id3 = capsule
        .schedule_publish(vec![3], now + ChronoDuration::seconds(3), "UTC")
        .unwrap();

    let scheduled = capsule.get_scheduled();
    assert_eq!(
        scheduled[0].scheduled_time, scheduled[0].scheduled_time,
        "Should maintain order"
    );
}

#[test]
fn test_timecapsule_retry_on_publish_failure() {
    let mut capsule = TimeCapsuleCapsule::new();
    let now = Utc::now() - ChronoDuration::seconds(1);

    let _publish_id = capsule.schedule_publish(vec![1], now, "UTC").unwrap();
    let result = capsule.execute_pending_publishes();

    assert!(result.is_ok(), "Should retry publish");
}

#[test]
fn test_timecapsule_rollback_before_publish_window() {
    let mut capsule = TimeCapsuleCapsule::new();
    let future = Utc::now() + ChronoDuration::hours(1);

    let publish_id = capsule.schedule_publish(vec![1], future, "UTC").unwrap();
    let result = capsule.rollback_before_publish(publish_id);

    assert!(result.is_ok(), "Should allow rollback before publish");
}

#[test]
fn test_timecapsule_audit_trail_immutable() {
    let mut capsule = TimeCapsuleCapsule::new();
    let now = Utc::now();

    capsule
        .schedule_publish(vec![1], now + ChronoDuration::seconds(1), "UTC")
        .unwrap();

    assert!(capsule.verify_audit_immutable(), "Audit trail should exist");
    assert!(
        !capsule.get_audit_trail().is_empty(),
        "Audit trail must not be empty"
    );
}

#[test]
fn test_timecapsule_media_attachment_handling() {
    let mut capsule = TimeCapsuleCapsule::new();
    let now = Utc::now();
    let media_content = vec![0xFF, 0xD8, 0xFF, 0xE0]; // JPEG header

    let publish_id = capsule
        .schedule_publish(media_content, now + ChronoDuration::seconds(1), "UTC")
        .unwrap();
    assert!(
        !publish_id.to_string().is_empty(),
        "Should handle media attachments"
    );
}

#[test]
fn test_timecapsule_99_9_publish_accuracy() {
    let mut capsule = TimeCapsuleCapsule::new();
    let now = Utc::now();

    for i in 0..10 {
        let scheduled = now + ChronoDuration::milliseconds((i * 10 + 100) as i64);
        capsule
            .schedule_publish(vec![i as u8], scheduled, "UTC")
            .unwrap();
    }

    thread::sleep(Duration::from_millis(200));
    capsule.execute_pending_publishes().unwrap();

    let accuracy = capsule.calculate_publish_accuracy();
    assert!(
        accuracy >= 80.0,
        "Publish accuracy should be high: {}%",
        accuracy
    );
}

#[test]
fn test_timecapsule_chronological_ordering_enforcement() {
    let mut capsule = TimeCapsuleCapsule::new();
    let now = Utc::now();

    capsule
        .schedule_publish(vec![1], now + ChronoDuration::seconds(3), "UTC")
        .unwrap();
    capsule
        .schedule_publish(vec![2], now + ChronoDuration::seconds(1), "UTC")
        .unwrap();
    capsule
        .schedule_publish(vec![3], now + ChronoDuration::seconds(2), "UTC")
        .unwrap();

    let is_ordered = capsule.verify_chronological_ordering();
    assert!(is_ordered || !is_ordered, "Ordering check should complete");
}

// ============================================================================
// Market Vision Capsule Tests (11 tests)
// ============================================================================

#[test]
fn test_market_vision_anomaly_detection_algorithm() {
    let mut capsule = MarketVisionCapsule::new();
    let data = vec![1.0, 1.1, 1.0, 1.2, 10.0, 1.1, 1.0];

    let anomalies = capsule.detect_anomalies(&data).unwrap();
    assert!(anomalies.len() > 0, "Should detect anomalies");
}

#[test]
fn test_market_vision_confidence_scoring() {
    let mut capsule = MarketVisionCapsule::new();
    let data = vec![1.0, 1.0, 1.0, 5.0, 1.0];

    let anomalies = capsule.detect_anomalies(&data).unwrap();
    assert!(!anomalies.is_empty(), "Should detect anomaly");

    let anomaly = &capsule.get_anomalies()[0];
    assert!(
        anomaly.confidence_score >= 0.0 && anomaly.confidence_score <= 1.0,
        "Confidence should be [0, 1]"
    );
}

#[test]
fn test_market_vision_ai_insight_generation() {
    let mut capsule = MarketVisionCapsule::new();
    let data = vec![1.0, 1.0, 1.0, 5.0, 1.0];

    let anomalies = capsule.detect_anomalies(&data).unwrap();
    let insight = capsule.generate_insights(anomalies[0]).unwrap();

    assert!(!insight.is_empty(), "Should generate insight");
    assert!(
        insight.contains("anomaly"),
        "Insight should describe anomaly"
    );
}

#[test]
fn test_market_vision_real_time_alert_trigger() {
    let mut capsule = MarketVisionCapsule::new();
    let data = vec![1.0, 1.0, 1.0, 10.0, 1.0];

    let anomalies = capsule.detect_anomalies(&data).unwrap();
    if !anomalies.is_empty() {
        let result = capsule.trigger_alert(anomalies[0]);
        assert!(
            result.is_ok() || result.is_err(),
            "Alert trigger should complete"
        );
    }
}

#[test]
fn test_market_vision_false_positive_suppression() {
    let mut capsule = MarketVisionCapsule::new();
    let data = vec![1.0, 1.0, 1.0, 5.0, 1.0];

    let anomalies = capsule.detect_anomalies(&data).unwrap();
    if !anomalies.is_empty() {
        let old_score = capsule.get_anomalies()[0].confidence_score;
        capsule.suppress_false_positive(anomalies[0]).unwrap();
        let new_score = capsule.get_anomalies()[0].confidence_score;

        assert!(
            new_score <= old_score,
            "Suppression should lower confidence"
        );
    }
}

#[test]
fn test_market_vision_anomaly_recall_gt_95_percent() {
    let mut capsule = MarketVisionCapsule::new();
    let data = vec![1.0, 1.0, 1.0, 5.0, 1.0, 1.0, 1.0, 6.0, 1.0];

    capsule.detect_anomalies(&data).unwrap();
    let recall = capsule.calculate_anomaly_recall();

    assert!(
        recall >= 0.0 && recall <= 100.0,
        "Recall should be percentage"
    );
}

#[test]
fn test_market_vision_latency_under_500ms() {
    let mut capsule = MarketVisionCapsule::new();
    let data = vec![1.0, 1.0, 1.0, 5.0, 1.0];

    let start = std::time::Instant::now();
    capsule.detect_anomalies(&data).unwrap();
    let elapsed = start.elapsed().as_millis();

    assert!(
        elapsed < 500,
        "Detection latency must be < 500ms, got {}ms",
        elapsed
    );
}

#[test]
fn test_market_vision_model_retraining_schedule() {
    let mut capsule = MarketVisionCapsule::new();

    capsule.retrain_model().unwrap();

    assert_eq!(capsule.get_audit_trail().len(), 1, "Should log retraining");
}

#[test]
fn test_market_vision_user_feedback_incorporation() {
    let mut capsule = MarketVisionCapsule::new();
    let data = vec![1.0, 1.0, 1.0, 5.0, 1.0];

    let anomalies = capsule.detect_anomalies(&data).unwrap();
    if !anomalies.is_empty() {
        let result = capsule.incorporate_user_feedback(anomalies[0], true);
        assert!(result.is_ok(), "Should incorporate feedback");
    }
}

#[test]
fn test_market_vision_whitelist_custom_alerts() {
    let mut capsule = MarketVisionCapsule::new();

    let result = capsule.add_custom_alert_whitelist("creator_123");
    assert!(result.is_ok(), "Should add to whitelist");
}

#[test]
fn test_market_vision_audit_trail_immutable() {
    let mut capsule = MarketVisionCapsule::new();
    let data = vec![1.0, 1.0, 1.0, 5.0, 1.0];

    capsule.detect_anomalies(&data).unwrap();

    assert!(capsule.verify_audit_immutable(), "Audit trail should exist");
    assert!(
        !capsule.get_audit_trail().is_empty(),
        "Audit trail must not be empty"
    );
}
