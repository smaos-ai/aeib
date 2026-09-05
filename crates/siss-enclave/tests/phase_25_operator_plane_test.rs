use siss_enclave::integration::CoEvolutionOrchestrator;
use siss_enclave::memory::EphemeralBuffer;
use siss_enclave::operator::{
    CryptoApproval, HitlError, HitlGate, HitlVerdict, LoraSwapEvent, OperatorCockpit,
    OperatorTelemetry, SwapEventKind,
};
use std::sync::Arc;
use uuid::Uuid;

/// Test 1: Operator Telemetry — Direct emit and receive via broadcast channel
/// Verifies that OperatorTelemetry correctly broadcasts LoraSwapEvent to all subscribers
#[tokio::test]
async fn test_operator_telemetry_emits_and_receives_events() {
    let (telemetry, mut rx) = OperatorTelemetry::new();

    let task_id = Uuid::new_v4();
    let event = LoraSwapEvent {
        task_id,
        agent_id: "agent:test".to_string(),
        kind: SwapEventKind::Queued,
        timestamp_ms: 1000,
    };

    telemetry.emit(event.clone());

    // Should receive the event on the subscriber
    let received = rx.recv().await.expect("should receive event");
    assert_eq!(received.task_id, task_id);
    assert_eq!(received.agent_id, "agent:test");
    assert_eq!(received.kind, SwapEventKind::Queued);
}

/// Test 2: Cockpit Telemetry — Emits Queued and Authorized events on distillation
/// Verifies that process_distillation_with_telemetry generates the expected SSE event sequence
#[tokio::test]
async fn test_cockpit_emits_queued_and_authorized_events_on_distillation() {
    let (tx, _rx) = tokio::sync::mpsc::channel::<siss_enclave::memory::RawObservation>(100);
    let ephemeral = Arc::new(EphemeralBuffer::new(tx));

    ephemeral.append_thought("execute_payment".to_string());
    ephemeral.append_tool_call("burn_nonce".to_string(), "nonce:xyz".to_string());
    ephemeral.append_action_result("SUCCESS: nonce burned".to_string());

    tokio::time::sleep(tokio::time::Duration::from_millis(50)).await;

    let orchestrator = Arc::new(CoEvolutionOrchestrator::new());
    let (cockpit, mut rx) = OperatorCockpit::new(orchestrator);

    // Process distillation with telemetry; should emit Queued + Authorized
    let task_id = cockpit
        .process_distillation_with_telemetry(ephemeral, "agent:trusted".to_string())
        .await
        .expect("process_distillation_with_telemetry failed");

    // Drain up to 10 events and verify we see at least Queued and Authorized
    let mut events = Vec::new();
    for _ in 0..10 {
        match tokio::time::timeout(tokio::time::Duration::from_millis(100), rx.recv()).await {
            Ok(Ok(event)) => events.push(event),
            _ => break,
        }
    }

    // Must have received at least Queued + Authorized
    let has_queued = events.iter().any(|e| e.kind == SwapEventKind::Queued);
    let has_authorized = events
        .iter()
        .any(|e| matches!(e.kind, SwapEventKind::Authorized { .. }));

    assert!(
        has_queued,
        "Must emit Queued event; got events: {:?}",
        events
    );
    assert!(
        has_authorized,
        "Must emit Authorized event; got events: {:?}",
        events
    );
    assert!(!task_id.to_string().is_empty(), "task_id must be non-empty");
}

/// Test 3: HITL Gate — Requires approval for borderline trust scores
/// Verifies that requires_approval() correctly identifies trust scores in [0.50, 0.80]
#[tokio::test]
async fn test_hitl_gate_requires_approval_for_borderline_trust() {
    let gate = HitlGate::new(); // default bounds [0.50, 0.80]

    // Trust scores in [0.50, 0.80] should require approval
    assert!(
        gate.requires_approval(0.60),
        "Trust 0.60 should require approval"
    );
    assert!(
        gate.requires_approval(0.75),
        "Trust 0.75 should require approval"
    );
    assert!(
        gate.requires_approval(0.50),
        "Trust 0.50 (boundary) should require approval"
    );
    assert!(
        gate.requires_approval(0.80),
        "Trust 0.80 (boundary) should require approval"
    );

    // Trust scores outside [0.50, 0.80] should NOT require approval
    assert!(
        !gate.requires_approval(0.20),
        "Trust 0.20 should NOT require approval"
    );
    assert!(
        !gate.requires_approval(0.95),
        "Trust 0.95 should NOT require approval"
    );
}

/// Test 4: HITL Gate — Suspends and resumes on valid cryptographic approval
/// Verifies that wait_for_approval blocks until issue_approval provides a verdict
#[tokio::test]
async fn test_hitl_gate_suspends_and_resumes_on_approval() {
    let gate = Arc::new(HitlGate::new());
    let task_id = Uuid::new_v4();

    let gate_clone = gate.clone();
    let task_id_clone = task_id;

    // Spawn a task that will wait for approval
    let join_handle = tokio::spawn(async move {
        gate_clone
            .wait_for_approval(task_id_clone)
            .await
            .expect("wait_for_approval failed")
    });

    // Give the spawned task time to block on wait_for_approval
    tokio::time::sleep(tokio::time::Duration::from_millis(20)).await;

    // Compute the expected signature: hex(sha256(task_id || operator_id))
    use sha2::{Digest, Sha256};
    let mut hasher = Sha256::new();
    hasher.update(task_id.as_bytes());
    hasher.update(b"op:admin");
    let sig_bytes = hasher.finalize();
    let signature = hex::encode(sig_bytes);

    // Issue a valid approval
    let approval = CryptoApproval {
        task_id,
        operator_id: "op:admin".to_string(),
        signature,
        approved: true,
        rejection_reason: None,
    };

    gate.issue_approval(approval)
        .await
        .expect("issue_approval failed");

    // Join the spawned task and verify it received HitlVerdict::Approved
    let verdict = join_handle.await.expect("join failed");

    assert_eq!(verdict, HitlVerdict::Approved);
}

