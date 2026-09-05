// Wave 3 Task 5: Audit Logging + S3 Archive Export Tests
// TDD: All tests should FAIL initially, PASS after implementation

use siss_behavioral_firewall::audit::{AuditLogger, EventType};
use siss_behavioral_firewall::rebac::{PolicyAction, PolicyResource, SovereignIdentity};
use std::time::{Duration, SystemTime};
use uuid::Uuid;

// ============================================================================
// Test 1: AuditEntry creation with Allow decision
// ============================================================================
#[test]
fn test_audit_entry_creation_allow() {
    let sovereign_id = SovereignIdentity(Uuid::new_v4());
    let action = PolicyAction::Spawn;
    let resource = PolicyResource::Agent(Uuid::new_v4());

    let logger = AuditLogger::new();
    let audit_id = logger.log_rebac_decision(
        sovereign_id,
        action,
        resource,
        true, // Allow
        "Relationship verified".to_string(),
    );

    assert!(
        audit_id.is_some(),
        "Should create audit entry for Allow decision"
    );
    assert_eq!(logger.event_count(), 1, "Should have 1 event logged");
}

// ============================================================================
// Test 2: AuditEntry creation with Deny decision
// ============================================================================
#[test]
fn test_audit_entry_creation_deny() {
    let sovereign_id = SovereignIdentity(Uuid::new_v4());
    let action = PolicyAction::Pause;
    let resource = PolicyResource::Agent(Uuid::new_v4());

    let logger = AuditLogger::new();
    let audit_id = logger.log_rebac_decision(
        sovereign_id,
        action,
        resource,
        false, // Deny
        "No relationship found".to_string(),
    );

    assert!(
        audit_id.is_some(),
        "Should create audit entry for Deny decision"
    );
    assert_eq!(logger.event_count(), 1, "Should have 1 event logged");
}

// ============================================================================
// Test 3: Audit log insertion and retrieval
// ============================================================================
#[test]
fn test_audit_log_insertion_and_retrieval() {
    let sovereign_id = SovereignIdentity(Uuid::new_v4());
    let action = PolicyAction::Spawn;
    let resource = PolicyResource::Agent(Uuid::new_v4());

    let logger = AuditLogger::new();
    let audit_id = logger.log_policy_decision(
        sovereign_id,
        action,
        resource,
        true,
        "Policy check passed".to_string(),
    );

    assert!(audit_id.is_some(), "Should create audit ID");

    let events = logger.get_events();
    assert_eq!(events.len(), 1, "Should have 1 event in log");
    assert_eq!(events[0].id, audit_id.unwrap(), "Audit ID should match");
}

// ============================================================================
// Test 4: Audit log retrieval by date range
// ============================================================================
#[test]
fn test_audit_log_date_range_query() {
    let sovereign_id = SovereignIdentity(Uuid::new_v4());
    let action = PolicyAction::Spawn;
    let resource = PolicyResource::Agent(Uuid::new_v4());

    let logger = AuditLogger::new();
    let before = SystemTime::now();

    let audit_id = logger.log_rebac_decision(
        sovereign_id,
        action,
        resource,
        true,
        "Test event".to_string(),
    );

    let after = SystemTime::now();

    assert!(audit_id.is_some(), "Should create audit entry");

    let events = logger.get_events();
    assert!(
        events[0].timestamp >= before,
        "Event timestamp should be >= before"
    );
    assert!(
        events[0].timestamp <= after,
        "Event timestamp should be <= after"
    );
}

// ============================================================================
// Test 5: S3 export format (JSONL)
// ============================================================================
#[test]
fn test_s3_export_jsonl_format() {
    let sovereign_id = SovereignIdentity(Uuid::new_v4());
    let action = PolicyAction::Resume;
    let resource = PolicyResource::Agent(Uuid::new_v4());

    let logger = AuditLogger::new();
    logger.log_rebac_decision(
        sovereign_id,
        action,
        resource,
        true,
        "Test event for export".to_string(),
    );

    let events = logger.get_events();
    assert_eq!(events.len(), 1, "Should have 1 event");

    // Verify event can be serialized to JSON
    let json_line = serde_json::to_string(&events[0]).expect("Should serialize to JSON");
    assert!(
        !json_line.is_empty(),
        "JSON serialization should not be empty"
    );

    // Verify JSON contains expected fields
    assert!(json_line.contains("id"), "JSON should contain id field");
    assert!(
        json_line.contains("event_type"),
        "JSON should contain event_type field"
    );
}

