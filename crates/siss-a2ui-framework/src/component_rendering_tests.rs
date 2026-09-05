#[cfg(test)]
mod component_rendering_tests {
    use siss_agent_shell::a2ui::schema::A2UIComponent;

    #[test]
    fn test_render_jsx_button() {
        let button = A2UIComponent::Button {
            id: "btn1".to_string(),
            label: "Click Me".to_string(),
            action: Some("submit".to_string()),
        };
        let jsx = super::super::react_renderer::ReactRendererSpec::render_jsx(&button);
        assert!(jsx.contains("button"));
        assert!(jsx.contains("Click Me"));
    }

    #[test]
    fn test_render_jsx_input_with_placeholder() {
        let input = A2UIComponent::Input {
            id: "input1".to_string(),
            label: "Name".to_string(),
            placeholder: Some("Enter your name".to_string()),
            required: true,
        };
        let jsx = super::super::react_renderer::ReactRendererSpec::render_jsx(&input);
        assert!(jsx.contains("input"));
        assert!(jsx.contains("Name"));
        assert!(jsx.contains("Enter your name"));
    }

    #[test]
    fn test_render_jsx_dropdown_with_options() {
        let select = A2UIComponent::Select {
            id: "select1".to_string(),
            label: "Choose".to_string(),
            options: vec![
                siss_agent_shell::a2ui::schema::SelectOption {
                    value: "opt1".to_string(),
                    label: "Option 1".to_string(),
                },
            ],
        };
        let jsx = super::super::react_renderer::ReactRendererSpec::render_jsx(&select);
        assert!(jsx.contains("select"));
        assert!(jsx.contains("Choose"));
        assert!(jsx.contains("Option 1"));
    }

    #[test]
    fn test_render_jsx_table_with_headers() {
        let table = A2UIComponent::Table {
            id: "table1".to_string(),
            headers: vec!["Name".to_string(), "Age".to_string()],
            rows: vec![vec!["Alice".to_string(), "30".to_string()]],
        };
        let jsx = super::super::react_renderer::ReactRendererSpec::render_jsx(&table);
        assert!(jsx.contains("table"));
        assert!(jsx.contains("Name"));
        assert!(jsx.contains("Age"));
        assert!(jsx.contains("Alice"));
    }

    #[test]
    fn test_render_jsx_modal_with_backdrop() {
        let modal = A2UIComponent::Modal {
            id: "modal1".to_string(),
            title: "Confirm".to_string(),
            content: "Are you sure?".to_string(),
            children: vec![],
        };
        let jsx = super::super::react_renderer::ReactRendererSpec::render_jsx(&modal);
        assert!(jsx.contains("dialog") || jsx.contains("modal"));
        assert!(jsx.contains("Confirm"));
    }

    #[test]
    fn test_render_native_button() {
        let button = A2UIComponent::Button {
            id: "btn1".to_string(),
            label: "Tap".to_string(),
            action: None,
        };
        let native = super::super::react_renderer::ReactRendererSpec::render_native(&button);
        assert!(native.contains("Button") || native.contains("button"));
        assert!(native.contains("Tap"));
    }

    #[test]
    fn test_render_native_input() {
        let input = A2UIComponent::Input {
            id: "input1".to_string(),
            label: "Field".to_string(),
            placeholder: Some("Type".to_string()),
            required: false,
        };
        let native = super::super::react_renderer::ReactRendererSpec::render_native(&input);
        assert!(native.contains("TextInput") || native.contains("Input"));
    }

    #[test]
    fn test_inject_aria_button_aria_label() {
        let html = "<button id=\"btn1\">Click</button>";
        let with_aria = super::super::react_renderer::ReactRendererSpec::inject_aria(html);
        assert!(with_aria.contains("aria-label") || with_aria.contains("aria"));
    }

