use siss_cockpit::a2ui::{form_handler::FormHandler, renderer::Renderer};
use siss_agent_shell::a2ui::{A2UIComponent, FormSubmission, A2UIValidator, SelectOption};
use serde_json::json;
use std::time::Instant;
use uuid::Uuid;

/// Test 1: Full pipeline JSON → deserialize → validate → render
#[test]
fn test_pipeline_json_deserialize_validate_render() {
    let json_str = r#"{"type":"text","id":"msg1","content":"Hello World","size":null}"#;
    let component: A2UIComponent = serde_json::from_str(json_str).expect("JSON parse failed");

    assert!(A2UIValidator::validate(&component).is_ok());

    let html = Renderer::render(&component);
    assert!(html.contains("Hello World"));
}

/// Test 2: Form inputs render inside Card
#[test]
fn test_pipeline_form_inputs_render() {
    let component = A2UIComponent::Card {
        id: "approval_card".to_string(),
        title: Some("Approval Form".to_string()),
        children: vec![
            A2UIComponent::Input {
                id: "email".to_string(),
                label: "Email".to_string(),
                placeholder: Some("user@example.com".to_string()),
                required: true,
            },
            A2UIComponent::Textarea {
                id: "reason".to_string(),
                label: "Reason".to_string(),
                rows: Some(5),
            },
            A2UIComponent::Button {
                id: "submit_btn".to_string(),
                label: "Submit".to_string(),
                action: Some("submit".to_string()),
            },
        ],
    };

    assert!(A2UIValidator::validate(&component).is_ok());

    let html = Renderer::render(&component);
    assert!(html.contains("Approval Form"));
    assert!(html.contains("email"));
    assert!(html.contains("Email"));
    assert!(html.contains("reason"));
    assert!(html.contains("Reason"));
    assert!(html.contains("submit_btn"));
    assert!(html.contains("Submit"));
}

/// Test 3: FormSubmission roundtrip accepted
#[test]
fn test_form_submission_accepted_roundtrip() {
    let task_id = Uuid::new_v4();
    let submission = FormSubmission {
        task_id,
        form_id: "approval_form".to_string(),
        values: json!({
            "approved": true,
            "reason": "looks good"
        }),
    };

    let handler = FormHandler::new();
    let result = handler.process(&submission);

    assert!(result.is_ok());
    let response = result.unwrap();
    assert_eq!(response.status, "accepted");
    assert!(!response.submission_id.is_empty());
    // submission_id should be valid UUID string
    Uuid::parse_str(&response.submission_id).expect("submission_id should be UUID");
}

/// Test 4: Validator blocks invalid component before renderer
#[test]
fn test_validator_blocks_invalid_before_render() {
    let component = A2UIComponent::Text {
        id: "".to_string(), // Empty ID — should fail validation
        content: "Content".to_string(),
        size: None,
    };

    // Validator rejects empty ID
    assert!(A2UIValidator::validate(&component).is_err());

    // Renderer should still work (it ignores validation)
    // but in real flow, we'd never reach here
    let html = Renderer::render(&component);
    assert!(!html.is_empty()); // Renderer doesn't enforce validation
}

/// Test 5: XSS payload escapes through full pipeline
#[test]
fn test_renderer_xss_safety_through_pipeline() {
    let component = A2UIComponent::Text {
        id: "xss_test".to_string(),
        content: "<script>alert('xss')</script>".to_string(),
        size: None,
    };

    // Validator passes (content is checked for emptiness, not safety)
    assert!(A2UIValidator::validate(&component).is_ok());

    // Renderer escapes the dangerous content
    let html = Renderer::render(&component);
    assert!(!html.contains("<script>"), "Script tag should be escaped");
    assert!(html.contains("&lt;") || html.contains("&gt;"), "Should contain escaped HTML");
}

