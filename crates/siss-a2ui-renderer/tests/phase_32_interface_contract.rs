/// Phase 32: A2UI Interface Contract Tests
/// Golden path validation of the 18 JSON component primitives,
/// SSE stream specification, and fail-closed validation rules
use siss_a2ui_renderer::{A2UIPayload, PayloadRenderer, PayloadValidator, ValidationError};
use uuid::Uuid;

/// Test 1: All 18 JSON component primitives validate and render
#[test]
fn test_18_component_primitives_valid_and_render() {
    let validator = PayloadValidator::new();
    let renderer = PayloadRenderer::new();

    let test_cases = vec![
        // Display primitives
        (
            "text",
            serde_json::json!({"type": "text", "id": "text1", "content": "Hello"}),
        ),
        (
            "badge",
            serde_json::json!({"type": "badge", "id": "badge1", "label": "New"}),
        ),
        (
            "alert",
            serde_json::json!({"type": "alert", "id": "alert1", "message": "Warning", "level": "warn"}),
        ),
        (
            "progress",
            serde_json::json!({"type": "progress", "id": "prog1", "value": 50, "max": 100}),
        ),
        (
            "divider",
            serde_json::json!({"type": "divider", "id": "div1"}),
        ),
        (
            "link",
            serde_json::json!({"type": "link", "id": "link1", "label": "Click", "href": "https://example.com"}),
        ),
        (
            "tooltip",
            serde_json::json!({"type": "tooltip", "id": "tip1", "text": "Hover", "content": "Tooltip text"}),
        ),
        (
            "breadcrumb",
            serde_json::json!({"type": "breadcrumb", "id": "bread1", "items": ["Home", "Section"]}),
        ),
        // Form primitives
        (
            "input",
            serde_json::json!({"type": "input", "id": "input1", "label": "Name"}),
        ),
        (
            "textarea",
            serde_json::json!({"type": "textarea", "id": "text1", "label": "Comment"}),
        ),
        (
            "select",
            serde_json::json!({"type": "select", "id": "select1", "label": "Choose", "options": []}),
        ),
        (
            "checkbox",
            serde_json::json!({"type": "checkbox", "id": "check1", "label": "Agree"}),
        ),
        (
            "radio",
            serde_json::json!({"type": "radio", "id": "radio1", "label": "Option", "value": "opt1"}),
        ),
        (
            "button",
            serde_json::json!({"type": "button", "id": "btn1", "label": "Submit"}),
        ),
        // Layout primitives
        (
            "card",
            serde_json::json!({"type": "card", "id": "card1", "children": []}),
        ),
        (
            "grid",
            serde_json::json!({"type": "grid", "id": "grid1", "columns": 2, "children": []}),
        ),
        (
            "modal",
            serde_json::json!({"type": "modal", "id": "modal1", "title": "Dialog", "content": "Content", "children": []}),
        ),
        (
            "table",
            serde_json::json!({"type": "table", "id": "table1", "headers": ["Col1"], "rows": [["Data1"]]}),
        ),
    ];

    assert_eq!(
        test_cases.len(),
        18,
        "Must have exactly 18 component primitives"
    );

    for (prim_type, json) in test_cases {
        let payload = A2UIPayload {
            id: Uuid::new_v4(),
            components: vec![json],
        };

        // All 18 primitives must validate
        let result = validator.validate(&payload);
        assert!(
            result.is_ok(),
            "Primitive '{}' should validate successfully, got error: {:?}",
            prim_type,
            result
        );

        // All 18 primitives must render to non-empty HTML
        if let Ok(components) = result {
            let html = renderer.render_all(components);
            assert!(
                !html.is_empty(),
                "Primitive '{}' should render HTML",
                prim_type
            );
        }
    }
}

/// Test 2: AG-UI SSE Stream Contract — unknown types are fail-closed rejected
#[test]
fn test_fail_closed_validation_rejects_unknown_types() {
    let validator = PayloadValidator::new();

    let unknown_types = vec!["UnknownComponent", "CustomWidget", "ProprietaryUI"];

    for unknown in unknown_types {
        let payload = A2UIPayload {
            id: Uuid::new_v4(),
            components: vec![serde_json::json!({
                "type": unknown,
                "id": "test",
            })],
        };

        let result = validator.validate(&payload);
        assert!(
            matches!(result, Err(ValidationError::UnknownType(_))),
            "Unknown type '{}' must be fail-closed rejected",
            unknown
        );
    }
}

/// Test 3: Fail-closed validation rejects missing type field
#[test]
fn test_fail_closed_validation_rejects_missing_type_field() {
    let validator = PayloadValidator::new();

    let payload = A2UIPayload {
        id: Uuid::new_v4(),
        components: vec![serde_json::json!({
            "id": "test",
            "label": "Missing type field"
        })],
    };

    let result = validator.validate(&payload);
    assert!(
        matches!(result, Err(ValidationError::UnknownType(_))),
        "Missing type field must be fail-closed rejected"
    );
}

/// Test 4: SSE Stream Contract — empty payloads timeout gracefully
#[test]
fn test_sse_stream_empty_payload_handling() {
    let validator = PayloadValidator::new();

    // Empty payload (equivalent to SSE stream timeout)
    let payload = A2UIPayload {
        id: Uuid::new_v4(),
        components: vec![],
    };

    let result = validator.validate(&payload);
    assert!(
        matches!(result, Err(ValidationError::EmptyPayload)),
        "Empty SSE payload must be caught and fail gracefully"
    );
}

/// Test 5: AG-UI Middleware translation — JSON schema is strictly typed and rejects malformed input
#[test]
fn test_ag_ui_middleware_strict_json_validation() {
    let validator = PayloadValidator::new();

    // Malformed JSON component (e.g., from garbled SSE stream)
    let payload = A2UIPayload {
        id: Uuid::new_v4(),
        components: vec![serde_json::json!({
            "type": 123,  // type should be string, not number
            "id": "test",
        })],
    };

    let result = validator.validate(&payload);
    // Should fail because type is not a string (AG-UI middleware strict contract)
    assert!(
        result.is_err(),
        "Malformed JSON (type as number instead of string) must be rejected"
    );
}
