#![cfg(feature = "axum")]

/// Phase 37: AG-UI Handler Scaffolding Tests
///
/// Verify handler signatures compile and basic state management works.

use siss_graph_db::rce_axum_handlers::RceState;
use siss_graph_db::rce::ExecutionState;
use uuid::Uuid;

#[test]
fn test_rce_state_creation() {
    let workflow_id = Uuid::new_v4();
    let state = RceState::new(workflow_id);

    // State should be cloneable (Arc-wrapped)
    let state_clone = state.clone();
    assert!(format!("{:?}", state_clone).len() > 0);
}

#[tokio::test]
async fn test_rce_state_rwlock_access() {
    let workflow_id = Uuid::new_v4();
    let state = RceState::new(workflow_id);

    // Should be able to acquire read lock
    let rce = state.rce.read().await;
    assert_eq!(rce.get_state(), ExecutionState::Idle);
    assert_eq!(rce.workflow_id, workflow_id);
}

#[tokio::test]
async fn test_rce_state_write_access() {
    let workflow_id = Uuid::new_v4();
    let state = RceState::new(workflow_id);

    // Should be able to acquire write lock and modify state
    let mut rce = state.rce.write().await;
    let plan = vec![siss_graph_db::rce::Step {
        id: Uuid::new_v4(),
        name: "test_step".to_string(),
        timeout_ms: 1000,
        idempotent: true,
    }];

    assert!(rce.start_workflow(plan).is_ok());
    assert_eq!(rce.get_state(), ExecutionState::Perform);
}
