/// Phase 32 Wave 1: A2UI Schema Foundation
///
/// Tests all 18 A2UIComponent primitives can be:
/// 1. Created with valid data
/// 2. Serialized to JSON
/// 3. Deserialized from JSON
/// 4. Emitted via UIRequested event
/// 5. Embedded in AgentEvent enum
use chrono::Utc;
use siss_agent_shell::a2ui::{A2UIComponent, SelectOption};
use siss_agent_shell::events::AgentEvent;
use uuid::Uuid;

// ============================================================================
// DISPLAY COMPONENTS (8 types)
// ============================================================================

#[test]
fn test_a2ui_text_component() {
    let component = A2UIComponent::Text {
        id: "text_1".to_string(),
        content: "Hello World".to_string(),
        size: Some("lg".to_string()),
    };

    // Serialize
    let json = serde_json::to_string(&component).expect("Should serialize");
    assert!(json.contains("\"type\":\"text\""));
    assert!(json.contains("Hello World"));

    // Deserialize
    let deserialized: A2UIComponent = serde_json::from_str(&json).expect("Should deserialize");
    assert_eq!(component, deserialized);
}

#[test]
fn test_a2ui_badge_component() {
    let component = A2UIComponent::Badge {
        id: "badge_1".to_string(),
        label: "Important".to_string(),
        color: Some("red".to_string()),
    };

    let json = serde_json::to_string(&component).expect("Should serialize");
    assert!(json.contains("\"type\":\"badge\""));
    let deserialized: A2UIComponent = serde_json::from_str(&json).expect("Should deserialize");
    assert_eq!(component, deserialized);
}

#[test]
fn test_a2ui_alert_component() {
    let component = A2UIComponent::Alert {
        id: "alert_1".to_string(),
        message: "System update required".to_string(),
        level: "error".to_string(),
    };

    let json = serde_json::to_string(&component).expect("Should serialize");
    assert!(json.contains("\"type\":\"alert\""));
    let deserialized: A2UIComponent = serde_json::from_str(&json).expect("Should deserialize");
    assert_eq!(component, deserialized);
}

#[test]
fn test_a2ui_progress_component() {
    let component = A2UIComponent::Progress {
        id: "progress_1".to_string(),
        value: 75,
        max: 100,
        label: Some("75%".to_string()),
    };

    let json = serde_json::to_string(&component).expect("Should serialize");
    assert!(json.contains("\"type\":\"progress\""));
    assert!(json.contains("\"value\":75"));
    let deserialized: A2UIComponent = serde_json::from_str(&json).expect("Should deserialize");
    assert_eq!(component, deserialized);
}

#[test]
fn test_a2ui_divider_component() {
    let component = A2UIComponent::Divider {
        id: "divider_1".to_string(),
    };

    let json = serde_json::to_string(&component).expect("Should serialize");
    assert!(json.contains("\"type\":\"divider\""));
    let deserialized: A2UIComponent = serde_json::from_str(&json).expect("Should deserialize");
    assert_eq!(component, deserialized);
}

#[test]
fn test_a2ui_link_component() {
    let component = A2UIComponent::Link {
        id: "link_1".to_string(),
        label: "Click here".to_string(),
        href: "https://example.com".to_string(),
    };

    let json = serde_json::to_string(&component).expect("Should serialize");
    assert!(json.contains("\"type\":\"link\""));
    assert!(json.contains("https://example.com"));
    let deserialized: A2UIComponent = serde_json::from_str(&json).expect("Should deserialize");
    assert_eq!(component, deserialized);
}

#[test]
fn test_a2ui_tooltip_component() {
    let component = A2UIComponent::Tooltip {
        id: "tooltip_1".to_string(),
        text: "Hover me".to_string(),
        content: "Additional information".to_string(),
    };

    let json = serde_json::to_string(&component).expect("Should serialize");
    assert!(json.contains("\"type\":\"tooltip\""));
    let deserialized: A2UIComponent = serde_json::from_str(&json).expect("Should deserialize");
    assert_eq!(component, deserialized);
}

#[test]
fn test_a2ui_breadcrumb_component() {
    let component = A2UIComponent::Breadcrumb {
        id: "breadcrumb_1".to_string(),
        items: vec![
            "Home".to_string(),
            "Products".to_string(),
            "Item".to_string(),
        ],
    };

    let json = serde_json::to_string(&component).expect("Should serialize");
    assert!(json.contains("\"type\":\"breadcrumb\""));
    assert!(json.contains("Home"));
    let deserialized: A2UIComponent = serde_json::from_str(&json).expect("Should deserialize");
    assert_eq!(component, deserialized);
}

