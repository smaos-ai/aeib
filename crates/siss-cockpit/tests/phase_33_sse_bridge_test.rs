use chrono::Utc;
use siss_agent_shell::a2ui::A2UIComponent;
use siss_agent_shell::events::{AgentEvent, HookPoint, HookResultSummary};
use siss_behavioral_firewall::types::Verdict;
/// Phase 33 SSE Event Bridge Test Suite
///
/// Tests verify that AgentEvent instances convert correctly to CockpitEvent payloads
/// for real-time SSE streaming to the dashboard. Covers all 14 AgentEvent variants.
use siss_cockpit::event_bridge::agent_event_to_cockpit;
use siss_graph_core::node::execution::HardwareTarget;
use uuid::Uuid;

// ============================================================================
// ACCEPTANCE TESTS
// ============================================================================

#[test]
fn test_ui_requested_converts_with_components_and_form_id() {
    let task_id = Uuid::new_v4();
    let event = AgentEvent::UIRequested {
        task_id,
        components: vec![
            A2UIComponent::Text {
                id: "msg".to_string(),
                content: "Please approve".to_string(),
                size: None,
            },
            A2UIComponent::Button {
                id: "approve_btn".to_string(),
                label: "Approve".to_string(),
                action: Some("submit".to_string()),
            },
        ],
        form_id: Some("approval_form".to_string()),
        timestamp: Utc::now(),
    };

    let cockpit = agent_event_to_cockpit(event);

    assert_eq!(cockpit.event_type, "ui_requested");
    assert_eq!(cockpit.agent_id, Some(task_id.to_string()));
    assert_eq!(cockpit.payload["form_id"], "approval_form");
    assert!(cockpit.payload["components"].is_array());
    assert_eq!(cockpit.payload["components"].as_array().unwrap().len(), 2);
}

#[test]
fn test_ui_requested_without_form_id_has_null() {
    let task_id = Uuid::new_v4();
    let event = AgentEvent::UIRequested {
        task_id,
        components: vec![],
        form_id: None,
        timestamp: Utc::now(),
    };

    let cockpit = agent_event_to_cockpit(event);

    assert_eq!(cockpit.event_type, "ui_requested");
    assert_eq!(cockpit.payload["form_id"], serde_json::Value::Null);
}

#[test]
fn test_session_started_maps_correctly() {
    let session_id = Uuid::new_v4();
    let persona_id = Uuid::new_v4();
    let event = AgentEvent::SessionStarted {
        session_id,
        persona_id,
        timestamp: Utc::now(),
    };

    let cockpit = agent_event_to_cockpit(event);

    assert_eq!(cockpit.event_type, "session_started");
    assert_eq!(cockpit.agent_id, Some(session_id.to_string()));
    assert_eq!(cockpit.payload["session_id"], session_id.to_string());
    assert_eq!(cockpit.payload["persona_id"], persona_id.to_string());
}

#[test]
fn test_intent_completed_includes_quality_score() {
    let task_id = Uuid::new_v4();
    let event = AgentEvent::IntentCompleted {
        task_id,
        quality_score: 0.87,
        timestamp: Utc::now(),
    };

    let cockpit = agent_event_to_cockpit(event);

    assert_eq!(cockpit.event_type, "intent_completed");
    assert_eq!(cockpit.agent_id, Some(task_id.to_string()));
    assert_eq!(cockpit.payload["quality_score"], 0.87);
}

#[test]
fn test_error_event_no_agent_id() {
    let event = AgentEvent::Error {
        message: "pipeline failure: routed to unreachable hardware".to_string(),
        timestamp: Utc::now(),
    };

    let cockpit = agent_event_to_cockpit(event);

    assert_eq!(cockpit.event_type, "error");
    assert_eq!(cockpit.agent_id, None);
    assert_eq!(
        cockpit.payload["message"],
        "pipeline failure: routed to unreachable hardware"
    );
}

#[test]
fn test_all_14_agent_event_variants_convert() {
    let now = Utc::now();
    let task_id = Uuid::new_v4();
    let session_id = Uuid::new_v4();
    let mandate_id = Uuid::new_v4();

    let events = vec![
        AgentEvent::SessionStarted {
            session_id,
            persona_id: Uuid::new_v4(),
            timestamp: now,
        },
        AgentEvent::SessionClosed {
            session_id,
            timestamp: now,
        },
        AgentEvent::HookFired {
            hook_name: "gatekeeper".to_string(),
            hook_point: HookPoint::PreExecution,
            result: HookResultSummary::Continue,
            timestamp: now,
        },
        AgentEvent::TaskCreated {
            task_id,
            intent: "summarize this".to_string(),
            timestamp: now,
        },
        AgentEvent::Authorized {
            task_id,
            mandate_id,
            timestamp: now,
        },
        AgentEvent::Routed {
            task_id,
            hardware_target: HardwareTarget::LocalMlx,
            timestamp: now,
        },
        AgentEvent::OutputChunk {
            task_id,
            chunk: serde_json::json!("output"),
            index: 0,
            timestamp: now,
        },
        AgentEvent::Executing {
            task_id,
            token_cost: 150,
            duration_ms: 1000,
            timestamp: now,
        },
        AgentEvent::FirewallInspected {
            task_id,
            verdict: Verdict::Clear,
            violation_count: 0,
            timestamp: now,
        },
        AgentEvent::Scored {
            task_id,
            quality_score: 0.9,
            timestamp: now,
        },
        AgentEvent::Crystallized {
            task_id,
            memory_count: 3,
            timestamp: now,
        },
        AgentEvent::IntentCompleted {
            task_id,
            quality_score: 0.88,
            timestamp: now,
        },
        AgentEvent::Error {
            message: "test error".to_string(),
            timestamp: now,
        },
        AgentEvent::UIRequested {
            task_id,
            components: vec![],
            form_id: None,
            timestamp: now,
        },
    ];

    // Verify all 14 variants convert without panic
    for event in events {
        let event_type_name = event.event_type().to_string();
        let cockpit = agent_event_to_cockpit(event);

        // Round-trip check: cockpit event_type should match original event's event_type()
        assert_eq!(cockpit.event_type, event_type_name);
        assert!(!cockpit.payload.is_null());
    }
}