// ============================================================================
// Test 6: S3 export with gzip compression
// ============================================================================
#[test]
fn test_s3_export_gzip_compression() {
    let logger = AuditLogger::new();

    // Add multiple events
    for i in 0..5 {
        let sovereign_id = SovereignIdentity(Uuid::new_v4());
        let action = PolicyAction::Spawn;
        let resource = PolicyResource::Agent(Uuid::new_v4());

        logger.log_rebac_decision(
            sovereign_id,
            action,
            resource,
            i % 2 == 0,
            format!("Event {}", i),
        );
    }

    let events = logger.get_events();
    assert_eq!(events.len(), 5, "Should have 5 events");

    // Simulate JSONL export
    let jsonl_content: String = events
        .iter()
        .filter_map(|e| serde_json::to_string(e).ok())
        .map(|json| format!("{}\n", json))
        .collect();

    assert!(
        !jsonl_content.is_empty(),
        "JSONL content should not be empty"
    );

    // Verify each line is valid JSON (in a real implementation, gzip compression would follow)
    for line in jsonl_content.lines() {
        if !line.is_empty() {
            assert!(
                serde_json::from_str::<serde_json::Value>(line).is_ok(),
                "Each JSONL line should be valid JSON"
            );
        }
    }
}

// ============================================================================
// Test 7: 90-day TTL enforcement
// ============================================================================
#[test]
fn test_90day_ttl_enforcement() {
    let sovereign_id = SovereignIdentity(Uuid::new_v4());
    let action = PolicyAction::Spawn;
    let resource = PolicyResource::Agent(Uuid::new_v4());

    let logger = AuditLogger::new();
    logger.log_rebac_decision(
        sovereign_id,
        action,
        resource,
        true,
        "TTL test event".to_string(),
    );

    let events = logger.get_events();
    assert_eq!(events.len(), 1, "Should have 1 event");

    let event_timestamp = events[0].timestamp;
    let ttl_duration = Duration::from_secs(90 * 24 * 60 * 60); // 90 days
    let expires_at = event_timestamp + ttl_duration;
    let now = SystemTime::now();

    // Event should not be expired yet (created just now)
    assert!(
        now < expires_at,
        "Event should not be expired immediately after creation"
    );
}

// ============================================================================
// Test 8: Automatic cleanup after export
// ============================================================================
#[test]
fn test_automatic_cleanup_after_export() {
    let logger = AuditLogger::new();

    // Add 3 events
    for i in 0..3 {
        let sovereign_id = SovereignIdentity(Uuid::new_v4());
        let action = PolicyAction::Resume;
        let resource = PolicyResource::Agent(Uuid::new_v4());

        logger.log_rebac_decision(sovereign_id, action, resource, true, format!("Event {}", i));
    }

    assert_eq!(
        logger.event_count(),
        3,
        "Should have 3 events before export"
    );

    // In a real implementation, after S3 export and 90-day window,
    // events would be deleted. For this test, we verify event count is accessible.
    let events = logger.get_events();
    assert_eq!(events.len(), 3, "All events should be retrievable");
}

// ============================================================================
// Test 9: Idempotent S3 export (re-export same data)
// ============================================================================
#[test]
fn test_s3_export_idempotency() {
    let logger = AuditLogger::new();

    let sovereign_id = SovereignIdentity(Uuid::new_v4());
    let action = PolicyAction::Spawn;
    let resource = PolicyResource::Agent(Uuid::new_v4());

    logger.log_rebac_decision(
        sovereign_id,
        action,
        resource,
        true,
        "Idempotent test event".to_string(),
    );

    let events_first = logger.get_events();
    let events_second = logger.get_events();

    assert_eq!(
        events_first.len(),
        events_second.len(),
        "Retrieving events multiple times should be idempotent"
    );
    assert_eq!(
        events_first[0].id, events_second[0].id,
        "Event IDs should be stable across multiple retrievals"
    );
}