// ============================================================================
// FORM COMPONENTS (6 types)
// ============================================================================

#[test]
fn test_a2ui_input_component() {
    let component = A2UIComponent::Input {
        id: "input_1".to_string(),
        label: "Username".to_string(),
        placeholder: Some("Enter username".to_string()),
        required: true,
    };

    let json = serde_json::to_string(&component).expect("Should serialize");
    assert!(json.contains("\"type\":\"input\""));
    assert!(json.contains("\"required\":true"));
    let deserialized: A2UIComponent = serde_json::from_str(&json).expect("Should deserialize");
    assert_eq!(component, deserialized);
}

#[test]
fn test_a2ui_textarea_component() {
    let component = A2UIComponent::Textarea {
        id: "textarea_1".to_string(),
        label: "Comments".to_string(),
        rows: Some(5),
    };

    let json = serde_json::to_string(&component).expect("Should serialize");
    assert!(json.contains("\"type\":\"textarea\""));
    let deserialized: A2UIComponent = serde_json::from_str(&json).expect("Should deserialize");
    assert_eq!(component, deserialized);
}

#[test]
fn test_a2ui_select_component() {
    let component = A2UIComponent::Select {
        id: "select_1".to_string(),
        label: "Choose option".to_string(),
        options: vec![
            SelectOption {
                value: "opt1".to_string(),
                label: "Option 1".to_string(),
            },
            SelectOption {
                value: "opt2".to_string(),
                label: "Option 2".to_string(),
            },
        ],
    };

    let json = serde_json::to_string(&component).expect("Should serialize");
    assert!(json.contains("\"type\":\"select\""));
    assert!(json.contains("\"value\":\"opt1\""));
    let deserialized: A2UIComponent = serde_json::from_str(&json).expect("Should deserialize");
    assert_eq!(component, deserialized);
}

#[test]
fn test_a2ui_checkbox_component() {
    let component = A2UIComponent::Checkbox {
        id: "checkbox_1".to_string(),
        label: "Accept terms".to_string(),
        checked: true,
    };

    let json = serde_json::to_string(&component).expect("Should serialize");
    assert!(json.contains("\"type\":\"checkbox\""));
    assert!(json.contains("\"checked\":true"));
    let deserialized: A2UIComponent = serde_json::from_str(&json).expect("Should deserialize");
    assert_eq!(component, deserialized);
}

#[test]
fn test_a2ui_radio_component() {
    let component = A2UIComponent::Radio {
        id: "radio_1".to_string(),
        label: "Gender".to_string(),
        value: "male".to_string(),
        checked: false,
    };

    let json = serde_json::to_string(&component).expect("Should serialize");
    assert!(json.contains("\"type\":\"radio\""));
    assert!(json.contains("\"value\":\"male\""));
    let deserialized: A2UIComponent = serde_json::from_str(&json).expect("Should deserialize");
    assert_eq!(component, deserialized);
}

#[test]
fn test_a2ui_button_component() {
    let component = A2UIComponent::Button {
        id: "button_1".to_string(),
        label: "Submit".to_string(),
        action: Some("submit".to_string()),
    };

    let json = serde_json::to_string(&component).expect("Should serialize");
    assert!(json.contains("\"type\":\"button\""));
    assert!(json.contains("\"label\":\"Submit\""));
    let deserialized: A2UIComponent = serde_json::from_str(&json).expect("Should deserialize");
    assert_eq!(component, deserialized);
}

// ============================================================================
// LAYOUT COMPONENTS (4 types)
// ============================================================================

#[test]
fn test_a2ui_card_component() {
    let component = A2UIComponent::Card {
        id: "card_1".to_string(),
        title: Some("Card Title".to_string()),
        children: vec![A2UIComponent::Text {
            id: "text_in_card".to_string(),
            content: "Card content".to_string(),
            size: None,
        }],
    };

    let json = serde_json::to_string(&component).expect("Should serialize");
    assert!(json.contains("\"type\":\"card\""));
    assert!(json.contains("Card content"));
    let deserialized: A2UIComponent = serde_json::from_str(&json).expect("Should deserialize");
    assert_eq!(component, deserialized);
}

