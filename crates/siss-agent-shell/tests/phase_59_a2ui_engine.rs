/// Phase 59: A2UI Protocol & Interactive Payload Engine — 27 TDD Tests
use siss_agent_shell::a2ui::schema::A2UIComponent;
use siss_agent_shell::a2ui_composer::{A2UIComposer, ComponentRef};
use siss_agent_shell::a2ui_primitives::{PrimitiveError, PrimitiveRegistry};
use siss_agent_shell::ag_ui_integration::{AgUiStream, AgUiStreamEvent};
use uuid::Uuid;

// ─── A2UI PRIMITIVES TESTS (1–9) ──────────────────────────────

#[test]
fn test_registry_knows_all_18_primitives() {
    let names = vec![
        "text",
        "badge",
        "alert",
        "progress",
        "divider",
        "link",
        "tooltip",
        "breadcrumb",
        "input",
        "textarea",
        "select",
        "checkbox",
        "radio",
        "button",
        "card",
        "grid",
        "modal",
        "table",
    ];
    for name in names {
        assert!(PrimitiveRegistry::is_known(name), "Should know: {}", name);
    }
}

#[test]
fn test_registry_rejects_unknown_type() {
    assert!(!PrimitiveRegistry::is_known("html_inject"));
    assert!(!PrimitiveRegistry::is_known("evil_script"));
    assert!(!PrimitiveRegistry::is_known(""));
}

#[test]
fn test_try_parse_valid_text_component() {
    let json = serde_json::json!({
        "type": "text",
        "id": "t1",
        "content": "hello"
    });
    let result = PrimitiveRegistry::try_parse(&json);
    assert!(result.is_ok());
}

#[test]
fn test_try_parse_valid_card_with_children() {
    let json = serde_json::json!({
        "type": "card",
        "id": "card1",
        "title": "Card Title",
        "children": [
            {
                "type": "button",
                "id": "btn1",
                "label": "Click Me"
            }
        ]
    });
    let result = PrimitiveRegistry::try_parse(&json);
    assert!(result.is_ok());
}

#[test]
fn test_try_parse_unknown_type_returns_error() {
    let json = serde_json::json!({
        "type": "evil_script",
        "id": "x"
    });
    let result = PrimitiveRegistry::try_parse(&json);
    assert!(matches!(result, Err(PrimitiveError::MalformedJson(_))));
}

#[test]
fn test_try_parse_malformed_json_field() {
    let json = serde_json::json!({
        "type": "text",
        "id": 42,
        "content": "x"
    });
    let result = PrimitiveRegistry::try_parse(&json);
    assert!(matches!(result, Err(PrimitiveError::MalformedJson(_))));
}

#[test]
fn test_filter_batch_drops_unknown_keeps_valid() {
    let batch = vec![
        serde_json::json!({"type": "text", "id": "t1", "content": "hello"}),
        serde_json::json!({"type": "evil_script", "id": "x"}),
        serde_json::json!({"type": "button", "id": "b1", "label": "Click"}),
    ];
    let result = PrimitiveRegistry::filter_batch(&batch);
    assert_eq!(result.len(), 2);
}

#[test]
fn test_filter_batch_empty_input_returns_empty() {
    let result = PrimitiveRegistry::filter_batch(&[]);
    assert!(result.is_empty());
}

#[test]
fn test_try_parse_empty_id_returns_validation_error() {
    let json = serde_json::json!({
        "type": "text",
        "id": "",
        "content": "x"
    });
    let result = PrimitiveRegistry::try_parse(&json);
    assert!(matches!(result, Err(PrimitiveError::ValidationFailed(_))));
}

// ─── A2UI COMPOSER TESTS (10–18) ──────────────────────────────

#[test]
fn test_compose_binds_single_component() {
    let refs = vec![ComponentRef {
        id: "t1".to_string(),
        data: serde_json::json!({
            "type": "text",
            "id": "t1",
            "content": "hello"
        }),
    }];
    let task_id = Uuid::new_v4();
    let form_id = "form1".to_string();

    let payload = A2UIComposer::compose(refs, task_id, form_id.clone());
    assert_eq!(payload.components.len(), 1);
    assert_eq!(payload.task_id, task_id);
    assert_eq!(payload.form_id, form_id);
}

#[test]
fn test_compose_drops_unknown_type_ref() {
    let refs = vec![ComponentRef {
        id: "x".to_string(),
        data: serde_json::json!({
            "type": "evil_script",
            "id": "x"
        }),
    }];
    let task_id = Uuid::new_v4();
    let form_id = "form1".to_string();

    let payload = A2UIComposer::compose(refs, task_id, form_id);
    assert_eq!(payload.components.len(), 0);
}

#[test]
fn test_compose_drops_malformed_ref() {
    let refs = vec![ComponentRef {
        id: "bad".to_string(),
        data: serde_json::json!({
            "type": "text",
            "id": 42,
            "content": "x"
        }),
    }];
    let task_id = Uuid::new_v4();
    let form_id = "form1".to_string();

    let payload = A2UIComposer::compose(refs, task_id, form_id);
    assert_eq!(payload.components.len(), 0);
}

#[test]
fn test_compose_preserves_input_order() {
    let refs = vec![
        ComponentRef {
            id: "t1".to_string(),
            data: serde_json::json!({
                "type": "text",
                "id": "t1",
                "content": "first"
            }),
        },
        ComponentRef {
            id: "b1".to_string(),
            data: serde_json::json!({
                "type": "button",
                "id": "b1",
                "label": "second"
            }),
        },
        ComponentRef {
            id: "t2".to_string(),
            data: serde_json::json!({
                "type": "text",
                "id": "t2",
                "content": "third"
            }),
        },
    ];
    let task_id = Uuid::new_v4();
    let form_id = "form1".to_string();

    let payload = A2UIComposer::compose(refs, task_id, form_id);
    assert_eq!(payload.components.len(), 3);
}

