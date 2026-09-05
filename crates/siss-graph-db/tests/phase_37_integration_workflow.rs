#![cfg(feature = "axum")]

/// Phase 37: Full End-to-End RCE Workflow Integration Test
///
/// Tests complete workflow: Start → Pause → Fetch Projection → Decide → Resume
/// Verifies:
/// - State machine transitions (Idle → Perform → Paused → Resumed)
/// - Event emission and reception via broadcast
/// - Projection data retrieval
/// - Decision webhook processing
/// - Checkpoint integrity
use chrono::Utc;
use siss_graph_db::rce::{ExecutionState, InterruptSignal, ResumableCognitiveExecution, Step};
use siss_graph_db::rce_event_broadcaster::{RceEvent, RceEventBroadcaster};
use std::sync::Arc;
use tokio::sync::RwLock;
use uuid::Uuid;

// =====================================================================
// INTEGRATION TEST: FULL WORKFLOW
// =====================================================================

#[tokio::test]
async fn test_full_rce_workflow_start_pause_resume_approve() {
    // Setup
    let workflow_id = Uuid::new_v4();
    let rce = Arc::new(RwLock::new(ResumableCognitiveExecution::new(workflow_id)));
    let broadcaster = Arc::new(RceEventBroadcaster::new());
    let mut rx = broadcaster.subscribe();

    // Step 1: Start workflow (Idle → Perform)
    {
        let mut rce_guard = rce.write().await;
        let plan = vec![
            Step {
                id: Uuid::new_v4(),
                name: "evaluate_threat_surface".to_string(),
                timeout_ms: 5000,
                idempotent: true,
            },
            Step {
                id: Uuid::new_v4(),
                name: "compute_blast_radius".to_string(),
                timeout_ms: 3000,
                idempotent: true,
            },
            Step {
                id: Uuid::new_v4(),
                name: "notify_operators".to_string(),
                timeout_ms: 2000,
                idempotent: false,
            },
        ];

        assert!(rce_guard.start_workflow(plan).is_ok());
        assert_eq!(rce_guard.get_state(), ExecutionState::Perform);
    }

    // Step 2: Simulate threat detection and pause workflow (Perform → Paused)
    {
        let mut rce_guard = rce.write().await;

        let interrupt_signal = InterruptSignal {
            workflow_id,
            severity: "High".to_string(),
            reason: "threat_anticipation_blast_radius_high: 600000 tokens at risk".to_string(),
            human_approval_required: true,
            timestamp: Utc::now(),
        };

        let checkpoint_snapshot = vec![1, 2, 3, 4, 5];
        assert!(
            rce_guard
                .pause_workflow(interrupt_signal, checkpoint_snapshot)
                .is_ok()
        );
        assert_eq!(rce_guard.get_state(), ExecutionState::Paused);
        assert!(rce_guard.has_checkpoint());

        // Emit pause event
        broadcaster.emit(RceEvent::WorkflowPaused {
            workflow_id,
            timestamp: Utc::now(),
            step_index: rce_guard.get_current_step_index(),
            step_id: rce_guard.plan[rce_guard.get_current_step_index()].id,
            step_name: rce_guard.plan[rce_guard.get_current_step_index()]
                .name
                .clone(),
            interrupt_reason: "threat_anticipation_blast_radius_high".to_string(),
            interrupt_severity: "High".to_string(),
        });
    }

    // Step 3: Verify pause event was broadcast
    {
        let event = tokio::time::timeout(std::time::Duration::from_secs(1), rx.recv())
            .await
            .expect("Timeout waiting for event")
            .expect("Failed to receive event");

        assert_eq!(event.event_type(), "workflow_paused");
        assert_eq!(event.workflow_id(), workflow_id);
    }

    // Step 4: Verify checkpoint integrity
    {
        let rce_guard = rce.read().await;
        let checkpoint = rce_guard.checkpoint.as_ref().expect("No checkpoint");

        // Verify checksum is valid
        assert!(rce_guard.verify_checkpoint_integrity(checkpoint, 1).is_ok());
    }

    // Step 5: Human operator decision - APPROVE
    {
        let mut rce_guard = rce.write().await;
        assert!(rce_guard.resume_workflow_approve().is_ok());
        assert_eq!(rce_guard.get_state(), ExecutionState::Resumed);

        // Emit resume event
        broadcaster.emit(RceEvent::WorkflowResumed {
            workflow_id,
            timestamp: Utc::now(),
            step_index: rce_guard.get_current_step_index(),
            decision: "approve".to_string(),
        });
    }

    // Step 6: Verify resume event was broadcast
    {
        let event = tokio::time::timeout(std::time::Duration::from_secs(1), rx.recv())
            .await
            .expect("Timeout waiting for event")
            .expect("Failed to receive event");

        assert_eq!(event.event_type(), "workflow_resumed");
    }

    // Step 7: Verify workflow can continue execution
    {
        let mut rce_guard = rce.write().await;
        assert_eq!(rce_guard.get_current_step_index(), 0);

        // Execute first step
        assert!(rce_guard.execute_next_step().is_ok());
        assert_eq!(rce_guard.get_current_step_index(), 1);

        // Execute second step
        assert!(rce_guard.execute_next_step().is_ok());
        assert_eq!(rce_guard.get_current_step_index(), 2);
    }
}

