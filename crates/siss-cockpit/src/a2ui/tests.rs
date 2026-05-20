#[cfg(test)]
mod tests {
    use siss_agent_shell::a2ui::{A2UIComponent, SelectOption, RadioOption};
    use crate::a2ui::renderer::Renderer;

    #[test]
    fn test_render_text_sm() {
        let component = A2UIComponent::Text {
            content: "Hello World".to_string(),
            size: "sm".to_string(),
        };
        let html = Renderer::render(&component);
        assert!(html.contains("Hello World"));
        assert!(html.contains("sm"));
    }

    #[test]
    fn test_render_text_default_size() {
        let component = A2UIComponent::Text {
            content: "Default Size".to_string(),
            size: String::new(),
        };
        let html = Renderer::render(&component);
        assert!(html.contains("Default Size"));
    }

    #[test]
    fn test_render_badge_blue() {
        let component = A2UIComponent::Badge {
            label: "Active".to_string(),
            color: "blue".to_string(),
        };
        let html = Renderer::render(&component);
        assert!(html.contains("Active"));
        assert!(html.contains("blue"));
    }

    #[test]
    fn test_render_badge_default_color() {
        let component = A2UIComponent::Badge {
            label: "Status".to_string(),
            color: String::new(),
        };
        let html = Renderer::render(&component);
        assert!(html.contains("Status"));
    }

    #[test]
    fn test_render_alert_info() {
        let component = A2UIComponent::Alert {
            message: "Information message".to_string(),
            level: "info".to_string(),
        };
        let html = Renderer::render(&component);
        assert!(html.contains("Information message"));
        assert!(html.contains("info"));
    }

    #[test]
    fn test_render_alert_error() {
        let component = A2UIComponent::Alert {
            message: "Error occurred".to_string(),
            level: "error".to_string(),
        };
        let html = Renderer::render(&component);
        assert!(html.contains("Error occurred"));
        assert!(html.contains("error"));
    }

    #[test]
    fn test_render_progress_half() {
        let component = A2UIComponent::Progress {
            value: 50,
            max: 100,
            label: None,
        };
        let html = Renderer::render(&component);
        assert!(html.contains("50"));
        assert!(html.contains("100"));
    }

    #[test]
    fn test_render_progress_with_label() {
        let component = A2UIComponent::Progress {
            value: 75,
            max: 100,
            label: Some("Upload".to_string()),
        };
        let html = Renderer::render(&component);
        assert!(html.contains("75"));
        assert!(html.contains("Upload"));
    }

    #[test]
    fn test_render_divider() {
        let component = A2UIComponent::Divider;
        let html = Renderer::render(&component);
        assert!(!html.is_empty());
    }

    #[test]
    fn test_render_link() {
        let component = A2UIComponent::Link {
            text: "Click here".to_string(),
            href: "https://example.com".to_string(),
        };
        let html = Renderer::render(&component);
        assert!(html.contains("Click here"));
        assert!(html.contains("https://example.com"));
    }

    #[test]
    fn test_render_tooltip() {
        let component = A2UIComponent::Tooltip {
            text: "Hover me".to_string(),
            content: "Tooltip content".to_string(),
        };
        let html = Renderer::render(&component);
        assert!(html.contains("Hover me"));
        assert!(html.contains("Tooltip content"));
    }

    #[test]
    fn test_render_breadcrumb() {
        let component = A2UIComponent::Breadcrumb {
            items: vec!["Home".to_string(), "Products".to_string(), "Item".to_string()],
        };
        let html = Renderer::render(&component);
        assert!(html.contains("Home"));
        assert!(html.contains("Products"));
        assert!(html.contains("Item"));
    }

    #[test]
    fn test_render_input_required() {
        let component = A2UIComponent::Input {
            id: "email".to_string(),
            label: "Email Address".to_string(),
            placeholder: "user@example.com".to_string(),
            required: true,
        };
        let html = Renderer::render(&component);
        assert!(html.contains("email"));
        assert!(html.contains("Email Address"));
        assert!(html.contains("user@example.com"));
        assert!(html.contains("required"));
    }

    #[test]
    fn test_render_input_optional() {
        let component = A2UIComponent::Input {
            id: "phone".to_string(),
            label: "Phone".to_string(),
            placeholder: String::new(),
            required: false,
        };
        let html = Renderer::render(&component);
        assert!(html.contains("phone"));
        assert!(html.contains("Phone"));
    }

    #[test]
    fn test_render_textarea() {
        let component = A2UIComponent::Textarea {
            id: "message".to_string(),
            label: "Message".to_string(),
            rows: 5,
        };
        let html = Renderer::render(&component);
        assert!(html.contains("message"));
        assert!(html.contains("Message"));
        assert!(html.contains("5"));
    }

    #[test]
    fn test_render_select() {
        let component = A2UIComponent::Select {
            id: "country".to_string(),
            label: "Select Country".to_string(),
            options: vec![
                SelectOption { value: "us".to_string(), label: "United States".to_string() },
                SelectOption { value: "uk".to_string(), label: "United Kingdom".to_string() },
            ],
        };
        let html = Renderer::render(&component);
        assert!(html.contains("country"));
        assert!(html.contains("Select Country"));
        assert!(html.contains("us"));
        assert!(html.contains("United States"));
        assert!(html.contains("uk"));
    }

    #[test]
    fn test_render_checkbox() {
        let component = A2UIComponent::Checkbox {
            id: "agree".to_string(),
            label: "I agree".to_string(),
        };
        let html = Renderer::render(&component);
        assert!(html.contains("agree"));
        assert!(html.contains("I agree"));
    }

