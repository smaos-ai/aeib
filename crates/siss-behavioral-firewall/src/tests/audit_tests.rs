// Phase 25 Wave 3: Audit + Archive Infrastructure Tests
// Comprehensive TDD test suite for audit logging and merkle archive

use crate::audit::{
    AuditLogger, EventType, AuditArchive, MerkleArchive,
};
use crate::rebac::{SovereignIdentity, PolicyAction, PolicyResource, ReBAC, RelationType};
use std::time::Duration;
use uuid::Uuid;

fn test_identity(id: u64) -> SovereignIdentity {
    SovereignIdentity(Uuid::from_u64_pair(id, 0))
}

fn test_resource() -> PolicyResource {
    PolicyResource::Agent(Uuid::from_u64_pair(1, 0))
}

// ============================================================================
// AUDIT LOGGER TESTS
// ============================================================================

#[test]
fn test_audit_logger_create_empty() {
    let logger = AuditLogger::new();
    assert_eq!(logger.event_count(), 0);
}

#[test]
fn test_audit_logger_log_rebac_decision() {
    let logger = AuditLogger::new();
    let identity = test_identity(1);
    let resource = test_resource();

    let event_id = logger.log_rebac_decision(
        identity,
        PolicyAction::Spawn,
        resource,
        true,
        "Owner relationship exists".to_string(),
    );

    assert!(event_id.is_some());
    assert_eq!(logger.event_count(), 1);
}

#[test]
fn test_audit_logger_log_ap2_evaluation() {
    let logger = AuditLogger::new();
    let identity = test_identity(2);
    let resource = test_resource();

    let event_id = logger.log_ap2_evaluation(
        identity,
        PolicyAction::ReadMetrics,
        resource,
        true,
        "TrustLevel 85 >= 50".to_string(),
    );

    assert!(event_id.is_some());
    assert_eq!(logger.event_count(), 1);
}

#[test]
fn test_audit_logger_log_temporal_check() {
    let logger = AuditLogger::new();
    let identity = test_identity(3);

    let event_id = logger.log_temporal_check(
        identity,
        PolicyAction::AssignTask,
        true,
        "Rate limit OK (5/10 tokens used)".to_string(),
    );

    assert!(event_id.is_some());
    assert_eq!(logger.event_count(), 1);
}

#[test]
fn test_audit_logger_log_policy_decision() {
    let logger = AuditLogger::new();
    let identity = test_identity(4);
    let resource = test_resource();

    let event_id = logger.log_policy_decision(
        identity,
        PolicyAction::CreatePolicy,
        resource,
        false,
        "Policy conflicts with existing mandate".to_string(),
    );

    assert!(event_id.is_some());
    assert_eq!(logger.event_count(), 1);
}

#[test]
fn test_audit_logger_multiple_events() {
    let logger = AuditLogger::new();
    let identity1 = test_identity(1);
    let identity2 = test_identity(2);
    let resource = test_resource();

    logger.log_rebac_decision(identity1, PolicyAction::Spawn, resource.clone(), true, "Ok".to_string());
    logger.log_ap2_evaluation(identity2, PolicyAction::ReadMetrics, resource.clone(), true, "Ok".to_string());
    logger.log_temporal_check(identity1, PolicyAction::AssignTask, false, "Rate limit exceeded".to_string());
    logger.log_policy_decision(identity2, PolicyAction::DeletePolicy, resource, true, "Permitted".to_string());

    assert_eq!(logger.event_count(), 4);
}

#[test]
fn test_audit_logger_event_immutability() {
    let logger = AuditLogger::new();
    let identity = test_identity(1);
    let resource = test_resource();

    logger.log_rebac_decision(identity, PolicyAction::Spawn, resource, true, "Test".to_string());

    let events = logger.get_events();
    assert_eq!(events.len(), 1);
    assert!(events[0].timestamp.elapsed().unwrap() < Duration::from_secs(1));
}