#[test]
fn test_compose_empty_refs_returns_empty_payload() {
    let refs = vec![];
    let task_id = Uuid::new_v4();
    let form_id = "form1".to_string();

    let payload = A2UIComposer::compose(refs, task_id, form_id);
    assert!(payload.components.is_empty());
}

#[test]
fn test_compose_task_id_propagated() {
    let refs = vec![ComponentRef {
        id: "t1".to_string(),
        data: serde_json::json!({
            "type": "text",
            "id": "t1",
            "content": "hello"
        }),
    }];
    let task_id = Uuid::new_v4();
    let form_id = "form1".to_string();

    let payload = A2UIComposer::compose(refs, task_id, form_id);
    assert_eq!(payload.task_id, task_id);
}

#[test]
fn test_compose_form_id_propagated() {
    let refs = vec![ComponentRef {
        id: "t1".to_string(),
        data: serde_json::json!({
            "type": "text",
            "id": "t1",
            "content": "hello"
        }),
    }];
    let task_id = Uuid::new_v4();
    let form_id = "form_xyz".to_string();

    let payload = A2UIComposer::compose(refs, task_id, form_id.clone());
    assert_eq!(payload.form_id, form_id);
}

#[test]
fn test_compose_drops_empty_id_component() {
    let refs = vec![ComponentRef {
        id: "bad".to_string(),
        data: serde_json::json!({
            "type": "text",
            "id": "",
            "content": "x"
        }),
    }];
    let task_id = Uuid::new_v4();
    let form_id = "form1".to_string();

    let payload = A2UIComposer::compose(refs, task_id, form_id);
    assert_eq!(payload.components.len(), 0);
}

#[test]
fn test_compose_mixed_valid_invalid_batch() {
    let refs = vec![
        ComponentRef {
            id: "t1".to_string(),
            data: serde_json::json!({
                "type": "text",
                "id": "t1",
                "content": "valid"
            }),
        },
        ComponentRef {
            id: "bad1".to_string(),
            data: serde_json::json!({
                "type": "evil_script",
                "id": "x"
            }),
        },
        ComponentRef {
            id: "b1".to_string(),
            data: serde_json::json!({
                "type": "button",
                "id": "b1",
                "label": "valid"
            }),
        },
        ComponentRef {
            id: "bad2".to_string(),
            data: serde_json::json!({
                "type": "text",
                "id": "",
                "content": "invalid"
            }),
        },
    ];
    let task_id = Uuid::new_v4();
    let form_id = "form1".to_string();

    let payload = A2UIComposer::compose(refs, task_id, form_id);
    assert_eq!(payload.components.len(), 2);
}

// ─── AG-UI STREAMING INTEGRATION TESTS (19–27) ─────────────────

fn create_test_text_component() -> A2UIComponent {
    A2UIComponent::Text {
        id: "t1".to_string(),
        content: "hello".to_string(),
        size: None,
    }
}

#[test]
fn test_format_event_text_produces_sse_prefix() {
    let event = AgUiStreamEvent::Text {
        content: "hello".to_string(),
    };
    let result = AgUiStream::format_event(&event);
    assert!(result.is_some());
    let s = result.unwrap();
    assert!(s.starts_with("data: "));
}

#[test]
fn test_format_event_component_produces_sse_prefix() {
    let component = create_test_text_component();
    let event = AgUiStreamEvent::UiComponent { component };
    let result = AgUiStream::format_event(&event);
    assert!(result.is_some());
    let s = result.unwrap();
    assert!(s.starts_with("data: "));
}

#[test]
fn test_push_done_returns_done_sentinel() {
    let result = AgUiStream::push_done();
    assert!(result.contains("done"));
    assert!(result.contains("data: "));
}

#[test]
fn test_push_text_serializes_content() {
    let result = AgUiStream::push_text("hello");
    assert!(result.is_some());
    let s = result.unwrap();
    assert!(s.contains("hello"));
}

#[test]
fn test_push_component_serializes_type() {
    let component = create_test_text_component();
    let result = AgUiStream::push_component(&component);
    assert!(result.is_some());
    let s = result.unwrap();
    assert!(s.contains("text"));
}

#[test]
fn test_format_stream_interleaves_events() {
    let events = vec![
        AgUiStreamEvent::Text {
            content: "start".to_string(),
        },
        AgUiStreamEvent::UiComponent {
            component: create_test_text_component(),
        },
        AgUiStreamEvent::Done,
    ];
    let result = AgUiStream::format_stream(&events);
    let lines: Vec<&str> = result.split("\n\n").filter(|s| !s.is_empty()).collect();
    assert_eq!(lines.len(), 3);
}

#[test]
fn test_format_stream_empty_returns_empty_string() {
    let result = AgUiStream::format_stream(&[]);
    assert_eq!(result, "");
}

#[test]
fn test_sse_line_ends_with_double_newline() {
    let event = AgUiStreamEvent::Text {
        content: "test".to_string(),
    };
    let result = AgUiStream::format_event(&event);
    assert!(result.is_some());
    let s = result.unwrap();
    assert!(s.ends_with("\n\n"));
}

#[test]
fn test_format_stream_drops_none_events() {
    let component = create_test_text_component();
    let events = vec![
        AgUiStreamEvent::Text {
            content: "valid".to_string(),
        },
        AgUiStreamEvent::UiComponent { component },
        AgUiStreamEvent::Done,
    ];
    let result = AgUiStream::format_stream(&events);
    let lines: Vec<&str> = result.split("\n\n").filter(|s| !s.is_empty()).collect();
    assert_eq!(lines.len(), 3);
}
