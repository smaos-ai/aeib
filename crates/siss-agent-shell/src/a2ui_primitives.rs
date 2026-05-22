/// Phase 59: A2UI Primitives Registry — Fail-Closed Component Type Gate

use crate::a2ui::schema::A2UIComponent;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PrimitiveError {
    UnknownType(String),
    MalformedJson(String),
    ValidationFailed(String),
}

pub struct PrimitiveRegistry;

impl PrimitiveRegistry {
    /// RULE 1: Returns true iff type_name is one of the 18 known snake_case names.
    pub fn is_known(type_name: &str) -> bool {
        matches!(
            type_name,
            "text" | "badge" | "alert" | "progress" | "divider" | "link" | "tooltip"
                | "breadcrumb" | "input" | "textarea" | "select" | "checkbox" | "radio"
                | "button" | "card" | "grid" | "modal" | "table"
        )
    }

    /// RULE 2: Deserialize json → A2UIComponent; fail-closed.
    pub fn try_parse(json: &serde_json::Value) -> Result<A2UIComponent, PrimitiveError> {
        let component: A2UIComponent = serde_json::from_value(json.clone())
            .map_err(|e| PrimitiveError::MalformedJson(e.to_string()))?;

        crate::a2ui::validator::A2UIValidator::validate(&component)
            .map_err(|reason| PrimitiveError::ValidationFailed(reason))?;

        Ok(component)
    }

    /// RULE 3: For a batch of JSON values, silently drop any that fail try_parse.
    pub fn filter_batch(components: &[serde_json::Value]) -> Vec<A2UIComponent> {
        components
            .iter()
            .filter_map(|c| Self::try_parse(c).ok())
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_registry_knows_all_18_primitives() {
        let names = vec![
            "text", "badge", "alert", "progress", "divider", "link", "tooltip", "breadcrumb",
            "input", "textarea", "select", "checkbox", "radio", "button", "card", "grid",
            "modal", "table",
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
}
