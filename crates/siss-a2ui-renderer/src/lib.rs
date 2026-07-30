use siss_agent_shell::a2ui::A2UIComponent;
use siss_agent_shell::a2ui_primitives::PrimitiveRegistry;
use siss_cockpit::a2ui::renderer::Renderer;
use uuid::Uuid;

/// Payload containing a list of A2UI components to validate and render
#[derive(Debug, Clone)]
pub struct A2UIPayload {
    pub id: Uuid,
    pub components: Vec<serde_json::Value>,
}

/// Errors that can occur during A2UI payload validation
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ValidationError {
    UnknownType(String),
    ParseError(String),
    EmptyPayload,
}

/// Validates A2UI payloads against the primitive registry
pub struct PayloadValidator;

impl PayloadValidator {
    /// Create a new PayloadValidator instance
    pub fn new() -> Self {
        PayloadValidator
    }

    /// Validate a payload and return parsed components or error
    pub fn validate(&self, payload: &A2UIPayload) -> Result<Vec<A2UIComponent>, ValidationError> {
        if payload.components.is_empty() {
            return Err(ValidationError::EmptyPayload);
        }

        let mut components = Vec::new();
        for json in &payload.components {
            let type_name = json.get("type").and_then(|v| v.as_str());
            if let Some(type_name) = type_name {
                if !PrimitiveRegistry::is_known(type_name) {
                    return Err(ValidationError::UnknownType(type_name.to_string()));
                }
            } else {
                return Err(ValidationError::UnknownType("missing type".to_string()));
            }

            let component = PrimitiveRegistry::try_parse(json)
                .map_err(|e| ValidationError::ParseError(format!("{:?}", e)))?;
            components.push(component);
        }

        Ok(components)
    }
}

impl Default for PayloadValidator {
    fn default() -> Self {
        Self::new()
    }
}

/// Renders A2UI components to HTML strings
pub struct PayloadRenderer;

impl PayloadRenderer {
    /// Create a new PayloadRenderer instance
    pub fn new() -> Self {
        PayloadRenderer
    }

    /// Render a list of A2UI components to HTML strings
    pub fn render_all(&self, components: Vec<A2UIComponent>) -> Vec<String> {
        components
            .into_iter()
            .map(|c| Renderer::render(&c))
            .collect()
    }
}

impl Default for PayloadRenderer {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Test that unknown component types are rejected with ValidationError::UnknownType
    #[test]
    fn test_unknown_component_rejected_by_validator() {
        let validator = PayloadValidator::new();
        let payload = A2UIPayload {
            id: Uuid::new_v4(),
            components: vec![serde_json::json!({
                "type": "unknown_type",
                "id": "test1"
            })],
        };
        let result = validator.validate(&payload);
        assert!(matches!(result, Err(ValidationError::UnknownType(_))));
    }

    /// Test that Checkbox components render to non-empty HTML strings
    #[test]
    fn test_checkbox_component_renders_to_html() {
        let renderer = PayloadRenderer::new();
        let component = A2UIComponent::Checkbox {
            id: "check1".to_string(),
            label: "Test Checkbox".to_string(),
            checked: false,
        };
        let html_strings = renderer.render_all(vec![component]);
        assert_eq!(html_strings.len(), 1);
        assert!(!html_strings[0].is_empty());
        assert!(html_strings[0].contains("checkbox"));
    }

    /// Test that empty component payloads are rejected with ValidationError::EmptyPayload
    #[test]
    fn test_empty_payload_rejected() {
        let validator = PayloadValidator::new();
        let payload = A2UIPayload {
            id: Uuid::new_v4(),
            components: vec![],
        };
        let result = validator.validate(&payload);
        assert!(matches!(result, Err(ValidationError::EmptyPayload)));
    }
}
