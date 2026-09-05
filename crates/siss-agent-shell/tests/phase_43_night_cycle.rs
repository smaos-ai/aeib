/// Phase 43: Night Cycle & Memory Crystallization
/// 7 TDD tests covering:
/// - Compaction Trigger: heuristics for safe wake during idle (Invariant 1)
/// - Hot-to-Cold Distillation: atomic crystallization (Invariant 2)
/// - Database Pruning: safe metabolic decay (Invariant 3)
use siss_agent_shell::night_cycle::{
    CompactionDecision, CompactionTrigger, CycleError, NightCycleEngine, SwarmSnapshot,
};
use siss_agent_shell::swarm_mcp_server::SwarmStatePayload;
use siss_feedback_router::crystallizer::Crystallizer;
use siss_feedback_router::types::CrystallizedMemory;
use std::collections::HashMap;
use std::time::Duration;

/// Mock crystallizer for testing distillation failures.
struct MockCrystallizer;

impl Crystallizer for MockCrystallizer {
    fn crystallize(
        &self,
        _context: &siss_feedback_router::crystallizer::CrystallizationContext,
    ) -> Vec<CrystallizedMemory> {
        // Mock returns empty; NightCycleEngine handles the actual logic in tests
        Vec::new()
    }
}

// ============================================================================
// TEST 1: Compaction Trigger fires when all idle + count met
// ============================================================================

#[test]
fn test_trigger_fires_when_all_idle() {
    let trigger = CompactionTrigger {
        event_count_threshold: 5,
        cycle_interval: Duration::from_secs(3600),
    };

    let mut payloads = vec![];
    for i in 0..10 {
        payloads.push(SwarmStatePayload {
            idempotency_key: format!("key-{}", i),
            agent_id: "agent-1".to_string(),
            phase: "PHASE_43".to_string(),
            status: if i < 5 { "COMPLETE" } else { "FAILED" }.to_string(),
            payload_json: None,
        });
    }

    let snapshot = SwarmSnapshot {
        payloads,
        elapsed_since_last_cycle: Duration::from_secs(1),
    };

    assert_eq!(
        trigger.should_trigger(&snapshot),
        CompactionDecision::Trigger
    );
}

// ============================================================================
// TEST 2: Compaction Trigger skipped when any agent is RUNNING
// ============================================================================

#[test]
fn test_trigger_skipped_when_any_running() {
    let trigger = CompactionTrigger {
        event_count_threshold: 5,
        cycle_interval: Duration::from_secs(3600),
    };

    let mut payloads = vec![];
    for i in 0..10 {
        payloads.push(SwarmStatePayload {
            idempotency_key: format!("key-{}", i),
            agent_id: "agent-1".to_string(),
            phase: "PHASE_43".to_string(),
            status: if i == 0 { "RUNNING" } else { "COMPLETE" }.to_string(),
            payload_json: None,
        });
    }

    let snapshot = SwarmSnapshot {
        payloads,
        elapsed_since_last_cycle: Duration::from_secs(1),
    };

    match trigger.should_trigger(&snapshot) {
        CompactionDecision::Skip(reason) => assert!(reason.contains("active")),
        _ => panic!("expected Skip"),
    }
}

// ============================================================================
// TEST 3: Compaction Trigger skipped on empty swarm
// ============================================================================

#[test]
fn test_trigger_skipped_empty_swarm() {
    let trigger = CompactionTrigger {
        event_count_threshold: 5,
        cycle_interval: Duration::from_secs(3600),
    };

    let snapshot = SwarmSnapshot {
        payloads: vec![],
        elapsed_since_last_cycle: Duration::from_secs(1),
    };

    match trigger.should_trigger(&snapshot) {
        CompactionDecision::Skip(reason) => assert!(reason.contains("no events")),
        _ => panic!("expected Skip"),
    }
}

// ============================================================================
// TEST 4: Compaction Trigger fires on time threshold even with low count
// ============================================================================

#[test]
fn test_trigger_fires_on_time_threshold() {
    let trigger = CompactionTrigger {
        event_count_threshold: 100, // high threshold
        cycle_interval: Duration::from_secs(60),
    };

    let payloads = vec![SwarmStatePayload {
        idempotency_key: "key-1".to_string(),
        agent_id: "agent-1".to_string(),
        phase: "PHASE_43".to_string(),
        status: "COMPLETE".to_string(),
        payload_json: None,
    }];

    let snapshot = SwarmSnapshot {
        payloads,
        elapsed_since_last_cycle: Duration::from_secs(3600), // elapsed > interval
    };

    assert_eq!(
        trigger.should_trigger(&snapshot),
        CompactionDecision::Trigger
    );
}