    #[test]
    fn test_render_radio() {
        let component = A2UIComponent::Radio {
            id: "priority".to_string(),
            label: "Priority".to_string(),
            options: vec![
                RadioOption { value: "high".to_string(), label: "High".to_string() },
                RadioOption { value: "low".to_string(), label: "Low".to_string() },
            ],
        };
        let html = Renderer::render(&component);
        assert!(html.contains("priority"));
        assert!(html.contains("Priority"));
        assert!(html.contains("high"));
        assert!(html.contains("low"));
    }

    #[test]
    fn test_render_button_submit() {
        let component = A2UIComponent::Button {
            id: "submit_btn".to_string(),
            label: "Submit".to_string(),
            action: "submit".to_string(),
        };
        let html = Renderer::render(&component);
        assert!(html.contains("submit_btn"));
        assert!(html.contains("Submit"));
    }

    #[test]
    fn test_render_card_with_children() {
        let component = A2UIComponent::Card {
            title: "Card Title".to_string(),
            children: vec![
                A2UIComponent::Text {
                    content: "Card content".to_string(),
                    size: String::new(),
                },
            ],
        };
        let html = Renderer::render(&component);
        assert!(html.contains("Card Title"));
        assert!(html.contains("Card content"));
    }

    #[test]
    fn test_render_card_empty() {
        let component = A2UIComponent::Card {
            title: "Empty Card".to_string(),
            children: vec![],
        };
        let html = Renderer::render(&component);
        assert!(html.contains("Empty Card"));
    }

    #[test]
    fn test_render_grid_two_columns() {
        let component = A2UIComponent::Grid {
            columns: 2,
            children: vec![
                A2UIComponent::Text { content: "Item 1".to_string(), size: String::new() },
                A2UIComponent::Text { content: "Item 2".to_string(), size: String::new() },
            ],
        };
        let html = Renderer::render(&component);
        assert!(html.contains("2"));
        assert!(html.contains("Item 1"));
        assert!(html.contains("Item 2"));
    }

    #[test]
    fn test_render_modal() {
        let component = A2UIComponent::Modal {
            id: "modal_1".to_string(),
            title: "Confirm Action".to_string(),
            children: vec![
                A2UIComponent::Text { content: "Are you sure?".to_string(), size: String::new() },
            ],
        };
        let html = Renderer::render(&component);
        assert!(html.contains("modal_1"));
        assert!(html.contains("Confirm Action"));
        assert!(html.contains("Are you sure?"));
    }

    #[test]
    fn test_render_table() {
        let component = A2UIComponent::Table {
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
        assert!(html.contains("30"));
        assert!(html.contains("Bob"));
    }

    #[test]
    fn test_render_nested_components() {
        let component = A2UIComponent::Card {
            title: "Nested".to_string(),
            children: vec![
                A2UIComponent::Input {
                    id: "field1".to_string(),
                    label: "Field 1".to_string(),
                    placeholder: String::new(),
                    required: false,
                },
                A2UIComponent::Button {
                    id: "btn".to_string(),
                    label: "Submit".to_string(),
                    action: "submit".to_string(),
                },
            ],
        };
        let html = Renderer::render(&component);
        assert!(html.contains("Nested"));
        assert!(html.contains("Field 1"));
        assert!(html.contains("Submit"));
    }

    #[test]
    fn test_html_safety_xss_prevention() {
        let component = A2UIComponent::Text {
            content: "<script>alert('xss')</script>".to_string(),
            size: String::new(),
        };
        let html = Renderer::render(&component);
        // Ensure script tags are escaped
        assert!(!html.contains("<script>"));
        // Should contain escaped version
        assert!(html.contains("&lt;") || html.contains("script"));
    }

    #[test]
    fn test_render_all_18_primitives() {
        // Ensure each of the 18 primitives renders without panic
        let primitives = vec![
            A2UIComponent::Text { content: "text".to_string(), size: String::new() },
            A2UIComponent::Badge { label: "badge".to_string(), color: String::new() },
            A2UIComponent::Alert { message: "alert".to_string(), level: String::new() },
            A2UIComponent::Progress { value: 50, max: 100, label: None },
            A2UIComponent::Divider,
            A2UIComponent::Link { text: "link".to_string(), href: "http://example.com".to_string() },
            A2UIComponent::Tooltip { text: "tooltip".to_string(), content: "content".to_string() },
            A2UIComponent::Breadcrumb { items: vec!["home".to_string()] },
            A2UIComponent::Input { id: "input".to_string(), label: "input".to_string(), placeholder: String::new(), required: false },
            A2UIComponent::Textarea { id: "textarea".to_string(), label: "textarea".to_string(), rows: 5 },
            A2UIComponent::Select { id: "select".to_string(), label: "select".to_string(), options: vec![] },
            A2UIComponent::Checkbox { id: "checkbox".to_string(), label: "checkbox".to_string() },
            A2UIComponent::Radio { id: "radio".to_string(), label: "radio".to_string(), options: vec![] },
            A2UIComponent::Button { id: "button".to_string(), label: "button".to_string(), action: String::new() },
            A2UIComponent::Card { title: "card".to_string(), children: vec![] },
            A2UIComponent::Grid { columns: 1, children: vec![] },
            A2UIComponent::Modal { id: "modal".to_string(), title: "modal".to_string(), children: vec![] },
            A2UIComponent::Table { headers: vec![], rows: vec![] },
        ];

        for component in primitives {
            let html = Renderer::render(&component);
            assert!(!html.is_empty(), "Primitive should render to non-empty HTML");
        }
    }
}
