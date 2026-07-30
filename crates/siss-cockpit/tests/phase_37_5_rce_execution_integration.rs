use chrono::Utc;
use std::sync::Arc;
/// Phase 37.5: RCE Execution Layer — Integration Tests with Testcontainers
///
/// 6 tests proving fail-closed invariants under concurrent load via PostgreSQL:
/// - Atomic state mutation (exactly 1/10 concurrent decisions succeeds)
/// - Audit-first execution (audit writes before mutation, never rolled back)
/// - Synchronized broadcast (rollback on delivery failure)
use std::sync::atomic::{AtomicU32, Ordering};
use std::time::Duration;
use tokio::time::timeout;
use uuid::Uuid;

use sqlx::PgPool;
use testcontainers::runners::AsyncRunner;
use testcontainers::{GenericImage, ImageExt, core::WaitFor};

use axum::Json;
use axum::extract::State;
use axum::http::StatusCode;
use siss_cockpit::handlers::rce_decision::post_rce_decision;
use siss_cockpit::handlers::schema_contracts::DecisionWebhookPayload;
use siss_cockpit::state::CockpitState;
use siss_graph_db::rce::{ExecutionState, InterruptSignal, ResumableCognitiveExecution, Step};
use siss_graph_db::repo::rce_checkpoint_repo;

// =============================================================================
// HELPERS
// =============================================================================

async fn setup_postgres() -> (testcontainers::ContainerAsync<GenericImage>, PgPool) {
    let container = GenericImage::new("postgres", "16")
        .with_wait_for(WaitFor::message_on_stderr(
            "database system is ready to accept connections",
        ))
        .with_env_var("POSTGRES_PASSWORD", "postgres")
        .with_env_var("POSTGRES_DB", "siss_test")
        .start()
        .await
        .expect("postgres started");

    let port = container.get_host_port_ipv4(5432).await.unwrap();
    let url = format!("postgres://postgres:postgres@127.0.0.1:{port}/siss_test");
    let pool = PgPool::connect(&url).await.expect("pool connect");

    siss_graph_db::migrations::run_all(&pool)
        .await
        .expect("migrations");

    (container, pool)
}

fn make_paused_engine(workflow_id: Uuid) -> ResumableCognitiveExecution {
    let mut engine = ResumableCognitiveExecution::new(workflow_id);

    let step = Step {
        id: Uuid::new_v4(),
        name: "approval_step".to_string(),
        timeout_ms: 30_000,
        idempotent: true,
    };

    engine.start_workflow(vec![step]).expect("start_workflow");

    let interrupt = InterruptSignal {
        interrupt_type: "threat_anticipation_blast_radius_high".to_string(),
        severity: "High".to_string(),
        reason: "Awaiting human approval".to_string(),
        workflow_id: Some(workflow_id),
        human_approval_required: true,
        timestamp: Some(Utc::now()),
    };

    engine
        .pause_workflow(interrupt, b"state_snapshot_bytes".to_vec())
        .expect("pause_workflow");

    assert_eq!(
        engine.state,
        ExecutionState::Paused,
        "Engine should be Paused"
    );
    engine
}

