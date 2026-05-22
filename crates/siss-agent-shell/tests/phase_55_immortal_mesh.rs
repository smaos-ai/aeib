/// Phase 55: Immortal Mesh Integration — GUI Failure → LoRA Retraining, Pixel Telemetry → SSE, Sovereign Binary
/// RED gate: 9 failing tests define expected behavior for spatial CIPO routing, SSE telemetry, and runtime wiring.

use siss_agent_shell::ag_ui::AoeSpatialStream;
use siss_agent_shell::crafter_runtime::{CrafterRuntime, RuntimeConfig};
use siss_agent_shell::pixel_provenance::PixelProvenanceRecord;
use siss_agent_shell::spatial_cipo_router::SpatialCipoRouter;
use siss_agent_shell::swarm_channel::SwarmMessage;
use chrono::Utc;
use std::sync::Arc;
use uuid::Uuid;

// Test 1: SpatialCipoRouter skips success records
#[test]
fn test_spatial_router_skips_success_records() {
    let record = PixelProvenanceRecord {
        provenance_id: Uuid::new_v4(),
        intent_mandate_id: Uuid::new_v4(),
        task_id: Uuid::new_v4(),
        agent_id: "test_agent".to_string(),
        phase: "PHASE_54".to_string(),
        action_type: "GuiClick".to_string(),
        action_x: Some(50.0),
        action_y: Some(50.0),
        ui_element_selector: Some("button#submit".to_string()),
        before_screenshot_path: Some("/tmp/before.png".to_string()),
        after_screenshot_path: Some("/tmp/after.png".to_string()),
        token_cost: 42,
        recorded_at: Utc::now(),
        failure_reason: None,
    };

    let result = SpatialCipoRouter::route_failure(&record);
    assert!(result.is_none(), "Success records (failure_reason=None) should return None");
}

// Test 2: SpatialCipoRouter routes GUI failure
#[test]
fn test_spatial_router_routes_gui_failure() {
    let record = PixelProvenanceRecord {
        provenance_id: Uuid::new_v4(),
        intent_mandate_id: Uuid::new_v4(),
        task_id: Uuid::new_v4(),
        agent_id: "test_agent".to_string(),
        phase: "PHASE_54".to_string(),
        action_type: "GuiClick".to_string(),
        action_x: Some(50.0),
        action_y: Some(50.0),
        ui_element_selector: Some("button#submit".to_string()),
        before_screenshot_path: Some("/tmp/before.png".to_string()),
        after_screenshot_path: Some("/tmp/after.png".to_string()),
        token_cost: 42,
        recorded_at: Utc::now(),
        failure_reason: Some("element_not_found".to_string()),
    };

    let result = SpatialCipoRouter::route_failure(&record);
    assert!(result.is_some(), "Failure records should route to MemoryCrystal");
    let crystal = result.unwrap();
    assert!(
        crystal.source_content.contains("element_not_found"),
        "Lesson should contain failure reason"
    );
}

// Test 3: SpatialCipoRouter distills failures to contract or None
#[test]
fn test_spatial_router_distills_failures_to_contract_or_none() {
    let router = SpatialCipoRouter::default();

    // Empty batch → None
    let empty_result = router.distill_failures(&[]);
    assert!(empty_result.is_none(), "Empty records should return None");

    // Success record → None
    let success_record = PixelProvenanceRecord {
        provenance_id: Uuid::new_v4(),
        intent_mandate_id: Uuid::new_v4(),
        task_id: Uuid::new_v4(),
        agent_id: "test".to_string(),
        phase: "PHASE_54".to_string(),
        action_type: "GuiClick".to_string(),
        action_x: Some(0.0),
        action_y: Some(0.0),
        ui_element_selector: None,
        before_screenshot_path: None,
        after_screenshot_path: None,
        token_cost: 0,
        recorded_at: Utc::now(),
        failure_reason: None,
    };

    let success_result = router.distill_failures(&[success_record]);
    assert!(
        success_result.is_none(),
        "Success records should not produce contract"
    );
}