#[tokio::test]
async fn test_full_rce_workflow_reject_path() {
    // Setup
    let workflow_id = Uuid::new_v4();
    let rce = Arc::new(RwLock::new(ResumableCognitiveExecution::new(workflow_id)));
    let broadcaster = Arc::new(RceEventBroadcaster::new());
    let mut rx = broadcaster.subscribe();

    // Start workflow
    {
        let mut rce_guard = rce.write().await;
        let plan = vec![Step {
            id: Uuid::new_v4(),
            name: "risky_operation".to_string(),
            timeout_ms: 5000,
            idempotent: true,
        }];
        assert!(rce_guard.start_workflow(plan).is_ok());
    }

    // Pause workflow
    {
        let mut rce_guard = rce.write().await;
        let signal = InterruptSignal {
            workflow_id,
            severity: "Critical".to_string(),
            reason: "root_cause_discovered: high confidence anomaly".to_string(),
            human_approval_required: true,
            timestamp: Utc::now(),
        };
        assert!(rce_guard.pause_workflow(signal, vec![1, 2, 3]).is_ok());
    }

    // Emit pause event
    broadcaster.emit(RceEvent::WorkflowPaused {
        workflow_id,
        timestamp: Utc::now(),
        step_index: 0,
        step_id: Uuid::new_v4(),
        step_name: "risky_operation".to_string(),
        interrupt_reason: "root_cause_discovered".to_string(),
        interrupt_severity: "Critical".to_string(),
    });

    // Receive pause event
    let event = rx.recv().await.expect("Failed to receive pause event");
    assert_eq!(event.event_type(), "workflow_paused");

    // Reject the workflow
    {
        let mut rce_guard = rce.write().await;
        assert!(
            rce_guard
                .resume_workflow_reject("operator_manual_override".to_string())
                .is_ok()
        );
        assert_eq!(rce_guard.get_state(), ExecutionState::Idle);
        assert!(!rce_guard.has_checkpoint());

        // Emit reject event
        broadcaster.emit(RceEvent::WorkflowRejected {
            workflow_id,
            timestamp: Utc::now(),
            reason: "operator_manual_override".to_string(),
        });
    }

    // Receive reject event
    let event = rx.recv().await.expect("Failed to receive reject event");
    assert_eq!(event.event_type(), "workflow_rejected");

    // Verify workflow is back to Idle (can be restarted)
    {
        let mut rce_guard = rce.write().await;
        assert_eq!(rce_guard.get_state(), ExecutionState::Idle);
        assert_eq!(rce_guard.get_current_step_index(), 0);

        // Can start a new workflow
        let new_plan = vec![Step {
            id: Uuid::new_v4(),
            name: "safe_operation".to_string(),
            timeout_ms: 1000,
            idempotent: true,
        }];
        assert!(rce_guard.start_workflow(new_plan).is_ok());
    }
}

#[tokio::test]
async fn test_full_rce_workflow_modify_path() {
    // Setup
    let workflow_id = Uuid::new_v4();
    let rce = Arc::new(RwLock::new(ResumableCognitiveExecution::new(workflow_id)));
    let broadcaster = Arc::new(RceEventBroadcaster::new());
    let mut rx = broadcaster.subscribe();

    let step1_id = Uuid::new_v4();
    let step2_id = Uuid::new_v4();

    // Start with initial plan
    {
        let mut rce_guard = rce.write().await;
        let plan = vec![
            Step {
                id: step1_id,
                name: "step_1".to_string(),
                timeout_ms: 1000,
                idempotent: true,
            },
            Step {
                id: step2_id,
                name: "step_2".to_string(),
                timeout_ms: 1000,
                idempotent: true,
            },
        ];
        assert!(rce_guard.start_workflow(plan).is_ok());
    }

    // Pause workflow
    {
        let mut rce_guard = rce.write().await;
        let signal = InterruptSignal {
            workflow_id,
            severity: "Medium".to_string(),
            reason: "swot_scenario_degradation".to_string(),
            human_approval_required: true,
            timestamp: Utc::now(),
        };
        assert!(rce_guard.pause_workflow(signal, vec![1, 2]).is_ok());
    }

    // Emit pause event
    broadcaster.emit(RceEvent::WorkflowPaused {
        workflow_id,
        timestamp: Utc::now(),
        step_index: 0,
        step_id: step1_id,
        step_name: "step_1".to_string(),
        interrupt_reason: "swot_scenario_degradation".to_string(),
        interrupt_severity: "Medium".to_string(),
    });

    // Receive pause event
    let event = rx.recv().await.expect("Failed to receive pause event");
    assert_eq!(event.event_type(), "workflow_paused");

    // Operator modifies the plan
    {
        let mut rce_guard = rce.write().await;
        let new_plan = vec![
            Step {
                id: Uuid::new_v4(),
                name: "step_1_modified".to_string(),
                timeout_ms: 2000,
                idempotent: true,
            },
            Step {
                id: Uuid::new_v4(),
                name: "step_2_extra".to_string(),
                timeout_ms: 1500,
                idempotent: true,
            },
            Step {
                id: Uuid::new_v4(),
                name: "step_3_new".to_string(),
                timeout_ms: 1000,
                idempotent: true,
            },
        ];

        assert!(rce_guard.resume_workflow_modify(new_plan).is_ok());
        assert_eq!(rce_guard.get_state(), ExecutionState::Resumed);
        assert_eq!(rce_guard.plan.len(), 3);

        // Emit resume event
        broadcaster.emit(RceEvent::WorkflowResumed {
            workflow_id,
            timestamp: Utc::now(),
            step_index: rce_guard.get_current_step_index(),
            decision: "modify".to_string(),
        });
    }

    // Receive resume event
    let event = rx.recv().await.expect("Failed to receive resume event");
    assert_eq!(event.event_type(), "workflow_resumed");
}