#[test]
fn test_audit_logger_get_events_immutable_copy() {
    let logger = AuditLogger::new();
    let identity = test_identity(1);
    let resource = test_resource();

    logger.log_rebac_decision(identity, PolicyAction::Spawn, resource, true, "Event1".to_string());

    let events1 = logger.get_events();
    let events2 = logger.get_events();

    assert_eq!(events1.len(), events2.len());
    assert_eq!(events1[0].id, events2[0].id);
}

#[test]
fn test_audit_logger_query_by_identity() {
    let logger = AuditLogger::new();
    let identity1 = test_identity(1);
    let identity2 = test_identity(2);
    let resource = test_resource();

    logger.log_rebac_decision(identity1, PolicyAction::Spawn, resource.clone(), true, "Ev1".to_string());
    logger.log_ap2_evaluation(identity2, PolicyAction::ReadMetrics, resource.clone(), true, "Ev2".to_string());
    logger.log_rebac_decision(identity1, PolicyAction::Pause, resource, false, "Ev3".to_string());

    let identity1_events = logger.query_by_identity(identity1);
    assert_eq!(identity1_events.len(), 2);

    let identity2_events = logger.query_by_identity(identity2);
    assert_eq!(identity2_events.len(), 1);
}

#[test]
fn test_audit_logger_query_by_action() {
    let logger = AuditLogger::new();
    let identity = test_identity(1);
    let resource = test_resource();

    logger.log_rebac_decision(identity, PolicyAction::Spawn, resource.clone(), true, "A".to_string());
    logger.log_ap2_evaluation(identity, PolicyAction::ReadMetrics, resource.clone(), true, "B".to_string());
    logger.log_rebac_decision(identity, PolicyAction::Spawn, resource, false, "C".to_string());

    let spawn_events = logger.query_by_action(PolicyAction::Spawn);
    assert_eq!(spawn_events.len(), 2);

    let metrics_events = logger.query_by_action(PolicyAction::ReadMetrics);
    assert_eq!(metrics_events.len(), 1);
}

#[test]
fn test_audit_logger_query_by_event_type() {
    let logger = AuditLogger::new();
    let identity = test_identity(1);
    let resource = test_resource();

    logger.log_rebac_decision(identity, PolicyAction::Spawn, resource.clone(), true, "A".to_string());
    logger.log_ap2_evaluation(identity, PolicyAction::ReadMetrics, resource.clone(), true, "B".to_string());
    logger.log_temporal_check(identity, PolicyAction::AssignTask, true, "C".to_string());

    let rebac_events = logger.query_by_event_type(EventType::ReBAC);
    assert_eq!(rebac_events.len(), 1);

    let ap2_events = logger.query_by_event_type(EventType::AP2);
    assert_eq!(ap2_events.len(), 1);

    let temporal_events = logger.query_by_event_type(EventType::Temporal);
    assert_eq!(temporal_events.len(), 1);
}

#[test]
fn test_audit_logger_query_by_decision() {
    let logger = AuditLogger::new();
    let identity = test_identity(1);
    let resource = test_resource();

    logger.log_rebac_decision(identity, PolicyAction::Spawn, resource.clone(), true, "Allow".to_string());
    logger.log_ap2_evaluation(identity, PolicyAction::ReadMetrics, resource.clone(), false, "Deny".to_string());
    logger.log_rebac_decision(identity, PolicyAction::Pause, resource, true, "Allow".to_string());

    let allow_events = logger.query_by_decision(true);
    assert_eq!(allow_events.len(), 2);

    let deny_events = logger.query_by_decision(false);
    assert_eq!(deny_events.len(), 1);
}

// ============================================================================
// MERKLE ARCHIVE TESTS
// ============================================================================

#[test]
fn test_merkle_archive_create_empty() {
    let archive = MerkleArchive::new();
    assert_eq!(archive.snapshot_count(), 0);
    assert_eq!(archive.root_hash().len(), 32); // SHA256 hash length
}