#[test]
fn test_a2ui_grid_component() {
    let component = A2UIComponent::Grid {
        id: "grid_1".to_string(),
        columns: 3,
        children: vec![
            A2UIComponent::Text {
                id: "c1".to_string(),
                content: "Cell 1".to_string(),
                size: None,
            },
            A2UIComponent::Text {
                id: "c2".to_string(),
                content: "Cell 2".to_string(),
                size: None,
            },
        ],
    };

    let json = serde_json::to_string(&component).expect("Should serialize");
    assert!(json.contains("\"type\":\"grid\""));
    assert!(json.contains("\"columns\":3"));
    let deserialized: A2UIComponent = serde_json::from_str(&json).expect("Should deserialize");
    assert_eq!(component, deserialized);
}

#[test]
fn test_a2ui_modal_component() {
    let component = A2UIComponent::Modal {
        id: "modal_1".to_string(),
        title: "Confirmation".to_string(),
        content: "Are you sure?".to_string(),
        children: vec![A2UIComponent::Button {
            id: "confirm_btn".to_string(),
            label: "Yes".to_string(),
            action: Some("confirm".to_string()),
        }],
    };

    let json = serde_json::to_string(&component).expect("Should serialize");
    assert!(json.contains("\"type\":\"modal\""));
    assert!(json.contains("Confirmation"));
    let deserialized: A2UIComponent = serde_json::from_str(&json).expect("Should deserialize");
    assert_eq!(component, deserialized);
}

#[test]
fn test_a2ui_table_component() {
    let component = A2UIComponent::Table {
        id: "table_1".to_string(),
        headers: vec!["ID".to_string(), "Name".to_string(), "Email".to_string()],
        rows: vec![
            vec![
                "1".to_string(),
                "Alice".to_string(),
                "alice@example.com".to_string(),
            ],
            vec![
                "2".to_string(),
                "Bob".to_string(),
                "bob@example.com".to_string(),
            ],
        ],
    };

    let json = serde_json::to_string(&component).expect("Should serialize");
    assert!(json.contains("\"type\":\"table\""));
    assert!(json.contains("Alice"));
    let deserialized: A2UIComponent = serde_json::from_str(&json).expect("Should deserialize");
    assert_eq!(component, deserialized);
}

// ============================================================================
// EVENT INTEGRATION: UIRequested
// ============================================================================

#[test]
fn test_ui_requested_event_with_single_component() {
    let task_id = Uuid::new_v4();
    let components = vec![A2UIComponent::Text {
        id: "text_1".to_string(),
        content: "Hello".to_string(),
        size: None,
    }];

    let event = AgentEvent::UIRequested {
        task_id,
        components: components.clone(),
        form_id: Some("form_1".to_string()),
        timestamp: Utc::now(),
    };

    // Verify event_type method returns correct value
    assert_eq!(event.event_type(), "ui_requested");

    // Serialize event to JSON
    let json = serde_json::to_string(&event).expect("Should serialize event");
    assert!(json.contains("UIRequested"));
    assert!(json.contains(&task_id.to_string()));

    // Deserialize back
    let deserialized: AgentEvent = serde_json::from_str(&json).expect("Should deserialize event");
    match deserialized {
        AgentEvent::UIRequested {
            task_id: tid,
            components: comps,
            form_id,
            ..
        } => {
            assert_eq!(tid, task_id);
            assert_eq!(comps.len(), 1);
            assert_eq!(form_id, Some("form_1".to_string()));
        }
        _ => panic!("Expected UIRequested event"),
    }
}

#[test]
fn test_ui_requested_event_with_multiple_components() {
    let task_id = Uuid::new_v4();
    let components = vec![
        A2UIComponent::Input {
            id: "name".to_string(),
            label: "Name".to_string(),
            placeholder: None,
            required: true,
        },
        A2UIComponent::Input {
            id: "email".to_string(),
            label: "Email".to_string(),
            placeholder: None,
            required: true,
        },
        A2UIComponent::Button {
            id: "submit".to_string(),
            label: "Submit".to_string(),
            action: Some("submit".to_string()),
        },
    ];

    let event = AgentEvent::UIRequested {
        task_id,
        components: components.clone(),
        form_id: Some("contact_form".to_string()),
        timestamp: Utc::now(),
    };

    let json = serde_json::to_string(&event).expect("Should serialize");
    let deserialized: AgentEvent = serde_json::from_str(&json).expect("Should deserialize");

    match deserialized {
        AgentEvent::UIRequested {
            task_id: tid,
            components: comps,
            ..
        } => {
            assert_eq!(tid, task_id);
            assert_eq!(comps.len(), 3);
            assert!(matches!(comps[0], A2UIComponent::Input { .. }));
            assert!(matches!(comps[1], A2UIComponent::Input { .. }));
            assert!(matches!(comps[2], A2UIComponent::Button { .. }));
        }
        _ => panic!("Expected UIRequested event"),
    }
}