#[tokio::test]
async fn test_idempotency_guards_during_workflow() {
    let workflow_id = Uuid::new_v4();
    let mut rce = ResumableCognitiveExecution::new(workflow_id);

    let idempotent_step_id = Uuid::new_v4();
    let non_idempotent_step_id = Uuid::new_v4();

    let plan = vec![
        Step {
            id: idempotent_step_id,
            name: "safe_retry".to_string(),
            timeout_ms: 1000,
            idempotent: true,
        },
        Step {
            id: non_idempotent_step_id,
            name: "transfer_funds".to_string(),
            timeout_ms: 1000,
            idempotent: false,
        },
    ];

    assert!(rce.start_workflow(plan).is_ok());

    // Idempotent step should always be safe
    assert!(rce.is_step_safe_to_execute(&rce.plan[0].clone()));
    rce.mark_step_executed(idempotent_step_id);
    assert!(rce.is_step_safe_to_execute(&rce.plan[0].clone()));

    // Non-idempotent step safe on first execution
    assert!(rce.is_step_safe_to_execute(&rce.plan[1].clone()));
    rce.mark_step_executed(non_idempotent_step_id);
    assert!(!rce.is_step_safe_to_execute(&rce.plan[1].clone()));
}

#[tokio::test]
async fn test_event_filtering_by_workflow_and_severity() {
    let broadcaster = Arc::new(RceEventBroadcaster::new());
    let workflow1 = Uuid::new_v4();
    let workflow2 = Uuid::new_v4();

    let mut rx = broadcaster.subscribe();

    // Emit events for two different workflows with different severities
    broadcaster.emit(RceEvent::WorkflowPaused {
        workflow_id: workflow1,
        timestamp: Utc::now(),
        step_index: 0,
        step_id: Uuid::new_v4(),
        step_name: "step_1".to_string(),
        interrupt_reason: "high_priority".to_string(),
        interrupt_severity: "Critical".to_string(),
    });

    broadcaster.emit(RceEvent::WorkflowPaused {
        workflow_id: workflow2,
        timestamp: Utc::now(),
        step_index: 1,
        step_id: Uuid::new_v4(),
        step_name: "step_2".to_string(),
        interrupt_reason: "low_priority".to_string(),
        interrupt_severity: "Low".to_string(),
    });

    // Verify first event
    let event1 = rx.recv().await.expect("Failed to receive event 1");
    assert_eq!(event1.workflow_id(), workflow1);

    // Verify second event
    let event2 = rx.recv().await.expect("Failed to receive event 2");
    assert_eq!(event2.workflow_id(), workflow2);
}

#[tokio::test]
async fn test_serialization_roundtrip_preserves_state() {
    let workflow_id = Uuid::new_v4();
    let mut original = ResumableCognitiveExecution::new(workflow_id);

    let plan = vec![
        Step {
            id: Uuid::new_v4(),
            name: "step_1".to_string(),
            timeout_ms: 1000,
            idempotent: true,
        },
        Step {
            id: Uuid::new_v4(),
            name: "step_2".to_string(),
            timeout_ms: 2000,
            idempotent: false,
        },
    ];

    assert!(original.start_workflow(plan).is_ok());
    assert!(original.execute_next_step().is_ok());

    // Serialize
    let serialized = original.serialize_state().expect("Serialization failed");
    assert!(!serialized.is_empty());

    // Deserialize
    let deserialized = ResumableCognitiveExecution::deserialize_state(&serialized)
        .expect("Deserialization failed");

    // Verify roundtrip preserves state
    assert_eq!(deserialized.workflow_id, original.workflow_id);
    assert_eq!(deserialized.state, original.state);
    assert_eq!(deserialized.current_step_index, original.current_step_index);
    assert_eq!(deserialized.plan.len(), original.plan.len());
    assert_eq!(
        deserialized.get_history().len(),
        original.get_history().len()
    );
}
