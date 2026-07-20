use chrono::Utc;
use serde_json::json;
/// Phase 54: Spatial & Computer-Use Plane — Eyes and hands with δ+ security gates
/// RED gate: 9 failing tests define expected behavior for GUI sandbox, visual action membrane, and pixel provenance.
/// Invariants: (1) Non-Clone exclusive container token enforces δ+ jail isolation
///             (2) Visual action membrane validates click zones before execution
///             (3) Pixel provenance audit trail tied to AP2 mandate (fail-closed on nil)
use siss_agent_shell::gui_sandbox::{GuiSandboxAllocator, GuiSandboxError, MockContainerDriver};
use siss_agent_shell::hooks::{HookResult, LifecycleHook, ToolUseContext};
use siss_agent_shell::pixel_provenance::{
    PixelProvenanceRecord, PixelProvenanceRecorder, ProvenanceError,
};
use siss_agent_shell::swarm_mcp_server::SwarmMcpServer;
use siss_agent_shell::visual_action_membrane::{
    BoundingBox, MockZoneAnalyzer, RestrictedZone, VisualActionMembrane, ZonePolicy,
};
use siss_graph_core::node::NodeId;
use std::sync::Arc;
use uuid::Uuid;

// Test 1: GUI Sandbox allocates exclusive token
#[test]
fn test_gui_sandbox_allocates_exclusive_token() {
    let allocator = GuiSandboxAllocator::new();
    let driver = MockContainerDriver;
    let agent_id = Uuid::new_v4();

    let result = allocator.allocate(agent_id, 5900, ":99", &driver);

    assert!(result.is_ok());
    let token = result.unwrap();
    assert_eq!(token.vnc_port, 5900);
    assert_eq!(token.display, ":99");
    assert_eq!(token.agent_id, agent_id);
}

// Test 2: GUI Sandbox second alloc denied
#[test]
fn test_gui_sandbox_second_alloc_denied() {
    let allocator = GuiSandboxAllocator::new();
    let driver = MockContainerDriver;
    let agent1 = Uuid::new_v4();
    let agent2 = Uuid::new_v4();

    let first = allocator.allocate(agent1, 5900, ":99", &driver);
    assert!(first.is_ok());

    let second = allocator.allocate(agent2, 5900, ":99", &driver);
    assert!(matches!(
        second,
        Err(GuiSandboxError::PortAlreadyAllocated { port: 5900, held_by })
        if held_by == agent1
    ));
}

// Test 3: GUI Sandbox release allows realloc
#[test]
fn test_gui_sandbox_release_allows_realloc() {
    let allocator = GuiSandboxAllocator::new();
    let driver = MockContainerDriver;
    let agent1 = Uuid::new_v4();
    let agent2 = Uuid::new_v4();

    let first = allocator.allocate(agent1, 5900, ":99", &driver);
    assert!(first.is_ok());
    let token = first.unwrap();

    allocator.release(token, &driver).expect("release failed");

    let second = allocator.allocate(agent2, 5900, ":99", &driver);
    assert!(second.is_ok());
}

// Test 4: Membrane passes non-GUI tool
#[test]
fn test_membrane_passes_non_gui_tool() {
    let zones = vec![RestrictedZone {
        name: "delete_button".to_string(),
        bounds: BoundingBox {
            x_min: 400.0,
            y_min: 400.0,
            x_max: 600.0,
            y_max: 600.0,
        },
        policy: ZonePolicy::Deny,
    }];
    let analyzer = MockZoneAnalyzer { zones };
    let membrane = VisualActionMembrane { analyzer };

    let ctx = ToolUseContext {
        task_id: NodeId::new(),
        tool_id: Uuid::new_v4(),
        tool_name: "Edit".to_string(),
        tool_input: json!({}),
        tool_output: None,
    };

    let result = membrane.on_pre_tool_use(&ctx);
    assert_eq!(result, HookResult::Continue);
}

// Test 5: Membrane allows click in safe zone
#[test]
fn test_membrane_allows_click_in_safe_zone() {
    let zones = vec![RestrictedZone {
        name: "delete_button".to_string(),
        bounds: BoundingBox {
            x_min: 400.0,
            y_min: 400.0,
            x_max: 600.0,
            y_max: 600.0,
        },
        policy: ZonePolicy::Deny,
    }];
    let analyzer = MockZoneAnalyzer { zones };
    let membrane = VisualActionMembrane { analyzer };

    let ctx = ToolUseContext {
        task_id: NodeId::new(),
        tool_id: Uuid::new_v4(),
        tool_name: "GuiClick".to_string(),
        tool_input: json!({"x": 50.0, "y": 50.0}),
        tool_output: None,
    };

    let result = membrane.on_pre_tool_use(&ctx);
    assert_eq!(result, HookResult::Continue);
}