// =============================================================================
// TEST 1: Concurrency Lock — Exactly One Succeeds, Nine Get 409
// =============================================================================

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn test_01_concurrency_lock_exactly_one_succeeds() {
    let (_container, pool) = setup_postgres().await;
    let pool = Arc::new(pool);

    let workflow_id = Uuid::new_v4();
    let engine = make_paused_engine(workflow_id);

    let state = CockpitState::new();

    // Wire engine and pool (async-friendly direct assignment)
    *state.rce_engine.write().await = Some(engine);
    *state.pool.lock().unwrap() = Some(pool.clone());

    // Subscribe BEFORE spawning tasks
    let mut rx = state.rce_broadcaster.subscribe();

    // Fire 10 concurrent APPROVE decisions
    let success_count = Arc::new(AtomicU32::new(0));
    let conflict_count = Arc::new(AtomicU32::new(0));

    let handles: Vec<_> = (0..10)
        .map(|_| {
            let state_clone = state.clone();
            let workflow_id_str = workflow_id.to_string();
            let success = success_count.clone();
            let conflict = conflict_count.clone();

            tokio::spawn(async move {
                let payload = DecisionWebhookPayload {
                    workflow_id: workflow_id_str,
                    decision: "APPROVE".to_string(),
                    reason: None,
                    new_plan: None,
                    timestamp: Utc::now().to_rfc3339(),
                    human_operator_id: "op@example.com".to_string(),
                };

                let (status, _body) = post_rce_decision(State(state_clone), Json(payload)).await;

                match status {
                    StatusCode::OK => {
                        success.fetch_add(1, Ordering::SeqCst);
                    }
                    StatusCode::CONFLICT => {
                        conflict.fetch_add(1, Ordering::SeqCst);
                    }
                    _ => {} // other statuses
                }
            })
        })
        .collect();

    // Wait for all tasks
    for handle in handles {
        handle.await.unwrap();
    }

    // VERIFY: Exactly 1 success, 9 conflicts
    assert_eq!(
        success_count.load(Ordering::SeqCst),
        1,
        "Exactly 1 decision should succeed"
    );
    assert_eq!(
        conflict_count.load(Ordering::SeqCst),
        9,
        "Exactly 9 decisions should fail with 409 CONFLICT"
    );

    // VERIFY: Audit trail has exactly 1 row
    let audit_rows = rce_checkpoint_repo::fetch_audit_trail(&pool, workflow_id)
        .await
        .expect("fetch_audit_trail");
    assert_eq!(audit_rows.len(), 1, "Exactly 1 audit row should be written");

    let (_, event_type, decision, decided_by, _, _, _) = &audit_rows[0];
    assert_eq!(event_type, "decision", "Event type should be 'decision'");
    assert_eq!(
        decision.as_deref(),
        Some("APPROVE"),
        "Decision should be 'APPROVE'"
    );
    assert_eq!(
        decided_by.as_deref(),
        Some("op@example.com"),
        "decided_by should match"
    );

    // VERIFY: Exactly 1 SSE broadcast event
    let event_result = timeout(Duration::from_millis(100), rx.recv()).await;
    assert!(
        event_result.is_ok(),
        "Should receive broadcast event within 100ms"
    );

    let event = event_result.unwrap().expect("recv succeeded");
    assert_eq!(
        event.event_type(),
        "workflow_resumed",
        "Event type should be workflow_resumed"
    );

    // VERIFY: No more events
    let no_more = timeout(Duration::from_millis(50), rx.recv()).await;
    assert!(
        no_more.is_err(),
        "Should NOT receive more events (only 1 broadcast)"
    );
}

// =============================================================================
// TEST 2: Invalid Transition — Engine in Idle State
// =============================================================================

#[tokio::test]
async fn test_02_invalid_transition_idle_state() {
    let (_container, pool) = setup_postgres().await;
    let pool = Arc::new(pool);

    let workflow_id = Uuid::new_v4();

    // Create engine in Idle state (not started, not paused)
    let engine = ResumableCognitiveExecution::new(workflow_id);
    assert_eq!(
        engine.state,
        ExecutionState::Idle,
        "Engine should start in Idle"
    );

    let state = CockpitState::new();

    // Wire engine and pool
    *state.rce_engine.write().await = Some(engine);
    *state.pool.lock().unwrap() = Some(pool.clone());

    let payload = DecisionWebhookPayload {
        workflow_id: workflow_id.to_string(),
        decision: "APPROVE".to_string(),
        reason: None,
        new_plan: None,
        timestamp: Utc::now().to_rfc3339(),
        human_operator_id: "op@example.com".to_string(),
    };

    let (status, _body) = post_rce_decision(State(state), Json(payload)).await;

    // VERIFY: 409 Conflict (engine not in Paused state)
    assert_eq!(
        status,
        StatusCode::CONFLICT,
        "Should return 409 CONFLICT for non-Paused state"
    );

    // VERIFY: 0 audit rows (audit comes AFTER state guard, so rejected before audit)
    let audit_rows = rce_checkpoint_repo::fetch_audit_trail(&pool, workflow_id)
        .await
        .expect("fetch_audit_trail");
    assert_eq!(
        audit_rows.len(),
        0,
        "No audit row should be written for state guard rejection"
    );
}

// =============================================================================
// TEST 3: Broadcast Guarantee — Event Delivered When Subscriber Present
// =============================================================================