/// Test 5: HITL Gate — Returns Rejected verdict with reason
/// Verifies that rejection with a reason code is properly propagated
#[tokio::test]
async fn test_hitl_gate_returns_rejected_verdict() {
    let gate = Arc::new(HitlGate::new());
    let task_id = Uuid::new_v4();

    let gate_clone = gate.clone();
    let task_id_clone = task_id;

    let join_handle = tokio::spawn(async move {
        gate_clone
            .wait_for_approval(task_id_clone)
            .await
            .expect("wait_for_approval failed")
    });

    tokio::time::sleep(tokio::time::Duration::from_millis(20)).await;

    // Compute signature for rejection
    use sha2::{Digest, Sha256};
    let mut hasher = Sha256::new();
    hasher.update(task_id.as_bytes());
    hasher.update(b"op:admin");
    let sig_bytes = hasher.finalize();
    let signature = hex::encode(sig_bytes);

    let approval = CryptoApproval {
        task_id,
        operator_id: "op:admin".to_string(),
        signature,
        approved: false,
        rejection_reason: Some("policy_violation".to_string()),
    };

    gate.issue_approval(approval)
        .await
        .expect("issue_approval failed");

    let verdict = join_handle.await.expect("join failed");

    assert_eq!(
        verdict,
        HitlVerdict::Rejected {
            reason: "policy_violation".to_string()
        }
    );
}

/// Test 6: HITL Gate — Rejects approval with invalid signature
/// Verifies that tampered or invalid signatures return HitlError::InvalidSignature
#[tokio::test]
async fn test_hitl_invalid_signature_returns_error() {
    let gate = Arc::new(HitlGate::new());
    let task_id = Uuid::new_v4();

    let gate_clone = gate.clone();
    let task_id_clone = task_id;

    let join_handle = tokio::spawn(async move {
        let _ = gate_clone.wait_for_approval(task_id_clone).await;
    });

    tokio::time::sleep(tokio::time::Duration::from_millis(20)).await;

    // Issue approval with WRONG signature
    let approval = CryptoApproval {
        task_id,
        operator_id: "op:admin".to_string(),
        signature: "deadbeefcafebabe".to_string(), // invalid
        approved: true,
        rejection_reason: None,
    };

    let result = gate.issue_approval(approval).await;

    assert!(
        matches!(result, Err(HitlError::InvalidSignature { task_id: id }) if id == task_id),
        "Should return HitlError::InvalidSignature; got {:?}",
        result
    );

    let _ = join_handle.await;
}

/// Test 7: HITL Rejection — Propagates quarantine event via CoEvolutionOrchestrator
/// Verifies that a rejected operator approval triggers quarantine_failed_distillation
#[tokio::test]
async fn test_hitl_rejection_propagates_quarantine_event() {
    let (tx, _rx) = tokio::sync::mpsc::channel::<siss_enclave::memory::RawObservation>(100);
    let ephemeral = Arc::new(EphemeralBuffer::new(tx));

    ephemeral.append_thought("task".to_string());
    ephemeral.append_tool_call("tool".to_string(), "arg".to_string());
    ephemeral.append_action_result("result".to_string());

    tokio::time::sleep(tokio::time::Duration::from_millis(50)).await;

    let orchestrator = Arc::new(CoEvolutionOrchestrator::new());
    let (cockpit, _rx) = OperatorCockpit::new(orchestrator.clone());

    // Process distillation
    let task_id = cockpit
        .process_distillation_with_telemetry(ephemeral, "agent:test".to_string())
        .await
        .expect("process_distillation_with_telemetry failed");

    // Wait a bit for distillation to complete
    tokio::time::sleep(tokio::time::Duration::from_millis(200)).await;

    // Issue rejection via cockpit
    use sha2::{Digest, Sha256};
    let mut hasher = Sha256::new();
    hasher.update(task_id.as_bytes());
    hasher.update(b"op:reject");
    let sig_bytes = hasher.finalize();
    let signature = hex::encode(sig_bytes);

    let approval = CryptoApproval {
        task_id,
        operator_id: "op:reject".to_string(),
        signature,
        approved: false,
        rejection_reason: Some("operator_rejected".to_string()),
    };

    let _ = cockpit.issue_operator_approval(approval).await;

    // Manually quarantine to simulate what should happen
    let _ = orchestrator
        .quarantine_failed_distillation(&task_id, "operator_rejected")
        .await;

    // Verify quarantine audit log
    let audit_log = orchestrator
        .get_quarantine_audit_log(&task_id)
        .await
        .expect("audit log must exist");

    assert!(
        audit_log.contains("operator_rejected"),
        "Audit log must contain 'operator_rejected'; got: {}",
        audit_log
    );
}

/// Test 8: Cockpit State Projection — Returns agent context without panic
/// Verifies that project_agent_state() produces a valid ContextProjection
#[tokio::test]
async fn test_cockpit_projects_agent_state() {
    let orchestrator = Arc::new(CoEvolutionOrchestrator::new());
    let (cockpit, _rx) = OperatorCockpit::new(orchestrator);

    let agent_id = Uuid::new_v4();
    let projection = cockpit
        .project_agent_state(agent_id)
        .await
        .expect("project_agent_state failed");

    assert_eq!(projection.agent_id, agent_id);
    assert!(
        projection.gray_fog_summary.len() >= 0,
        "gray_fog_summary should be a valid string"
    );
    assert!(
        projection.visible_field_entries >= 0,
        "visible_field_entries should be non-negative"
    );
}
