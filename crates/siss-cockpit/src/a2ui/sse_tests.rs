/// Phase 32 Wave 2b: Cockpit SSE + Renderer Tests
/// TDD: Failing tests define expected behavior

#[cfg(test)]
mod sse_tests {
    use crate::a2ui::renderer::Renderer;
    use crate::a2ui::sse_handler::{A2UISseHandler, SseComponentMessage};
    use siss_agent_shell::a2ui::{A2UIComponent, SelectOption};

    // === SSE MESSAGE TESTS ===

    #[test]
    fn test_sse_message_serialization() {
        let component = A2UIComponent::Text {
            id: "test_text".to_string(),
            content: "Hello World".to_string(),
            size: Some("lg".to_string()),
        };

        let msg = SseComponentMessage::from_component(&component, "form_1");
        let json = serde_json::to_string(&msg).expect("serialization failed");

        assert!(json.contains("test_text"));
        assert!(json.contains("form_1"));
        assert!(json.contains("text"));
    }

    #[test]
    fn test_sse_message_deserialization() {
        let json = r#"{"component_id":"test","form_id":"form_1","rendered_html":"<div>test</div>","timestamp":"2026-05-29T00:00:00Z"}"#;
        let _msg: SseComponentMessage = serde_json::from_str(json).expect("deserialization failed");
    }

    // === RENDERER INTEGRATION TESTS ===

    #[test]
    fn test_renderer_text_component() {
        let component = A2UIComponent::Text {
            id: "text_1".to_string(),
            content: "Hello".to_string(),
            size: None,
        };

        let html = Renderer::render(&component);
        assert!(html.contains("Hello"));
        assert!(html.contains("a2ui-text"));
    }

    #[test]
    fn test_renderer_alert_component() {
        let component = A2UIComponent::Alert {
            id: "alert_1".to_string(),
            message: "Warning!".to_string(),
            level: "warn".to_string(),
        };

        let html = Renderer::render(&component);
        assert!(html.contains("Warning!"));
        assert!(html.contains("alert-warn"));
    }

    #[test]
    fn test_renderer_input_component() {
        let component = A2UIComponent::Input {
            id: "input_1".to_string(),
            label: "Name".to_string(),
            placeholder: Some("Enter name".to_string()),
            required: true,
        };

        let html = Renderer::render(&component);
        assert!(html.contains("Name"));
        assert!(html.contains("input_1"));
        assert!(html.contains("required"));
        assert!(html.contains("Enter name"));
    }

    #[test]
    fn test_renderer_select_component() {
        let component = A2UIComponent::Select {
            id: "select_1".to_string(),
            label: "Options".to_string(),
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

        let html = Renderer::render(&component);
        assert!(html.contains("opt1"));
        assert!(html.contains("opt2"));
        assert!(html.contains("Option 1"));
        assert!(html.contains("Option 2"));
    }

    #[test]
    fn test_renderer_button_component() {
        let component = A2UIComponent::Button {
            id: "btn_1".to_string(),
            label: "Submit".to_string(),
            action: Some("submit".to_string()),
        };

        let html = Renderer::render(&component);
        assert!(html.contains("Submit"));
        assert!(html.contains("submit"));
    }

    #[test]
    fn test_renderer_card_with_children() {
        let component = A2UIComponent::Card {
            id: "card_1".to_string(),
            title: Some("Card Title".to_string()),
            children: vec![A2UIComponent::Text {
                id: "text_1".to_string(),
                content: "Child content".to_string(),
                size: None,
            }],
        };

        let html = Renderer::render(&component);
        assert!(html.contains("Card Title"));
        assert!(html.contains("Child content"));
    }

    #[test]
    fn test_renderer_modal_component() {
        let component = A2UIComponent::Modal {
            id: "modal_1".to_string(),
            title: "Dialog".to_string(),
            content: "Modal content".to_string(),
            children: vec![],
        };

        let html = Renderer::render(&component);
        assert!(html.contains("Dialog"));
        assert!(html.contains("Modal content"));
    }

    #[test]
    fn test_renderer_table_component() {
        let component = A2UIComponent::Table {
            id: "table_1".to_string(),
            headers: vec!["Name".to_string(), "Age".to_string()],
            rows: vec![
                vec!["Alice".to_string(), "30".to_string()],
                vec!["Bob".to_string(), "25".to_string()],
            ],
        };

        let html = Renderer::render(&component);
        assert!(html.contains("Name"));
        assert!(html.contains("Age"));
        assert!(html.contains("Alice"));
        assert!(html.contains("Bob"));
    }

    #[test]
    fn test_renderer_xss_protection() {
        let component = A2UIComponent::Text {
            id: "xss_test".to_string(),
            content: "<script>alert('xss')</script>".to_string(),
            size: None,
        };

        let html = Renderer::render(&component);
        assert!(!html.contains("<script>"));
        assert!(html.contains("&lt;script&gt;"));
    }

    // === A2UI SSE HANDLER TESTS ===

    #[test]
    fn test_a2ui_sse_handler_creation() {
        let handler = A2UISseHandler::new();
        assert!(!handler.is_streaming());
    }

    #[test]
    fn test_a2ui_sse_handler_start_streaming() {
        let handler = A2UISseHandler::new();
        handler.start_streaming("agent_1");
        assert!(handler.is_streaming());
    }

    #[test]
    fn test_a2ui_sse_handler_stop_streaming() {
        let handler = A2UISseHandler::new();
        handler.start_streaming("agent_1");
        handler.stop_streaming();
        assert!(!handler.is_streaming());
    }

    #[test]
    fn test_a2ui_sse_handler_component_rendering() {
        let handler = A2UISseHandler::new();
        let component = A2UIComponent::Badge {
            id: "badge_1".to_string(),
            label: "Active".to_string(),
            color: Some("blue".to_string()),
        };

        let msg = handler.render_component(&component, "form_1");
        assert!(msg.rendered_html.contains("Active"));
        assert!(msg.form_id == "form_1");
    }

    #[test]
    fn test_a2ui_sse_multiple_components() {
        let handler = A2UISseHandler::new();
        let components = vec![
            A2UIComponent::Text {
                id: "text_1".to_string(),
                content: "Item 1".to_string(),
                size: None,
            },
            A2UIComponent::Text {
                id: "text_2".to_string(),
                content: "Item 2".to_string(),
                size: None,
            },
        ];

        for component in components {
            let msg = handler.render_component(&component, "form_1");
            assert!(!msg.rendered_html.is_empty());
        }
    }

    #[test]
    fn test_a2ui_sse_handler_timestamp() {
        let handler = A2UISseHandler::new();
        let component = A2UIComponent::Text {
            id: "text_1".to_string(),
            content: "test".to_string(),
            size: None,
        };

        let msg = handler.render_component(&component, "form_1");
        assert!(!msg.timestamp.is_empty());
    }
}