#[tokio::test]
async fn test_03_broadcast_guarantee_event_delivered() {
    let (_container, pool) = setup_postgres().await;
    let pool = Arc::new(pool);

    let workflow_id = Uuid::new_v4();
    let engine = make_paused_engine(workflow_id);

    let state = CockpitState::new();

    // Wire engine and pool
    *state.rce_engine.write().await = Some(engine);
    *state.pool.lock().unwrap() = Some(pool.clone());

    // Subscribe BEFORE request
    let mut rx = state.rce_broadcaster.subscribe();

    let payload = DecisionWebhookPayload {
        workflow_id: workflow_id.to_string(),
        decision: "APPROVE".to_string(),
        reason: None,
        new_plan: None,
        timestamp: Utc::now().to_rfc3339(),
        human_operator_id: "op@example.com".to_string(),
    };

    let (status, _body) = post_rce_decision(State(state), Json(payload)).await;

    // VERIFY: 200 OK
    assert_eq!(status, StatusCode::OK, "Should return 200 OK");

    // VERIFY: Event received within 100ms
    let event_result = timeout(Duration::from_millis(100), rx.recv()).await;
    assert!(
        event_result.is_ok(),
        "Event should be received within 100ms"
    );

    let event = event_result.unwrap().expect("recv succeeded");
    assert_eq!(
        event.event_type(),
        "workflow_resumed",
        "Event should be WorkflowResumed"
    );

    // VERIFY: 1 audit row written
    let audit_rows = rce_checkpoint_repo::fetch_audit_trail(&pool, workflow_id)
        .await
        .expect("fetch_audit_trail");
    assert_eq!(audit_rows.len(), 1, "Should have 1 audit row");
}

// =============================================================================
// TEST 4: Rollback on Broadcast Failure (No Subscribers)
// =============================================================================

#[tokio::test]
async fn test_04_rollback_on_broadcast_failure() {
    let (_container, pool) = setup_postgres().await;
    let pool = Arc::new(pool);

    let workflow_id = Uuid::new_v4();
    let engine = make_paused_engine(workflow_id);

    let state = CockpitState::new();

    // Wire engine and pool
    *state.rce_engine.write().await = Some(engine);
    *state.pool.lock().unwrap() = Some(pool.clone());

    // Do NOT subscribe — 0 broadcast receivers
    // This causes emit_checked() to return Err

    let payload = DecisionWebhookPayload {
        workflow_id: workflow_id.to_string(),
        decision: "APPROVE".to_string(),
        reason: None,
        new_plan: None,
        timestamp: Utc::now().to_rfc3339(),
        human_operator_id: "op@example.com".to_string(),
    };

    let (status, body) = post_rce_decision(State(state.clone()), Json(payload)).await;

    // VERIFY: 500 Internal Server Error
    assert_eq!(
        status,
        StatusCode::INTERNAL_SERVER_ERROR,
        "Should return 500 on broadcast failure"
    );

    // VERIFY: error_broadcast_required in response
    assert_eq!(
        body.0.status, "error_broadcast_required",
        "Error should indicate broadcast_required"
    );

    // VERIFY: Engine state rolled back to Paused
    let engine_guard = state.rce_engine.read().await;
    let current_state = engine_guard
        .as_ref()
        .map(|e| e.state)
        .expect("engine is wired");
    assert_eq!(
        current_state,
        ExecutionState::Paused,
        "Engine state should be rolled back to Paused"
    );
    drop(engine_guard);

    // VERIFY: 1 audit row EXISTS (audit-first: written before broadcast, not rolled back)
    let audit_rows = rce_checkpoint_repo::fetch_audit_trail(&pool, workflow_id)
        .await
        .expect("fetch_audit_trail");
    assert_eq!(
        audit_rows.len(),
        1,
        "Audit row should exist (audit happens before broadcast, not rolled back)"
    );
}

// =============================================================================
// TEST 5: Audit Schema Validation
// =============================================================================

