/// Phase 32: A2UI Payload Generation
/// RED phase: Failing tests for A2UI schema enforcement (18 safe components)
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};

/// The 18 safe A2UI component primitives
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum A2UIComponent {
    Card,
    TextField,
    TextArea,
    DateTimeInput,
    NumberInput,
    Select,
    MultiSelect,
    Checkbox,
    RadioGroup,
    Button,
    Link,
    Progress,
    Badge,
    Alert,
    Modal,
    Tabs,
    List,
    Grid,
}

impl A2UIComponent {
    /// Validate component type — fail-closed: reject unknown components
    pub fn from_string(s: &str) -> Result<Self, PayloadError> {
        match s {
            "card" => Ok(A2UIComponent::Card),
            "text_field" => Ok(A2UIComponent::TextField),
            "text_area" => Ok(A2UIComponent::TextArea),
            "date_time_input" => Ok(A2UIComponent::DateTimeInput),
            "number_input" => Ok(A2UIComponent::NumberInput),
            "select" => Ok(A2UIComponent::Select),
            "multi_select" => Ok(A2UIComponent::MultiSelect),
            "checkbox" => Ok(A2UIComponent::Checkbox),
            "radio_group" => Ok(A2UIComponent::RadioGroup),
            "button" => Ok(A2UIComponent::Button),
            "link" => Ok(A2UIComponent::Link),
            "progress" => Ok(A2UIComponent::Progress),
            "badge" => Ok(A2UIComponent::Badge),
            "alert" => Ok(A2UIComponent::Alert),
            "modal" => Ok(A2UIComponent::Modal),
            "tabs" => Ok(A2UIComponent::Tabs),
            "list" => Ok(A2UIComponent::List),
            "grid" => Ok(A2UIComponent::Grid),
            _ => Err(PayloadError::UnknownComponent), // Fail-closed: reject unknown
        }
    }

    /// Get list of all 18 safe components
    pub fn all_safe_components() -> Vec<&'static str> {
        vec![
            "card",
            "text_field",
            "text_area",
            "date_time_input",
            "number_input",
            "select",
            "multi_select",
            "checkbox",
            "radio_group",
            "button",
            "link",
            "progress",
            "badge",
            "alert",
            "modal",
            "tabs",
            "list",
            "grid",
        ]
    }
}

/// A2UI Payload — Declarative UI structure (decoupled from data)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct A2UIPayload {
    pub component_type: String,
    pub layout: serde_json::Value, // UI structure (no data binding)
    pub data_binding: serde_json::Value, // Data payload (separate from layout)
}

impl A2UIPayload {
    /// Generate A2UI payload from execution state
    pub fn from_execution_state(state: &str) -> Result<Self, PayloadError> {
        let parsed: serde_json::Value =
            serde_json::from_str(state).map_err(|_| PayloadError::MalformedPayload)?;

        // Map execution state to A2UI card component
        let layout = json!({
            "type": "card",
            "title": parsed.get("goal").and_then(|v| v.as_str()).unwrap_or("Execution State"),
            "fields": [
                { "type": "text_field", "label": "Skill Name" },
                { "type": "number_input", "label": "Depth" },
                { "type": "progress", "label": "Tokens Consumed" }
            ]
        });

        let data_binding = json!({
            "skillName": "$.name",
            "depth": "$.depth",
            "tokensConsumed": "$.tokens_consumed"
        });

        Ok(A2UIPayload {
            component_type: "card".to_string(),
            layout,
            data_binding,
        })
    }

    /// Validate payload schema: layout and data must be decoupled
    pub fn validate(&self) -> Result<(), PayloadError> {
        // Verify component type is one of 18 safe components
        A2UIComponent::from_string(&self.component_type)?;

        // Check that layout doesn't contain data values (fail-closed)
        if let Some(layout_obj) = self.layout.as_object() {
            for key in layout_obj.keys() {
                // Flag suspicious field names that might contain data
                if matches!(
                    key.as_str(),
                    "username"
                        | "email"
                        | "password"
                        | "token"
                        | "api_key"
                        | "secret"
                        | "name"
                        | "id"
                        | "value"
                        | "data"
                ) {
                    return Err(PayloadError::DataLayoutCoupling);
                }
            }
        }

        Ok(())
    }
}

#[derive(Debug, Clone)]
pub enum PayloadError {
    UnknownComponent,
    MalformedPayload,
    DataLayoutCoupling,
    InvalidState,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_a2ui_component_limit_18_primitives() {
        // GIVEN A2UI component enum
        // WHEN all safe components listed
        // THEN exactly 18 primitives exist
        // AND no hallucinated components present

        let safe = A2UIComponent::all_safe_components();
        assert_eq!(
            safe.len(),
            18,
            "A2UI must support exactly 18 safe components"
        );
    }

    #[test]
    fn test_a2ui_component_validation_rejects_unknown() {
        // GIVEN unknown component type "HallucinatedComponent"
        // WHEN validated
        // THEN returns PayloadError::UnknownComponent
        // AND execution rejected (fail-closed)

        let result = A2UIComponent::from_string("hallucinated_component");
        assert!(result.is_err(), "Unknown components must be rejected");
    }

    #[test]
    fn test_a2ui_component_validation_accepts_all_18_safe() {
        // GIVEN each of the 18 safe components
        // WHEN validated individually
        // THEN all pass validation
        // AND no safe component is rejected

        let safe_components = A2UIComponent::all_safe_components();

        for component_name in safe_components {
            let result = A2UIComponent::from_string(component_name);
            assert!(
                result.is_ok(),
                "Safe component {} should validate",
                component_name
            );
        }
    }

    #[test]
    fn test_a2ui_payload_structure_decoupled_from_data() {
        // GIVEN A2UI payload with separate layout and data_binding
        // WHEN schema validated
        // THEN layout (UI structure) and data_binding (values) are independent
        // AND coupling is rejected (fail-closed)

        let payload = A2UIPayload {
            component_type: "card".to_string(),
            layout: json!({
                "type": "card",
                "title": "User Profile",
                "fields": [
                    { "type": "text_field", "placeholder": "Name" },
                    { "type": "date_time_input", "label": "Birth Date" }
                ]
            }),
            data_binding: json!({
                "name": "$.user.name",
                "birthDate": "$.user.dob"
            }),
        };

        let result = payload.validate();
        assert!(result.is_ok(), "Decoupled payload should validate");
    }

    #[test]
    fn test_a2ui_payload_generation_from_skill_execution_state() {
        // GIVEN SkillPayload execution state (name, goal, depth, tokens_consumed)
        // WHEN generating A2UI payload
        // THEN maps execution state to valid A2UI component tree
        // AND respects 18-component limit

        let execution_state = r#"{
            "name": "data-extraction",
            "goal": "Extract structured data",
            "depth": 2,
            "tokens_consumed": 150
        }"#;

        let result = A2UIPayload::from_execution_state(execution_state);
        assert!(
            result.is_ok(),
            "Execution state should generate valid A2UI payload"
        );
    }

    #[test]
    fn test_a2ui_payload_rejects_data_in_layout_field() {
        // GIVEN A2UI payload where data values are embedded in layout
        // WHEN validated
        // THEN returns PayloadError::DataLayoutCoupling
        // AND rejects tight coupling (fail-closed)

        let invalid_payload = A2UIPayload {
            component_type: "card".to_string(),
            layout: json!({
                "type": "card",
                "username": "alice",  // Data in layout! (should be in data_binding)
                "email": "alice@example.com"
            }),
            data_binding: json!({}),
        };

        let result = invalid_payload.validate();
        assert!(result.is_err(), "Layout containing data must be rejected");
    }
}