#[test]
fn test_merkle_archive_add_snapshot() {
    let archive = MerkleArchive::new();
    let logger = AuditLogger::new();
    let identity = test_identity(1);
    let resource = test_resource();

    logger.log_rebac_decision(identity, PolicyAction::Spawn, resource, true, "Test".to_string());

    let root = archive.add_snapshot(logger.get_events());
    assert!(!root.is_empty());
    assert_eq!(archive.snapshot_count(), 1);
}

#[test]
fn test_merkle_archive_multiple_snapshots() {
    let archive = MerkleArchive::new();
    let logger1 = AuditLogger::new();
    let logger2 = AuditLogger::new();
    let identity = test_identity(1);
    let resource = test_resource();

    logger1.log_rebac_decision(identity, PolicyAction::Spawn, resource.clone(), true, "Snap1".to_string());
    let root1 = archive.add_snapshot(logger1.get_events());

    logger2.log_ap2_evaluation(identity, PolicyAction::ReadMetrics, resource, true, "Snap2".to_string());
    let root2 = archive.add_snapshot(logger2.get_events());

    assert_ne!(root1, root2);
    assert_eq!(archive.snapshot_count(), 2);
}

#[test]
fn test_merkle_archive_root_hash_consistency() {
    let archive = MerkleArchive::new();
    let logger = AuditLogger::new();
    let identity = test_identity(1);
    let resource = test_resource();

    logger.log_rebac_decision(identity, PolicyAction::Spawn, resource, true, "Test".to_string());
    archive.add_snapshot(logger.get_events());

    let root1 = archive.root_hash();
    let root2 = archive.root_hash();

    assert_eq!(root1, root2);
}

#[test]
fn test_merkle_archive_verify_snapshot() {
    let archive = MerkleArchive::new();
    let logger = AuditLogger::new();
    let identity = test_identity(1);
    let resource = test_resource();

    logger.log_rebac_decision(identity, PolicyAction::Spawn, resource, true, "Test".to_string());
    let root = archive.add_snapshot(logger.get_events());

    assert!(archive.verify_snapshot(0, &root).is_ok());
}

#[test]
fn test_merkle_archive_verify_invalid_snapshot() {
    let archive = MerkleArchive::new();
    let logger = AuditLogger::new();
    let identity = test_identity(1);
    let resource = test_resource();

    logger.log_rebac_decision(identity, PolicyAction::Spawn, resource, true, "Test".to_string());
    archive.add_snapshot(logger.get_events());

    let fake_root = vec![0u8; 32];
    let result = archive.verify_snapshot(0, &fake_root);
    assert!(result.is_ok());
    assert_eq!(result.unwrap(), false); // Verification returns Ok(false) for invalid hash
}

#[test]
fn test_merkle_archive_snapshot_chain() {
    let archive = MerkleArchive::new();
    let logger = AuditLogger::new();
    let identity = test_identity(1);
    let resource = test_resource();

    for i in 0..5 {
        logger.log_rebac_decision(
            identity,
            PolicyAction::Spawn,
            resource.clone(),
            true,
            format!("Event {}", i)
        );
        archive.add_snapshot(logger.get_events());
    }

    assert_eq!(archive.snapshot_count(), 5);
    for i in 0..5 {
        let root = archive.get_snapshot_root(i);
        assert!(root.is_some());
    }
}

#[test]
fn test_merkle_archive_proof_generation() {
    let archive = MerkleArchive::new();
    let logger = AuditLogger::new();
    let identity = test_identity(1);
    let resource = test_resource();

    logger.log_rebac_decision(identity, PolicyAction::Spawn, resource, true, "Test".to_string());
    archive.add_snapshot(logger.get_events());

    let proof = archive.get_proof(0);
    assert!(proof.is_some());
    assert!(!proof.unwrap().is_empty());
}

// ============================================================================
// AUDIT ARCHIVE INTEGRATION TESTS
// ============================================================================