// Test 4: PixelProvenance broadcasts SwarmMessage
#[tokio::test]
async fn test_pixel_provenance_broadcasts_swarm_message() {
    use siss_agent_shell::swarm_channel::SwarmChannel;
    use siss_agent_shell::swarm_mcp_server::SwarmMcpServer;
    use siss_agent_shell::pixel_provenance::PixelProvenanceRecorder;

    let server = Arc::new(
        SwarmMcpServer::new("sqlite::memory:")
            .await
            .expect("server creation failed"),
    );
    let channel = Arc::new(SwarmChannel::new());
    let recorder = PixelProvenanceRecorder::new_with_channel(server, channel.clone());

    let mandate_id = Uuid::new_v4();
    let record = PixelProvenanceRecord {
        provenance_id: Uuid::new_v4(),
        intent_mandate_id: mandate_id,
        task_id: Uuid::new_v4(),
        agent_id: "agent_test".to_string(),
        phase: "PHASE_55".to_string(),
        action_type: "GuiClick".to_string(),
        action_x: Some(100.0),
        action_y: Some(200.0),
        ui_element_selector: Some("button#ok".to_string()),
        before_screenshot_path: None,
        after_screenshot_path: None,
        token_cost: 50,
        recorded_at: Utc::now(),
        failure_reason: None,
    };

    let mut rx = channel.subscribe();
    let record_result = recorder.record(&record).await;
    assert!(record_result.is_ok(), "record() should succeed");

    let msg = rx.recv().await;
    assert!(msg.is_ok(), "Should receive broadcast message");
    let received_msg = msg.unwrap();
    match received_msg {
        SwarmMessage::PixelProvenance { mandate_id: m, .. } => {
            assert_eq!(m, mandate_id, "Broadcast mandate_id should match");
        }
        _ => panic!("Expected PixelProvenance message"),
    }
}

// Test 5: AoeSpatialStream translates PixelProvenance to AoEEvent
#[tokio::test]
async fn test_aoe_spatial_stream_translates_to_aoe_event() {
    use siss_agent_shell::swarm_channel::SwarmChannel;

    let channel = Arc::new(SwarmChannel::new());
    let mut stream = AoeSpatialStream::new(&channel);

    let provenance_id = Uuid::new_v4();
    let mandate_id = Uuid::new_v4();

    let msg = SwarmMessage::PixelProvenance {
        provenance_id,
        agent_id: "test_agent".to_string(),
        action_type: "GuiScroll".to_string(),
        action_x: Some(150.0),
        action_y: Some(250.0),
        token_cost: 30,
        mandate_id,
    };

    channel.broadcast(msg).expect("broadcast should succeed");

    let event = stream.next_event().await;
    assert!(event.is_some(), "Should receive AoEEvent");
    let ev = event.unwrap();
    assert_eq!(ev.action_type, "PIXEL_PROVENANCE");
    assert_eq!(ev.id, provenance_id.to_string());
    assert_eq!(ev.content, Some("GuiScroll".to_string()));
}

// Test 6: AoEEvent metadata contains all required fields
#[tokio::test]
async fn test_aoe_event_metadata_contains_all_fields() {
    use siss_agent_shell::swarm_channel::SwarmChannel;

    let channel = Arc::new(SwarmChannel::new());
    let mut stream = AoeSpatialStream::new(&channel);

    let provenance_id = Uuid::new_v4();
    let mandate_id = Uuid::new_v4();
    let action_x = 75.5;
    let action_y = 125.75;
    let token_cost = 99i64;

    let msg = SwarmMessage::PixelProvenance {
        provenance_id,
        agent_id: "test".to_string(),
        action_type: "GuiType".to_string(),
        action_x: Some(action_x),
        action_y: Some(action_y),
        token_cost,
        mandate_id,
    };

    channel.broadcast(msg).expect("broadcast should succeed");

    let event = stream.next_event().await;
    assert!(event.is_some(), "Should receive event");
    let ev = event.unwrap();
    let metadata = ev.metadata.expect("metadata should be present");

    assert_eq!(metadata["action_x"], action_x);
    assert_eq!(metadata["action_y"], action_y);
    assert_eq!(metadata["token_cost"], token_cost);
    assert_eq!(metadata["mandate_id"], mandate_id.to_string());
}

// Test 7: CrafterRuntime boots with defaults
#[tokio::test]
async fn test_crafter_runtime_boots_with_defaults() {
    let runtime = CrafterRuntime::new(RuntimeConfig::default()).await;
    assert!(
        runtime.hook_count() >= 2,
        "Runtime should have at least 2 hooks at startup"
    );
}

// Test 8: CrafterRuntime has minimum hooks
#[tokio::test]
async fn test_crafter_runtime_has_minimum_hooks() {
    let runtime = CrafterRuntime::new(RuntimeConfig::default()).await;
    let hook_count = runtime.hook_count();
    assert!(
        hook_count >= 2,
        "Runtime should have at least 2 hooks, got {}",
        hook_count
    );
}

// Test 9: CrafterRuntime channel broadcasts
#[tokio::test]
async fn test_crafter_runtime_channel_broadcasts() {
    let runtime = CrafterRuntime::new(RuntimeConfig::default()).await;
    let mut rx = runtime.channel.subscribe();

    let msg = SwarmMessage::StatusUpdate {
        agent_id: Uuid::new_v4(),
        state: "running".to_string(),
        progress_pct: 75,
    };

    let broadcast_result = runtime.channel.broadcast(msg);
    assert!(broadcast_result.is_ok(), "Broadcast should succeed");

    let received = rx.recv().await;
    assert!(received.is_ok(), "Should receive message from channel");
}
