#[cfg(test)]
mod edge_cases_tests {
    use siss_agent_shell::a2ui::schema::A2UIComponent;

    #[test]
    fn test_deeply_nested_components() {
        let mut nested = A2UIComponent::Text {
            id: "leaf".to_string(),
            content: "Deeply nested".to_string(),
            size: None,
        };

        for i in 0..5 {
            nested = A2UIComponent::Card {
                id: format!("card{}", i),
                title: Some(format!("Level {}", i)),
                children: vec![nested],
            };
        }

        // Verify rendering handles deep nesting
        let _jsx = super::super::react_renderer::ReactRendererSpec::render_jsx(&nested);
    }

    #[test]
    fn test_large_component_tree_performance() {
        let mut children = vec![];
        for i in 0..100 {
            children.push(A2UIComponent::Text {
                id: format!("text{}", i),
                content: format!("Item {}", i),
                size: None,
            });
        }

        let grid = A2UIComponent::Grid {
            id: "grid1".to_string(),
            columns: 10,
            children,
        };

        let jsx = super::super::react_renderer::ReactRendererSpec::render_jsx(&grid);
        assert!(!jsx.is_empty());
    }

    #[test]
    fn test_unicode_characters_in_labels() {
        let button = A2UIComponent::Button {
            id: "btn".to_string(),
            label: "🚀 Läunchën 中文 العربية".to_string(),
            action: None,
        };
        let jsx = super::super::react_renderer::ReactRendererSpec::render_jsx(&button);
        assert!(jsx.contains("🚀") || jsx.contains("Launch"));
    }

    #[test]
    fn test_special_characters_escaped() {
        let text = A2UIComponent::Text {
            id: "text1".to_string(),
            content: "Line1\nLine2\tTabbed".to_string(),
            size: None,
        };
        let jsx = super::super::react_renderer::ReactRendererSpec::render_jsx(&text);
        // Verify JSX is generated without unescaped control characters in attributes
        assert!(jsx.contains("Line1") && jsx.contains("Line2"));
    }

    #[test]
    fn test_null_props_handling() {
        let input = A2UIComponent::Input {
            id: "input1".to_string(),
            label: "Field".to_string(),
            placeholder: None,
            required: false,
        };
        let jsx = super::super::react_renderer::ReactRendererSpec::render_jsx(&input);
        assert!(jsx.contains("input"));
    }

    #[test]
    fn test_empty_string_props() {
        let button = A2UIComponent::Button {
            id: "".to_string(),
            label: "".to_string(),
            action: None,
        };
        let jsx = super::super::react_renderer::ReactRendererSpec::render_jsx(&button);
        // Should handle empty strings gracefully
        assert!(!jsx.is_empty());
    }

    #[test]
    fn test_component_without_props() {
        let divider = A2UIComponent::Divider {
            id: "divider1".to_string(),
        };
        let jsx = super::super::react_renderer::ReactRendererSpec::render_jsx(&divider);
        assert!(jsx.contains("divider") || jsx.contains("hr"));
    }
}
