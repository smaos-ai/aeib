/// Phase 32 Wave 3: End-to-End Integration Tests
/// TDD: 8 failing tests define expected behavior for complete SSE→Validator→Renderer→FormHandler pipeline
///
/// Coverage:
/// 1. Text component end-to-end (emit → render → verify)
/// 2. Form input component (render → user input → validate → submit)
/// 3. Select dropdown (options → user select → form value)
/// 4. Modal dialog (render → close → verify state)
/// 5. Grid layout with children (render → verify layout)
/// 6. Table component (render → verify rows/headers)
/// 7. Async SSE streaming (multiple components streamed)
/// 8. Form submission roundtrip (UI → FormHandler → response)

#[cfg(test)]
mod integration_tests {
    use siss_agent_shell::a2ui::{A2UIComponent, A2UIValidator, SelectOption, FormSubmission};
    use crate::a2ui::renderer::Renderer;
    use crate::a2ui::sse_handler::{SseComponentMessage, A2UISseHandler};
    use crate::a2ui::form_handler::FormHandler;
    use serde_json::json;
    use uuid::Uuid;

    // ========== TEST 1: Text Component End-to-End ==========
    // test_e2e_text_component: ensures Schema → Validator → Renderer pipeline works for Text
    #[test]
    fn test_e2e_text_component_emit_validate_render() {
        // Step 1: Create component (agent emission)
        let component = A2UIComponent::Text {
            id: "text_e2e_1".to_string(),
            content: "End-to-End Test Message".to_string(),
            size: Some("lg".to_string()),
        };

        // Step 2: Validate component (agent-side)
        let validation_result = A2UIValidator::validate(&component);
        assert!(validation_result.is_ok(), "Text component validation failed");

        // Step 3: Render to HTML (cockpit-side)
        let html = Renderer::render(&component);

        // Step 4: Verify rendered output
        assert!(html.contains("End-to-End Test Message"), "Content missing from HTML");
        assert!(html.contains("text-lg"), "Size class missing from HTML");
        assert!(html.contains("a2ui-text"), "Component class missing from HTML");
    }

    // ========== TEST 2: Form Input Component Full Lifecycle ==========
    // test_e2e_form_input_lifecycle: ensures Input → render → validation → submission
    #[test]
    fn test_e2e_form_input_render_validate_submit() {
        // Step 1: Create input component with required flag
        let component = A2UIComponent::Input {
            id: "username_input".to_string(),
            label: "Username".to_string(),
            placeholder: Some("Enter your username".to_string()),
            required: true,
        };

        // Step 2: Validate component
        assert!(A2UIValidator::validate(&component).is_ok());

        // Step 3: Render to HTML
        let html = Renderer::render(&component);
        assert!(html.contains("username_input"));
        assert!(html.contains("Username"));
        assert!(html.contains("required"));
        assert!(html.contains("Enter your username"));

        // Step 4: Simulate form submission with this input's value
        let task_id = Uuid::new_v4();
        let submission = FormSubmission {
            task_id,
            form_id: "user_form".to_string(),
            values: json!({
                "username_input": "testuser123"
            }),
        };

        // Step 5: Process form submission
        let handler = FormHandler::new();
        let result = handler.process(&submission);
        assert!(result.is_ok(), "Form submission failed");
        assert_eq!(result.unwrap().status, "accepted");
    }

    // ========== TEST 3: Select Dropdown with Options ==========
    // test_e2e_select_dropdown: ensures Select → options render → user selection → submission
    #[test]
    fn test_e2e_select_dropdown_options_submit() {
        // Step 1: Create select component with options
        let options = vec![
            SelectOption {
                value: "opt_red".to_string(),
                label: "Red".to_string(),
            },
            SelectOption {
                value: "opt_blue".to_string(),
                label: "Blue".to_string(),
            },
            SelectOption {
                value: "opt_green".to_string(),
                label: "Green".to_string(),
            },
        ];

        let component = A2UIComponent::Select {
            id: "color_select".to_string(),
            label: "Choose Color".to_string(),
            options,
        };

        // Step 2: Validate
        assert!(A2UIValidator::validate(&component).is_ok());

        // Step 3: Render to HTML
        let html = Renderer::render(&component);
        assert!(html.contains("color_select"));
        assert!(html.contains("Choose Color"));
        assert!(html.contains("opt_red"));
        assert!(html.contains("opt_blue"));
        assert!(html.contains("opt_green"));
        assert!(html.contains("Red"));
        assert!(html.contains("Blue"));
        assert!(html.contains("Green"));

        // Step 4: Simulate user selection and form submission
        let submission = FormSubmission {
            task_id: Uuid::new_v4(),
            form_id: "color_form".to_string(),
            values: json!({
                "color_select": "opt_blue"
            }),
        };

        // Step 5: Process submission
        let handler = FormHandler::new();
        let result = handler.process(&submission).unwrap();
        assert_eq!(result.status, "accepted");
    }