#[test]
fn test_audit_archive_create() {
    let audit_archive = AuditArchive::new();
    assert_eq!(audit_archive.event_count(), 0);
    assert!(audit_archive.get_root_hash().len() > 0);
}

#[test]
fn test_audit_archive_log_and_archive() {
    let audit_archive = AuditArchive::new();
    let identity = test_identity(1);
    let resource = test_resource();

    let event_id = audit_archive.log_rebac_decision(
        identity,
        PolicyAction::Spawn,
        resource,
        true,
        "Test".to_string(),
    );

    assert!(event_id.is_some());
    assert_eq!(audit_archive.event_count(), 1);
}

#[test]
fn test_audit_archive_create_snapshot() {
    let audit_archive = AuditArchive::new();
    let identity = test_identity(1);
    let resource = test_resource();

    audit_archive.log_rebac_decision(
        identity,
        PolicyAction::Spawn,
        resource,
        true,
        "Event1".to_string(),
    );

    let root = audit_archive.create_snapshot();
    assert!(!root.is_empty());
}

#[test]
fn test_audit_archive_verify_historical_state() {
    let audit_archive = AuditArchive::new();
    let identity = test_identity(1);
    let resource = test_resource();

    audit_archive.log_rebac_decision(
        identity,
        PolicyAction::Spawn,
        resource.clone(),
        true,
        "First event".to_string(),
    );

    let root1 = audit_archive.create_snapshot();

    audit_archive.log_rebac_decision(
        identity,
        PolicyAction::Pause,
        resource,
        false,
        "Second event".to_string(),
    );

    let root2 = audit_archive.create_snapshot();

    assert_ne!(root1, root2);
    assert_eq!(audit_archive.event_count(), 2);
}

#[test]
fn test_audit_archive_replay_from_snapshot() {
    let audit_archive = AuditArchive::new();
    let identity = test_identity(1);
    let resource = test_resource();

    audit_archive.log_rebac_decision(
        identity,
        PolicyAction::Spawn,
        resource,
        true,
        "Replay test".to_string(),
    );

    let _root = audit_archive.create_snapshot();

    let events = audit_archive.get_events();
    assert_eq!(events.len(), 1);
    assert_eq!(events[0].event_type, EventType::ReBAC);
}

#[test]
fn test_audit_archive_concurrent_logging() {
    use std::sync::Arc;
    use std::thread;

    let audit_archive = Arc::new(AuditArchive::new());
    let mut handles = vec![];

    for i in 0..5 {
        let archive_clone = Arc::clone(&audit_archive);
        let handle = thread::spawn(move || {
            let identity = test_identity(i as u64);
            let resource = test_resource();
            archive_clone.log_rebac_decision(
                identity,
                PolicyAction::Spawn,
                resource,
                true,
                format!("Thread {}", i),
            );
        });
        handles.push(handle);
    }

    for handle in handles {
        handle.join().unwrap();
    }

    assert_eq!(audit_archive.event_count(), 5);
}

#[test]
fn test_audit_archive_diverse_event_types() {
    let audit_archive = AuditArchive::new();
    let identity = test_identity(1);
    let resource = test_resource();

    audit_archive.log_rebac_decision(identity, PolicyAction::Spawn, resource.clone(), true, "R".to_string());
    audit_archive.log_ap2_evaluation(identity, PolicyAction::ReadMetrics, resource.clone(), true, "A".to_string());
    audit_archive.log_temporal_check(identity, PolicyAction::AssignTask, false, "T".to_string());
    audit_archive.log_policy_decision(identity, PolicyAction::CreatePolicy, resource, true, "P".to_string());

    assert_eq!(audit_archive.event_count(), 4);

    let rebac_events = audit_archive.query_by_event_type(EventType::ReBAC);
    assert_eq!(rebac_events.len(), 1);

    let ap2_events = audit_archive.query_by_event_type(EventType::AP2);
    assert_eq!(ap2_events.len(), 1);
}