/// Test 6: Latency all 18 primitives under 200ms
#[test]
fn test_latency_all_18_primitives_under_200ms() {
    let primitives = vec![
        A2UIComponent::Text {
            id: "t1".to_string(),
            content: "text".to_string(),
            size: None,
        },
        A2UIComponent::Badge {
            id: "b1".to_string(),
            label: "badge".to_string(),
            color: None,
        },
        A2UIComponent::Alert {
            id: "a1".to_string(),
            message: "alert".to_string(),
            level: "info".to_string(),
        },
        A2UIComponent::Progress {
            id: "p1".to_string(),
            value: 50,
            max: 100,
            label: None,
        },
        A2UIComponent::Divider {
            id: "d1".to_string(),
        },
        A2UIComponent::Link {
            id: "l1".to_string(),
            label: "link".to_string(),
            href: "http://example.com".to_string(),
        },
        A2UIComponent::Tooltip {
            id: "tt1".to_string(),
            text: "tooltip".to_string(),
            content: "content".to_string(),
        },
        A2UIComponent::Breadcrumb {
            id: "bc1".to_string(),
            items: vec!["home".to_string(), "products".to_string()],
        },
        A2UIComponent::Input {
            id: "input1".to_string(),
            label: "input".to_string(),
            placeholder: None,
            required: false,
        },
        A2UIComponent::Textarea {
            id: "ta1".to_string(),
            label: "textarea".to_string(),
            rows: None,
        },
        A2UIComponent::Select {
            id: "sel1".to_string(),
            label: "select".to_string(),
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
        },
        A2UIComponent::Checkbox {
            id: "cb1".to_string(),
            label: "checkbox".to_string(),
            checked: false,
        },
        A2UIComponent::Radio {
            id: "rad1".to_string(),
            label: "radio".to_string(),
            value: "v1".to_string(),
            checked: false,
        },
        A2UIComponent::Button {
            id: "btn1".to_string(),
            label: "button".to_string(),
            action: None,
        },
        A2UIComponent::Card {
            id: "card1".to_string(),
            title: None,
            children: vec![],
        },
        A2UIComponent::Grid {
            id: "grid1".to_string(),
            columns: 1,
            children: vec![],
        },
        A2UIComponent::Modal {
            id: "modal1".to_string(),
            title: "modal".to_string(),
            content: "content".to_string(),
            children: vec![],
        },
        A2UIComponent::Table {
            id: "table1".to_string(),
            headers: vec!["Name".to_string(), "Value".to_string()],
            rows: vec![vec!["row1".to_string(), "val1".to_string()]],
        },
    ];

    let start = Instant::now();

    for component in &primitives {
        // Validate each
        let _ = A2UIValidator::validate(component);
        // Render each
        let _ = Renderer::render(component);
    }

    let elapsed = start.elapsed();
    assert!(
        elapsed.as_millis() < 200,
        "All 18 primitives should validate + render in <200ms, took {}ms",
        elapsed.as_millis()
    );
}

/// Test 7: Deeply nested layout renders
#[test]
fn test_layout_nested_card_grid_modal_table() {
    let component = A2UIComponent::Card {
        id: "outer_card".to_string(),
        title: Some("Outer Card".to_string()),
        children: vec![A2UIComponent::Grid {
            id: "grid".to_string(),
            columns: 2,
            children: vec![
                A2UIComponent::Modal {
                    id: "modal".to_string(),
                    title: "Modal Title".to_string(),
                    content: "Modal content".to_string(),
                    children: vec![],
                },
                A2UIComponent::Table {
                    id: "table".to_string(),
                    headers: vec!["Col1".to_string(), "Col2".to_string()],
                    rows: vec![
                        vec!["Data1".to_string(), "Data2".to_string()],
                        vec!["Data3".to_string(), "Data4".to_string()],
                    ],
                },
            ],
        }],
    };

    assert!(A2UIValidator::validate(&component).is_ok());

    let html = Renderer::render(&component);
    assert!(html.contains("Outer Card"));
    assert!(html.contains("Modal Title"));
    assert!(html.contains("Modal content"));
    assert!(html.contains("Col1"));
    assert!(html.contains("Data1"));
    assert!(html.contains("Data4"));
}

/// Test 8: Full RCE approval flow
#[test]
fn test_rce_approval_flow() {
    // Agent emits approval request
    let approval_form = A2UIComponent::Card {
        id: "approval_request".to_string(),
        title: Some("Action Requires Approval".to_string()),
        children: vec![
            A2UIComponent::Text {
                id: "msg".to_string(),
                content: "Do you approve this action?".to_string(),
                size: None,
            },
            A2UIComponent::Input {
                id: "signature".to_string(),
                label: "Your Signature".to_string(),
                placeholder: Some("Enter your name".to_string()),
                required: true,
            },
            A2UIComponent::Button {
                id: "approve_btn".to_string(),
                label: "Approve".to_string(),
                action: Some("submit".to_string()),
            },
        ],
    };

    // Validator checks it
    assert!(A2UIValidator::validate(&approval_form).is_ok());

    // Cockpit renders it
    let html = Renderer::render(&approval_form);
    assert!(html.contains("Action Requires Approval"));
    assert!(html.contains("signature"));
    assert!(html.contains("Your Signature"));
    assert!(html.contains("Approve"));

    // Operator submits
    let task_id = Uuid::new_v4();
    let submission = FormSubmission {
        task_id,
        form_id: "approval_request".to_string(),
        values: json!({
            "signature": "Alice"
        }),
    };

    // Form handler accepts it
    let handler = FormHandler::new();
    let response = handler.process(&submission).expect("form processing should succeed");
    assert_eq!(response.status, "accepted");

    // Response routed back to agent
    assert!(!response.submission_id.is_empty());
}