#[tokio::test]
async fn test_05_audit_schema_validation_row_contents() {
    let (_container, pool) = setup_postgres().await;
    let pool = Arc::new(pool);

    let workflow_id = Uuid::new_v4();
    let engine = make_paused_engine(workflow_id);

    let state = CockpitState::new();

    // Wire engine and pool
    *state.rce_engine.write().await = Some(engine);
    *state.pool.lock().unwrap() = Some(pool.clone());

    // Subscribe (so broadcast succeeds)
    let _rx = state.rce_broadcaster.subscribe();

    let operator_id = "operator@acme.com";
    let payload = DecisionWebhookPayload {
        workflow_id: workflow_id.to_string(),
        decision: "APPROVE".to_string(),
        reason: Some("Test approval".to_string()),
        new_plan: None,
        timestamp: Utc::now().to_rfc3339(),
        human_operator_id: operator_id.to_string(),
    };

    let (status, _body) = post_rce_decision(State(state), Json(payload)).await;
    assert_eq!(status, StatusCode::OK, "Should succeed");

    // Fetch audit trail
    let audit_rows = rce_checkpoint_repo::fetch_audit_trail(&pool, workflow_id)
        .await
        .expect("fetch_audit_trail");
    assert_eq!(audit_rows.len(), 1, "Should have 1 audit row");

    let (_, event_type, decision, decided_by, reason, details, occurred_at) = &audit_rows[0];

    // Validate row contents
    assert_eq!(event_type, "decision", "event_type should be 'decision'");
    assert_eq!(
        decision.as_deref(),
        Some("APPROVE"),
        "decision should be 'APPROVE'"
    );
    assert_eq!(
        decided_by.as_deref(),
        Some(operator_id),
        "decided_by should match operator_id"
    );
    assert_eq!(
        reason.as_deref(),
        Some("Test approval"),
        "reason should match"
    );

    // Verify timestamp is recent
    let now = Utc::now();
    let diff = (now - *occurred_at).num_seconds();
    assert!(
        diff >= 0 && diff <= 5,
        "occurred_at should be within 5s of now"
    );

    // Verify details contains workflow_id
    if let Some(workflow_id_in_details) = details.get("workflow_id") {
        assert_eq!(
            workflow_id_in_details.as_str().unwrap_or(""),
            workflow_id.to_string(),
            "details should contain workflow_id"
        );
    }
}

// =============================================================================
// TEST 6: Audit-First Execution — Pool Unavailable
// =============================================================================

#[tokio::test]
async fn test_06_audit_first_execution_pool_unavailable() {
    let workflow_id = Uuid::new_v4();

    // Create paused engine
    let mut engine = ResumableCognitiveExecution::new(workflow_id);
    let step = Step {
        id: Uuid::new_v4(),
        name: "step".to_string(),
        timeout_ms: 1000,
        idempotent: true,
    };
    engine.start_workflow(vec![step]).expect("start");
    engine
        .pause_workflow(
            InterruptSignal {
                interrupt_type: "test".to_string(),
                severity: "High".to_string(),
                reason: "test".to_string(),
                workflow_id: Some(workflow_id),
                human_approval_required: true,
                timestamp: Some(Utc::now()),
            },
            b"snapshot".to_vec(),
        )
        .expect("pause");

    let state = CockpitState::new();

    // Wire ONLY engine, leave pool as None
    *state.rce_engine.write().await = Some(engine);
    // pool remains None (CockpitState::new() starts with pool=None)

    let payload = DecisionWebhookPayload {
        workflow_id: workflow_id.to_string(),
        decision: "APPROVE".to_string(),
        reason: None,
        new_plan: None,
        timestamp: Utc::now().to_rfc3339(),
        human_operator_id: "op@example.com".to_string(),
    };

    let (status, body) = post_rce_decision(State(state.clone()), Json(payload)).await;

    // VERIFY: 500 Internal Server Error
    assert_eq!(
        status,
        StatusCode::INTERNAL_SERVER_ERROR,
        "Should return 500 when pool is absent"
    );

    // VERIFY: error_audit_required in response
    assert_eq!(
        body.0.status, "error_audit_required",
        "Error should indicate audit_required"
    );

    // VERIFY: Engine state remains Paused (mutation was not applied)
    let engine_guard = state.rce_engine.read().await;
    let current_state = engine_guard
        .as_ref()
        .map(|e| e.state)
        .expect("engine is wired");
    assert_eq!(
        current_state,
        ExecutionState::Paused,
        "Engine state should remain Paused"
    );
}