#[test]
fn test_audit_archive_consistent_root_across_replays() {
    let audit_archive = AuditArchive::new();
    let identity = test_identity(1);
    let resource = test_resource();

    for i in 0..3 {
        audit_archive.log_rebac_decision(
            identity,
            PolicyAction::Spawn,
            resource.clone(),
            true,
            format!("Event {}", i),
        );
    }

    let root1 = audit_archive.get_root_hash();
    let events = audit_archive.get_events();
    let root2 = audit_archive.get_root_hash();

    assert_eq!(root1, root2);
    assert_eq!(events.len(), 3);
}

// ============================================================================
// INTEGRATION TESTS - SUBSYSTEM LOGGING
// ============================================================================

#[test]
fn test_rebac_decision_integration() {
    let audit = AuditArchive::new();
    let rebac = ReBAC::new();
    let identity = test_identity(1);
    let resource = PolicyResource::Agent(Uuid::from_u64_pair(100, 0));

    // Grant relationship
    let _ = rebac.grant_relationship(identity, resource.clone(), RelationType::Owner, None);

    // Simulate decision with audit logging
    match rebac.verify_relationship(identity, resource.clone(), PolicyAction::Spawn) {
        Ok(reason) => {
            audit.log_rebac_decision(identity, PolicyAction::Spawn, resource, true, reason);
            assert_eq!(audit.event_count(), 1);
        }
        Err(e) => panic!("ReBAC decision failed: {:?}", e),
    }
}

#[test]
fn test_ap2_evaluation_integration() {
    let audit = AuditArchive::new();
    let identity = test_identity(2);
    let resource = test_resource();

    // Simulate AP2 evaluation with audit logging
    let reason = "TrustLevel 85 >= 50 and not blacklisted".to_string();
    audit.log_ap2_evaluation(identity, PolicyAction::ReadMetrics, resource, true, reason);

    assert_eq!(audit.event_count(), 1);
    let ap2_events = audit.query_by_event_type(EventType::AP2);
    assert_eq!(ap2_events.len(), 1);
    assert_eq!(ap2_events[0].decision, true);
}

#[test]
fn test_temporal_guard_integration() {
    let audit = AuditArchive::new();
    let identity = test_identity(3);

    // Simulate temporal guard checks with audit logging
    let reason = "Rate limit: 8/10 tokens used, decision allowed".to_string();
    audit.log_temporal_check(identity, PolicyAction::AssignTask, true, reason);

    assert_eq!(audit.event_count(), 1);
    let temporal_events = audit.query_by_event_type(EventType::Temporal);
    assert_eq!(temporal_events.len(), 1);
}

#[test]
fn test_policy_engine_decision_integration() {
    let audit = AuditArchive::new();
    let identity = test_identity(4);
    let resource = test_resource();

    // Simulate policy engine decisions with audit logging
    let reason = "Mandate created: All three phases allow action".to_string();
    audit.log_policy_decision(identity, PolicyAction::CreatePolicy, resource, true, reason);

    assert_eq!(audit.event_count(), 1);
    let policy_events = audit.query_by_event_type(EventType::Policy);
    assert_eq!(policy_events.len(), 1);
}

#[test]
fn test_multi_phase_decision_pipeline() {
    let audit = AuditArchive::new();
    let identity = test_identity(1);
    let resource = test_resource();

    // Simulate a complete decision pipeline: ReBAC → AP2 → Temporal → Policy
    audit.log_rebac_decision(
        identity,
        PolicyAction::Spawn,
        resource.clone(),
        true,
        "Owner relationship permits action".to_string(),
    );

    audit.log_ap2_evaluation(
        identity,
        PolicyAction::Spawn,
        resource.clone(),
        true,
        "TrustLevel 90 >= 50".to_string(),
    );

    audit.log_temporal_check(
        identity,
        PolicyAction::Spawn,
        true,
        "Rate limit OK (5/10 tokens)".to_string(),
    );

    audit.log_policy_decision(
        identity,
        PolicyAction::Spawn,
        resource,
        true,
        "Final mandate: ALLOW".to_string(),
    );

    assert_eq!(audit.event_count(), 4);

    // Verify all event types are present
    assert_eq!(audit.query_by_event_type(EventType::ReBAC).len(), 1);
    assert_eq!(audit.query_by_event_type(EventType::AP2).len(), 1);
    assert_eq!(audit.query_by_event_type(EventType::Temporal).len(), 1);
    assert_eq!(audit.query_by_event_type(EventType::Policy).len(), 1);

    // All decisions are Allow (true)
    assert_eq!(audit.query_by_decision(true).len(), 4);
}