// ============================================================================
// TEST 5: Distillation processes only COMPLETE rows
// ============================================================================

#[test]
fn test_distillation_complete_rows_only() {
    let engine = NightCycleEngine {
        trigger: CompactionTrigger {
            event_count_threshold: 1,
            cycle_interval: Duration::from_secs(3600),
        },
        crystallizer: MockCrystallizer,
    };

    let payloads = vec![
        SwarmStatePayload {
            idempotency_key: "complete-1".to_string(),
            agent_id: "agent-1".to_string(),
            phase: "PHASE_43".to_string(),
            status: "COMPLETE".to_string(),
            payload_json: Some("data-1".to_string()),
        },
        SwarmStatePayload {
            idempotency_key: "running-1".to_string(),
            agent_id: "agent-2".to_string(),
            phase: "PHASE_43".to_string(),
            status: "RUNNING".to_string(),
            payload_json: None,
        },
        SwarmStatePayload {
            idempotency_key: "complete-2".to_string(),
            agent_id: "agent-3".to_string(),
            phase: "PHASE_43".to_string(),
            status: "COMPLETE".to_string(),
            payload_json: Some("data-2".to_string()),
        },
    ];

    let result = engine.crystallize_batch(&payloads);
    assert!(result.is_ok());

    let (memories, keys) = result.unwrap();
    assert_eq!(memories.len(), 2, "should crystallize only 2 COMPLETE rows");
    assert_eq!(keys.len(), 2);
    assert!(keys.contains(&"complete-1".to_string()));
    assert!(keys.contains(&"complete-2".to_string()));
    assert!(!keys.contains(&"running-1".to_string()));
}

// ============================================================================
// TEST 6: Distillation atomic on failure
// ============================================================================

#[test]
fn test_distillation_atomic_on_failure() {
    let engine = NightCycleEngine {
        trigger: CompactionTrigger {
            event_count_threshold: 1,
            cycle_interval: Duration::from_secs(3600),
        },
        crystallizer: MockCrystallizer,
    };

    let payloads = vec![SwarmStatePayload {
        idempotency_key: "complete-1".to_string(),
        agent_id: "agent-1".to_string(),
        phase: "PHASE_43".to_string(),
        status: "COMPLETE".to_string(),
        payload_json: Some("CRYSTALLIZER_ERROR".to_string()),
    }];

    let result = engine.crystallize_batch(&payloads);
    assert!(result.is_err(), "should fail atomically");
    match result {
        Err(CycleError::DistillationFailed(_)) => {}
        _ => panic!("expected DistillationFailed"),
    }
}

// ============================================================================
// TEST 7: Prune removes only crystallized keys, spares RUNNING
// ============================================================================

#[test]
fn test_prune_removes_only_crystallized() {
    let engine = NightCycleEngine {
        trigger: CompactionTrigger {
            event_count_threshold: 1,
            cycle_interval: Duration::from_secs(3600),
        },
        crystallizer: MockCrystallizer,
    };

    let mut store = HashMap::new();
    store.insert(
        "complete-1".to_string(),
        SwarmStatePayload {
            idempotency_key: "complete-1".to_string(),
            agent_id: "agent-1".to_string(),
            phase: "PHASE_43".to_string(),
            status: "COMPLETE".to_string(),
            payload_json: None,
        },
    );
    store.insert(
        "running-1".to_string(),
        SwarmStatePayload {
            idempotency_key: "running-1".to_string(),
            agent_id: "agent-2".to_string(),
            phase: "PHASE_43".to_string(),
            status: "RUNNING".to_string(),
            payload_json: None,
        },
    );
    store.insert(
        "complete-2".to_string(),
        SwarmStatePayload {
            idempotency_key: "complete-2".to_string(),
            agent_id: "agent-3".to_string(),
            phase: "PHASE_43".to_string(),
            status: "COMPLETE".to_string(),
            payload_json: None,
        },
    );

    let crystallized_keys = vec!["complete-1".to_string(), "complete-2".to_string()];
    let pruned = engine.prune_crystallized(&mut store, &crystallized_keys);

    assert_eq!(pruned, 2, "should prune 2 rows");
    assert!(!store.contains_key("complete-1"));
    assert!(!store.contains_key("complete-2"));
    assert!(
        store.contains_key("running-1"),
        "RUNNING row must survive prune"
    );
}