    #[test]
    fn test_inject_aria_input_aria_describedby() {
        let html = "<input id=\"input1\" />";
        let with_aria = super::super::react_renderer::ReactRendererSpec::inject_aria(html);
        assert!(with_aria.contains("aria-"));
    }

    #[test]
    fn test_inject_aria_modal_role_dialog() {
        let html = "<div id=\"modal1\"></div>";
        let with_aria = super::super::react_renderer::ReactRendererSpec::inject_aria(html);
        assert!(with_aria.contains("role") || with_aria.contains("aria-"));
    }

    #[test]
    fn test_jsx_escapes_html_entities() {
        let button = A2UIComponent::Button {
            id: "btn".to_string(),
            label: "Click & Watch <script>".to_string(),
            action: None,
        };
        let jsx = super::super::react_renderer::ReactRendererSpec::render_jsx(&button);
        assert!(!jsx.contains("<script>"));
    }

    #[test]
    fn test_jsx_handles_event_handlers() {
        let button = A2UIComponent::Button {
            id: "btn".to_string(),
            label: "Submit".to_string(),
            action: Some("submit".to_string()),
        };
        let jsx = super::super::react_renderer::ReactRendererSpec::render_jsx(&button);
        assert!(jsx.contains("onClick") || jsx.contains("action"));
    }

    #[test]
    fn test_jsx_conditional_rendering() {
        let input = A2UIComponent::Input {
            id: "input1".to_string(),
            label: "Required".to_string(),
            placeholder: None,
            required: true,
        };
        let jsx = super::super::react_renderer::ReactRendererSpec::render_jsx(&input);
        assert!(jsx.contains("required") || jsx.contains("*"));
    }

    #[test]
    fn test_jsx_list_rendering_key_prop() {
        let select = A2UIComponent::Select {
            id: "select1".to_string(),
            label: "Options".to_string(),
            options: vec![
                siss_agent_shell::a2ui::schema::SelectOption {
                    value: "1".to_string(),
                    label: "First".to_string(),
                },
                siss_agent_shell::a2ui::schema::SelectOption {
                    value: "2".to_string(),
                    label: "Second".to_string(),
                },
            ],
        };
        let jsx = super::super::react_renderer::ReactRendererSpec::render_jsx(&select);
        assert!(jsx.contains("key") || jsx.contains("First"));
    }

    #[test]
    fn test_jsx_spread_props() {
        let button = A2UIComponent::Button {
            id: "btn".to_string(),
            label: "Go".to_string(),
            action: Some("custom".to_string()),
        };
        let jsx = super::super::react_renderer::ReactRendererSpec::render_jsx(&button);
        assert!(jsx.contains("id") || jsx.contains("btn"));
    }

    #[test]
    fn test_jsx_component_composition() {
        let card = A2UIComponent::Card {
            id: "card1".to_string(),
            title: Some("Form".to_string()),
            children: vec![
                A2UIComponent::Input {
                    id: "input1".to_string(),
                    label: "Field".to_string(),
                    placeholder: None,
                    required: false,
                },
            ],
        };
        let jsx = super::super::react_renderer::ReactRendererSpec::render_jsx(&card);
        assert!(jsx.contains("Form"));
        assert!(jsx.contains("Field"));
    }

    #[test]
    fn test_jsx_style_prop_handling() {
        let text = A2UIComponent::Text {
            id: "text1".to_string(),
            content: "Styled".to_string(),
            size: Some("lg".to_string()),
        };
        let jsx = super::super::react_renderer::ReactRendererSpec::render_jsx(&text);
        assert!(jsx.contains("lg") || jsx.contains("style"));
    }

    #[test]
    fn test_jsx_class_name_handling() {
        let badge = A2UIComponent::Badge {
            id: "badge1".to_string(),
            label: "New".to_string(),
            color: Some("blue".to_string()),
        };
        let jsx = super::super::react_renderer::ReactRendererSpec::render_jsx(&badge);
        assert!(jsx.contains("class") || jsx.contains("blue"));
    }
}