#[test]
fn test_denial_path_audit_trail() {
    let audit = AuditArchive::new();
    let identity = test_identity(5);
    let resource = test_resource();

    // Simulate denial at AP2 phase
    audit.log_rebac_decision(
        identity,
        PolicyAction::DeletePolicy,
        resource.clone(),
        true,
        "Delegate relationship permits action".to_string(),
    );

    audit.log_ap2_evaluation(
        identity,
        PolicyAction::DeletePolicy,
        resource.clone(),
        false,
        "Reputation -15 < 0 threshold".to_string(),
    );

    // Temporal and Policy phases are skipped due to deny-override rule
    audit.log_policy_decision(
        identity,
        PolicyAction::DeletePolicy,
        resource,
        false,
        "Mandate: DENY (AP2 blocked)".to_string(),
    );

    assert_eq!(audit.event_count(), 3);

    // Count deny decisions
    let deny_events = audit.query_by_decision(false);
    assert_eq!(deny_events.len(), 2); // AP2 and Policy both deny
}

#[test]
fn test_audit_trail_completeness() {
    let audit = AuditArchive::new();
    let id1 = test_identity(1);
    let id2 = test_identity(2);
    let resource = test_resource();

    // Create diverse audit trail
    audit.log_rebac_decision(id1, PolicyAction::Spawn, resource.clone(), true, "R1".to_string());
    audit.log_ap2_evaluation(id1, PolicyAction::ReadMetrics, resource.clone(), true, "A1".to_string());
    audit.log_temporal_check(id1, PolicyAction::AssignTask, false, "T1".to_string());
    audit.log_policy_decision(id1, PolicyAction::CreatePolicy, resource.clone(), true, "P1".to_string());
    audit.log_rebac_decision(id2, PolicyAction::Pause, resource.clone(), false, "R2".to_string());
    audit.log_ap2_evaluation(id2, PolicyAction::ReadMetrics, resource, false, "A2".to_string());

    assert_eq!(audit.event_count(), 6);

    // Identity 1 has 4 events
    assert_eq!(audit.query_by_identity(id1).len(), 4);

    // Identity 2 has 2 events
    assert_eq!(audit.query_by_identity(id2).len(), 2);

    // 3 allow, 3 deny
    assert_eq!(audit.query_by_decision(true).len(), 3);
    assert_eq!(audit.query_by_decision(false).len(), 3);
}

#[test]
fn test_snapshot_captures_complete_state() {
    let audit = AuditArchive::new();
    let identity = test_identity(1);
    let resource = test_resource();

    // Phase 1: Log initial events
    for i in 0..3 {
        audit.log_rebac_decision(
            identity,
            PolicyAction::Spawn,
            resource.clone(),
            true,
            format!("Event {}", i),
        );
    }

    // Snapshot 1
    let root1 = audit.create_snapshot();
    assert!(!root1.is_empty());

    // Phase 2: Log additional events
    for i in 3..5 {
        audit.log_ap2_evaluation(
            identity,
            PolicyAction::ReadMetrics,
            resource.clone(),
            true,
            format!("Event {}", i),
        );
    }

    // Snapshot 2
    let root2 = audit.create_snapshot();
    assert!(!root2.is_empty());

    // Roots differ
    assert_ne!(root1, root2);

    // Total events captured
    assert_eq!(audit.event_count(), 5);
}