    // ========== TEST 4: Modal Dialog Render and State ==========
    // test_e2e_modal_dialog: ensures Modal → render → verify structure
    #[test]
    fn test_e2e_modal_dialog_render_structure() {
        // Step 1: Create modal with children
        let children = vec![
            A2UIComponent::Text {
                id: "modal_text".to_string(),
                content: "Confirm deletion?".to_string(),
                size: None,
            },
            A2UIComponent::Button {
                id: "confirm_btn".to_string(),
                label: "Confirm".to_string(),
                action: Some("submit".to_string()),
            },
        ];

        let component = A2UIComponent::Modal {
            id: "delete_modal".to_string(),
            title: "Delete Confirmation".to_string(),
            content: "This action cannot be undone.".to_string(),
            children,
        };

        // Step 2: Validate modal
        assert!(A2UIValidator::validate(&component).is_ok());

        // Step 3: Render to HTML
        let html = Renderer::render(&component);

        // Step 4: Verify modal structure
        assert!(html.contains("delete_modal"));
        assert!(html.contains("delete_modal"), "Modal ID attribute missing");
        assert!(html.contains("Delete Confirmation"));
        assert!(html.contains("Confirm deletion?"));
        assert!(html.contains("confirm_btn"));
        assert!(html.contains("Confirm"));
        assert!(html.contains("role=\"dialog\""), "Missing dialog role for accessibility");
    }

    // ========== TEST 5: Grid Layout with Children ==========
    // test_e2e_grid_layout: ensures Grid → multiple columns → children render
    #[test]
    fn test_e2e_grid_layout_children_render() {
        // Step 1: Create grid with multiple children
        let children = vec![
            A2UIComponent::Text {
                id: "grid_item_1".to_string(),
                content: "Item 1".to_string(),
                size: None,
            },
            A2UIComponent::Text {
                id: "grid_item_2".to_string(),
                content: "Item 2".to_string(),
                size: None,
            },
            A2UIComponent::Text {
                id: "grid_item_3".to_string(),
                content: "Item 3".to_string(),
                size: None,
            },
            A2UIComponent::Text {
                id: "grid_item_4".to_string(),
                content: "Item 4".to_string(),
                size: None,
            },
        ];

        let component = A2UIComponent::Grid {
            id: "grid_layout".to_string(),
            columns: 2,
            children,
        };

        // Step 2: Validate grid
        assert!(A2UIValidator::validate(&component).is_ok());

        // Step 3: Render to HTML
        let html = Renderer::render(&component);

        // Step 4: Verify grid structure and children
        assert!(html.contains("a2ui-grid"));
        assert!(html.contains("grid-template-columns: repeat(2, 1fr)"));
        assert!(html.contains("Item 1"));
        assert!(html.contains("Item 2"));
        assert!(html.contains("Item 3"));
        assert!(html.contains("Item 4"));
        assert!(html.contains("grid-item"), "Grid item wrapper class missing");
    }

    // ========== TEST 6: Table Component with Rows and Headers ==========
    // test_e2e_table_component: ensures Table → headers → rows → render
    #[test]
    fn test_e2e_table_render_headers_rows() {
        // Step 1: Create table with headers and rows
        let component = A2UIComponent::Table {
            id: "data_table".to_string(),
            headers: vec!["Name".to_string(), "Email".to_string(), "Status".to_string()],
            rows: vec![
                vec!["Alice".to_string(), "alice@example.com".to_string(), "Active".to_string()],
                vec!["Bob".to_string(), "bob@example.com".to_string(), "Inactive".to_string()],
                vec!["Charlie".to_string(), "charlie@example.com".to_string(), "Active".to_string()],
            ],
        };

        // Step 2: Validate table
        assert!(A2UIValidator::validate(&component).is_ok());

        // Step 3: Render to HTML
        let html = Renderer::render(&component);

        // Step 4: Verify table structure
        assert!(html.contains("a2ui-table"));
        assert!(html.contains("<thead>"));
        assert!(html.contains("<tbody>"));
        assert!(html.contains("Name"));
        assert!(html.contains("Email"));
        assert!(html.contains("Status"));
        assert!(html.contains("Alice"));
        assert!(html.contains("alice@example.com"));
        assert!(html.contains("Bob"));
        assert!(html.contains("bob@example.com"));
        assert!(html.contains("Charlie"));
        assert!(html.contains("charlie@example.com"));
        assert!(html.contains("Active"));
        assert!(html.contains("Inactive"));
    }