#[test]
fn test_ui_requested_event_without_form_id() {
    let task_id = Uuid::new_v4();
    let components = vec![A2UIComponent::Text {
        id: "status".to_string(),
        content: "Processing...".to_string(),
        size: None,
    }];

    let event = AgentEvent::UIRequested {
        task_id,
        components,
        form_id: None,
        timestamp: Utc::now(),
    };

    let json = serde_json::to_string(&event).expect("Should serialize");
    let deserialized: AgentEvent = serde_json::from_str(&json).expect("Should deserialize");

    match deserialized {
        AgentEvent::UIRequested { form_id, .. } => {
            assert_eq!(form_id, None);
        }
        _ => panic!("Expected UIRequested event"),
    }
}

#[test]
fn test_ui_requested_event_with_nested_layout() {
    let task_id = Uuid::new_v4();
    let components = vec![A2UIComponent::Card {
        id: "main_card".to_string(),
        title: Some("User Form".to_string()),
        children: vec![
            A2UIComponent::Input {
                id: "username".to_string(),
                label: "Username".to_string(),
                placeholder: Some("Enter username".to_string()),
                required: true,
            },
            A2UIComponent::Input {
                id: "password".to_string(),
                label: "Password".to_string(),
                placeholder: None,
                required: true,
            },
            A2UIComponent::Button {
                id: "submit_btn".to_string(),
                label: "Login".to_string(),
                action: Some("submit".to_string()),
            },
        ],
    }];

    let event = AgentEvent::UIRequested {
        task_id,
        components,
        form_id: Some("login_form".to_string()),
        timestamp: Utc::now(),
    };

    let json = serde_json::to_string(&event).expect("Should serialize");
    let deserialized: AgentEvent = serde_json::from_str(&json).expect("Should deserialize");

    match deserialized {
        AgentEvent::UIRequested { components, .. } => {
            assert_eq!(components.len(), 1);
            if let A2UIComponent::Card { children, .. } = &components[0] {
                assert_eq!(children.len(), 3);
            } else {
                panic!("Expected Card component");
            }
        }
        _ => panic!("Expected UIRequested event"),
    }
}

// ============================================================================
// COMPREHENSIVE TEST: All 18 types in single serialize/deserialize
// ============================================================================

#[test]
fn test_all_18_components_serialize_deserialize() {
    let all_components = vec![
        // Display (8)
        A2UIComponent::Text {
            id: "1".to_string(),
            content: "t".to_string(),
            size: None,
        },
        A2UIComponent::Badge {
            id: "2".to_string(),
            label: "b".to_string(),
            color: None,
        },
        A2UIComponent::Alert {
            id: "3".to_string(),
            message: "a".to_string(),
            level: "info".to_string(),
        },
        A2UIComponent::Progress {
            id: "4".to_string(),
            value: 50,
            max: 100,
            label: None,
        },
        A2UIComponent::Divider {
            id: "5".to_string(),
        },
        A2UIComponent::Link {
            id: "6".to_string(),
            label: "l".to_string(),
            href: "http://x".to_string(),
        },
        A2UIComponent::Tooltip {
            id: "7".to_string(),
            text: "t".to_string(),
            content: "tip".to_string(),
        },
        A2UIComponent::Breadcrumb {
            id: "8".to_string(),
            items: vec![],
        },
        // Forms (6)
        A2UIComponent::Input {
            id: "9".to_string(),
            label: "i".to_string(),
            placeholder: None,
            required: false,
        },
        A2UIComponent::Textarea {
            id: "10".to_string(),
            label: "ta".to_string(),
            rows: None,
        },
        A2UIComponent::Select {
            id: "11".to_string(),
            label: "s".to_string(),
            options: vec![],
        },
        A2UIComponent::Checkbox {
            id: "12".to_string(),
            label: "c".to_string(),
            checked: false,
        },
        A2UIComponent::Radio {
            id: "13".to_string(),
            label: "r".to_string(),
            value: "v".to_string(),
            checked: false,
        },
        A2UIComponent::Button {
            id: "14".to_string(),
            label: "btn".to_string(),
            action: None,
        },
        // Layout (4)
        A2UIComponent::Card {
            id: "15".to_string(),
            title: None,
            children: vec![],
        },
        A2UIComponent::Grid {
            id: "16".to_string(),
            columns: 2,
            children: vec![],
        },
        A2UIComponent::Modal {
            id: "17".to_string(),
            title: "m".to_string(),
            content: "content".to_string(),
            children: vec![],
        },
        A2UIComponent::Table {
            id: "18".to_string(),
            headers: vec![],
            rows: vec![],
        },
    ];

    for (idx, component) in all_components.iter().enumerate() {
        let json = serde_json::to_string(&component)
            .expect(&format!("Should serialize component {}", idx));
        let deserialized: A2UIComponent =
            serde_json::from_str(&json).expect(&format!("Should deserialize component {}", idx));
        assert_eq!(component, &deserialized, "Component {} mismatch", idx);
    }
}