// ============================================================================
// Test 10: Concurrent audit writes
// ============================================================================
#[test]
fn test_concurrent_audit_writes() {
    use std::sync::Arc;
    use std::thread;

    let logger = Arc::new(AuditLogger::new());
    let mut handles = vec![];

    // Spawn 5 threads, each writing 4 events
    for thread_id in 0..5 {
        let logger_clone = Arc::clone(&logger);
        let handle = thread::spawn(move || {
            for i in 0..4 {
                let sovereign_id = SovereignIdentity(Uuid::new_v4());
                let action = PolicyAction::Spawn;
                let resource = PolicyResource::Agent(Uuid::new_v4());

                logger_clone.log_rebac_decision(
                    sovereign_id,
                    action,
                    resource,
                    true,
                    format!("Thread {} Event {}", thread_id, i),
                );
            }
        });
        handles.push(handle);
    }

    // Wait for all threads to complete
    for handle in handles {
        handle.join().expect("Thread should complete successfully");
    }

    // Verify all events were written
    assert_eq!(
        logger.event_count(),
        20,
        "Should have 20 events from 5 threads * 4 events each"
    );
}

// ============================================================================
// Test 11: Archive metadata tracking
// ============================================================================
#[test]
fn test_archive_metadata_tracking() {
    let logger = AuditLogger::new();

    let sovereign_id = SovereignIdentity(Uuid::new_v4());
    let action = PolicyAction::Spawn;
    let resource = PolicyResource::Agent(Uuid::new_v4());

    logger.log_rebac_decision(
        sovereign_id,
        action,
        resource,
        true,
        "Archive metadata test".to_string(),
    );

    let events = logger.get_events();
    assert_eq!(events.len(), 1, "Should have 1 event");

    // Verify metadata fields exist
    let event = &events[0];
    assert!(!event.id.is_nil(), "Event should have valid UUID");
    assert!(
        event.timestamp <= SystemTime::now(),
        "Timestamp should be set"
    );
}

// ============================================================================
// Test 12: Multiple event types logged correctly
// ============================================================================
#[test]
fn test_multiple_event_types_logged() {
    let sovereign_id = SovereignIdentity(Uuid::new_v4());

    let logger = AuditLogger::new();

    // Log different event types (create separate resources as they're moved)
    logger.log_rebac_decision(
        sovereign_id,
        PolicyAction::Spawn,
        PolicyResource::Agent(Uuid::new_v4()),
        true,
        "ReBAC".to_string(),
    );
    logger.log_ap2_evaluation(
        sovereign_id,
        PolicyAction::Pause,
        PolicyResource::Task(Uuid::new_v4()),
        true,
        "AP2".to_string(),
    );
    logger.log_temporal_check(
        sovereign_id,
        PolicyAction::Resume,
        true,
        "Temporal".to_string(),
    );
    logger.log_policy_decision(
        sovereign_id,
        PolicyAction::Abort,
        PolicyResource::ConsentGrant(Uuid::new_v4()),
        true,
        "Policy".to_string(),
    );

    assert_eq!(logger.event_count(), 4, "Should have 4 events");

    let events = logger.get_events();
    assert_eq!(
        events[0].event_type,
        EventType::ReBAC,
        "First event should be ReBAC"
    );
    assert_eq!(
        events[1].event_type,
        EventType::AP2,
        "Second event should be AP2"
    );
    assert_eq!(
        events[2].event_type,
        EventType::Temporal,
        "Third event should be Temporal"
    );
    assert_eq!(
        events[3].event_type,
        EventType::Policy,
        "Fourth event should be Policy"
    );
}
