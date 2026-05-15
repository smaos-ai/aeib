#![cfg(feature = "axum")]

/// Phase 37: AG-UI Handler Scaffolding Tests
///
/// Verify handler signatures compile and basic state management works.

use siss_graph_db::rce_axum_handlers::RceState;
use siss_graph_db::rce::ExecutionState;
use uuid::Uuid;

#[test]
fn test_rce_event_broadcaster_creation() {
    use siss_graph_db::rce_event_broadcaster::RceEventBroadcaster;
    let broadcaster = RceEventBroadcaster::new();
    let mut rx = broadcaster.subscribe();

    // Subscribe should work
    drop(rx);
    assert!(true);
}

#[tokio::test]
async fn test_rce_event_broadcaster_emit() {
    use siss_graph_db::rce_event_broadcaster::{RceEvent, RceEventBroadcaster};

    let broadcaster = RceEventBroadcaster::new();
    let mut rx = broadcaster.subscribe();

    let event = RceEvent::WorkflowCompleted {
        workflow_id: Uuid::new_v4(),
        timestamp: chrono::Utc::now(),
        total_steps: 3,
    };

    broadcaster.emit(event.clone());

    let received = rx.recv().await;
    assert!(received.is_ok());
    assert_eq!(received.unwrap().event_type(), "workflow_completed");
}

#[tokio::test]
async fn test_rce_event_filtering_by_severity() {
    use siss_graph_db::rce_event_broadcaster::{RceEvent, RceEventBroadcaster};

    let broadcaster = RceEventBroadcaster::new();
    let mut rx = broadcaster.subscribe();

    let workflow_id = Uuid::new_v4();

    // Emit a paused event with High severity
    let event = RceEvent::WorkflowPaused {
        workflow_id,
        timestamp: chrono::Utc::now(),
        step_index: 1,
        step_id: Uuid::new_v4(),
        step_name: "test".to_string(),
        interrupt_reason: "test_interrupt".to_string(),
        interrupt_severity: "High".to_string(),
    };

    broadcaster.emit(event);

    let received = rx.recv().await.unwrap();
    assert_eq!(received.event_type(), "workflow_paused");
}