    // ========== TEST 7: Async SSE Streaming Multiple Components ==========
    // test_e2e_sse_streaming_async: ensures SSE handler → serialize → transmit multiple components
    #[tokio::test]
    async fn test_e2e_sse_streaming_multiple_components() {
        // Step 1: Create multiple components (simulating agent streaming)
        let components = vec![
            A2UIComponent::Text {
                id: "stream_text_1".to_string(),
                content: "First message".to_string(),
                size: None,
            },
            A2UIComponent::Alert {
                id: "stream_alert".to_string(),
                message: "Processing...".to_string(),
                level: "info".to_string(),
            },
            A2UIComponent::Progress {
                id: "stream_progress".to_string(),
                value: 50,
                max: 100,
                label: Some("Upload".to_string()),
            },
        ];

        // Step 2: Convert each to SSE message
        let form_id = "streaming_form";
        let messages: Vec<SseComponentMessage> = components
            .iter()
            .map(|c| SseComponentMessage::from_component(c, form_id))
            .collect();

        // Step 3: Verify all messages serialized correctly
        for msg in &messages {
            let json = serde_json::to_string(msg).expect("Serialization failed");
            assert!(!json.is_empty());
            assert!(json.contains("stream_"));
        }

        // Step 4: Verify message count and timestamps
        assert_eq!(messages.len(), 3);
        for msg in &messages {
            assert!(!msg.timestamp.is_empty(), "Timestamp missing");
            assert_eq!(msg.form_id, form_id);
        }
    }

    // ========== TEST 8: Form Submission Roundtrip ==========
    // test_e2e_form_submission_roundtrip: ensures UI → FormHandler → response complete flow
    #[test]
    fn test_e2e_form_submission_roundtrip_complete() {
        // Step 1: Create complex form with multiple input types
        let form_components = vec![
            A2UIComponent::Input {
                id: "email_field".to_string(),
                label: "Email".to_string(),
                placeholder: Some("user@example.com".to_string()),
                required: true,
            },
            A2UIComponent::Select {
                id: "priority_select".to_string(),
                label: "Priority".to_string(),
                options: vec![
                    SelectOption {
                        value: "low".to_string(),
                        label: "Low".to_string(),
                    },
                    SelectOption {
                        value: "high".to_string(),
                        label: "High".to_string(),
                    },
                ],
            },
            A2UIComponent::Checkbox {
                id: "agree_checkbox".to_string(),
                label: "I agree to terms".to_string(),
                checked: false,
            },
            A2UIComponent::Button {
                id: "submit_btn".to_string(),
                label: "Submit".to_string(),
                action: Some("submit".to_string()),
            },
        ];

        // Step 2: Validate all form components
        for component in &form_components {
            assert!(A2UIValidator::validate(component).is_ok(), "Component validation failed");
        }

        // Step 3: Render all components to HTML
        let html_parts: Vec<String> = form_components
            .iter()
            .map(|c| Renderer::render(c))
            .collect();

        // Step 4: Verify all rendered
        assert_eq!(html_parts.len(), 4);
        for html in &html_parts {
            assert!(!html.is_empty());
        }

        // Step 5: Simulate user filling form and submitting
        let task_id = Uuid::new_v4();
        let form_submission = FormSubmission {
            task_id,
            form_id: "approval_form".to_string(),
            values: json!({
                "email_field": "user@example.com",
                "priority_select": "high",
                "agree_checkbox": true
            }),
        };

        // Step 6: Process through FormHandler
        let handler = FormHandler::new();
        let result = handler.process(&form_submission);

        // Step 7: Verify successful response
        assert!(result.is_ok(), "Form processing failed");
        let response = result.unwrap();
        assert_eq!(response.status, "accepted");
        assert!(!response.submission_id.is_empty());

        // Step 8: Verify submission can be reprocessed with different values
        let second_submission = FormSubmission {
            task_id: Uuid::new_v4(),
            form_id: "approval_form".to_string(),
            values: json!({
                "email_field": "admin@example.com",
                "priority_select": "low",
                "agree_checkbox": true
            }),
        };

        let second_result = handler.process(&second_submission);
        assert!(second_result.is_ok());
        let second_response = second_result.unwrap();
        assert_eq!(second_response.status, "accepted");
        assert_ne!(response.submission_id, second_response.submission_id, "Submission IDs should differ");
    }
}