// ============================================================================
// COMPREHENSIVE TEST: All 18 types in UIRequested event
// ============================================================================

#[test]
fn test_ui_requested_with_all_18_components() {
    let task_id = Uuid::new_v4();
    let all_components = vec![
        // Display (8)
        A2UIComponent::Text {
            id: "1".to_string(),
            content: "t".to_string(),
            size: None,
        },
        A2UIComponent::Badge {
            id: "2".to_string(),
            label: "b".to_string(),
            color: None,
        },
        A2UIComponent::Alert {
            id: "3".to_string(),
            message: "a".to_string(),
            level: "info".to_string(),
        },
        A2UIComponent::Progress {
            id: "4".to_string(),
            value: 50,
            max: 100,
            label: None,
        },
        A2UIComponent::Divider {
            id: "5".to_string(),
        },
        A2UIComponent::Link {
            id: "6".to_string(),
            label: "l".to_string(),
            href: "http://x".to_string(),
        },
        A2UIComponent::Tooltip {
            id: "7".to_string(),
            text: "t".to_string(),
            content: "tip".to_string(),
        },
        A2UIComponent::Breadcrumb {
            id: "8".to_string(),
            items: vec![],
        },
        // Forms (6)
        A2UIComponent::Input {
            id: "9".to_string(),
            label: "i".to_string(),
            placeholder: None,
            required: false,
        },
        A2UIComponent::Textarea {
            id: "10".to_string(),
            label: "ta".to_string(),
            rows: None,
        },
        A2UIComponent::Select {
            id: "11".to_string(),
            label: "s".to_string(),
            options: vec![],
        },
        A2UIComponent::Checkbox {
            id: "12".to_string(),
            label: "c".to_string(),
            checked: false,
        },
        A2UIComponent::Radio {
            id: "13".to_string(),
            label: "r".to_string(),
            value: "v".to_string(),
            checked: false,
        },
        A2UIComponent::Button {
            id: "14".to_string(),
            label: "btn".to_string(),
            action: None,
        },
        // Layout (4)
        A2UIComponent::Card {
            id: "15".to_string(),
            title: None,
            children: vec![],
        },
        A2UIComponent::Grid {
            id: "16".to_string(),
            columns: 2,
            children: vec![],
        },
        A2UIComponent::Modal {
            id: "17".to_string(),
            title: "m".to_string(),
            content: "content".to_string(),
            children: vec![],
        },
        A2UIComponent::Table {
            id: "18".to_string(),
            headers: vec![],
            rows: vec![],
        },
    ];

    let event = AgentEvent::UIRequested {
        task_id,
        components: all_components.clone(),
        form_id: Some("comprehensive_form".to_string()),
        timestamp: Utc::now(),
    };

    let json =
        serde_json::to_string(&event).expect("Should serialize event with all 18 components");
    let deserialized: AgentEvent =
        serde_json::from_str(&json).expect("Should deserialize event with all 18 components");

    match deserialized {
        AgentEvent::UIRequested {
            task_id: tid,
            components: comps,
            ..
        } => {
            assert_eq!(tid, task_id);
            assert_eq!(comps.len(), 18, "All 18 components must be present");
            for (idx, (original, deserialized)) in
                all_components.iter().zip(comps.iter()).enumerate()
            {
                assert_eq!(original, deserialized, "Component {} mismatch", idx);
            }
        }
        _ => panic!("Expected UIRequested event"),
    }
}