// Test 6: Membrane denies click in restricted zone
#[test]
fn test_membrane_denies_click_in_restricted_zone() {
    let zones = vec![RestrictedZone {
        name: "delete_button".to_string(),
        bounds: BoundingBox {
            x_min: 400.0,
            y_min: 400.0,
            x_max: 600.0,
            y_max: 600.0,
        },
        policy: ZonePolicy::Deny,
    }];
    let analyzer = MockZoneAnalyzer { zones };
    let membrane = VisualActionMembrane { analyzer };

    let ctx = ToolUseContext {
        task_id: NodeId::new(),
        tool_id: Uuid::new_v4(),
        tool_name: "GuiClick".to_string(),
        tool_input: json!({"x": 500.0, "y": 500.0}),
        tool_output: None,
    };

    let result = membrane.on_pre_tool_use(&ctx);
    assert!(
        matches!(result, HookResult::Deny { ref reason } if reason.contains("restricted_zone")),
        "Expected Deny with 'restricted_zone' in reason, got {:?}",
        result
    );
}

// Test 7: Membrane defers click in approval zone
#[test]
fn test_membrane_defers_click_in_approval_zone() {
    let zones = vec![RestrictedZone {
        name: "approval_required".to_string(),
        bounds: BoundingBox {
            x_min: 700.0,
            y_min: 700.0,
            x_max: 900.0,
            y_max: 900.0,
        },
        policy: ZonePolicy::Defer,
    }];
    let analyzer = MockZoneAnalyzer { zones };
    let membrane = VisualActionMembrane { analyzer };

    let ctx = ToolUseContext {
        task_id: NodeId::new(),
        tool_id: Uuid::new_v4(),
        tool_name: "GuiClick".to_string(),
        tool_input: json!({"x": 800.0, "y": 800.0}),
        tool_output: None,
    };

    let result = membrane.on_pre_tool_use(&ctx);
    assert!(
        matches!(result, HookResult::Defer { ref severity, .. } if severity == "HIGH"),
        "Expected Defer with HIGH severity, got {:?}",
        result
    );
}

// Test 8: Provenance records with valid mandate (async)
#[tokio::test]
async fn test_provenance_records_with_valid_mandate() {
    let server = Arc::new(
        SwarmMcpServer::new("sqlite::memory:")
            .await
            .expect("failed to create server"),
    );
    let recorder = PixelProvenanceRecorder::new(server.clone());

    let mandate_id = Uuid::new_v4();
    let record = PixelProvenanceRecord {
        provenance_id: Uuid::new_v4(),
        intent_mandate_id: mandate_id,
        task_id: Uuid::new_v4(),
        agent_id: "agent_alpha".to_string(),
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

    let result = recorder.record(&record).await;
    assert!(result.is_ok());

    let queried = recorder.query_by_mandate(mandate_id).await;
    assert!(queried.is_ok());
    let records = queried.unwrap();
    assert_eq!(records.len(), 1);
    assert_eq!(records[0].intent_mandate_id, mandate_id);
}

// Test 9: Provenance rejects nil mandate (async)
#[tokio::test]
async fn test_provenance_rejects_nil_mandate() {
    let server = Arc::new(
        SwarmMcpServer::new("sqlite::memory:")
            .await
            .expect("failed to create server"),
    );
    let recorder = PixelProvenanceRecorder::new(server);

    let record = PixelProvenanceRecord {
        provenance_id: Uuid::new_v4(),
        intent_mandate_id: Uuid::nil(), // fail-closed gate
        task_id: Uuid::new_v4(),
        agent_id: "agent_alpha".to_string(),
        phase: "PHASE_54".to_string(),
        action_type: "GuiClick".to_string(),
        action_x: Some(50.0),
        action_y: Some(50.0),
        ui_element_selector: None,
        before_screenshot_path: None,
        after_screenshot_path: None,
        token_cost: 0,
        recorded_at: Utc::now(),
        failure_reason: None,
    };

    let result = recorder.record(&record).await;
    assert_eq!(result, Err(ProvenanceError::MissingMandate));
}
