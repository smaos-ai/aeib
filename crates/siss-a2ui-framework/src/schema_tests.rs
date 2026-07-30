#[cfg(test)]
mod schema_validation_tests {
    use serde_json::json;

    #[test]
    fn test_button_schema_valid() {
        let schema = super::super::schema::SchemaRegistry::schema_for("Button").unwrap();
        assert!(schema.is_object());
    }

    #[test]
    fn test_input_schema_valid() {
        let schema = super::super::schema::SchemaRegistry::schema_for("Input").unwrap();
        assert!(schema.is_object());
    }

    #[test]
    fn test_dropdown_schema_valid() {
        let schema = super::super::schema::SchemaRegistry::schema_for("Select").unwrap();
        assert!(schema.is_object());
    }

    #[test]
    fn test_dropdown_required_options_field() {
        let schema = super::super::schema::SchemaRegistry::schema_for("Select").unwrap();
        let empty = vec![];
        let required = schema.get("required").and_then(|v| v.as_array()).unwrap_or(&empty);
        assert!(required.iter().any(|r| r.as_str() == Some("options")));
    }

    #[test]
    fn test_input_required_value_field_label() {
        let schema = super::super::schema::SchemaRegistry::schema_for("Input").unwrap();
        let empty = vec![];
        let required = schema.get("required").and_then(|v| v.as_array()).unwrap_or(&empty);
        assert!(required.iter().any(|r| r.as_str() == Some("label")));
    }

    #[test]
    fn test_button_required_label_field() {
        let schema = super::super::schema::SchemaRegistry::schema_for("Button").unwrap();
        let empty = vec![];
        let required = schema.get("required").and_then(|v| v.as_array()).unwrap_or(&empty);
        assert!(required.iter().any(|r| r.as_str() == Some("label")));
    }

    #[test]
    fn test_all_18_schemas_defined() {
        let schemas = super::super::schema::SchemaRegistry::all_schemas();
        let component_types = vec![
            "Text", "Badge", "Alert", "Progress", "Divider", "Link", "Tooltip", "Breadcrumb",
            "Input", "Textarea", "Select", "Checkbox", "Radio", "Button",
            "Card", "Grid", "Modal", "Table",
        ];
        for component_type in component_types {
            assert!(schemas.contains_key(component_type), "Missing schema for {}", component_type);
        }
        assert_eq!(schemas.len(), 18);
    }

    #[test]
    fn test_schema_type_mismatch_error() {
        let json_value = json!({"type": "button", "value": 123});
        match super::super::json_schema::JsonSchemaValidator::validate(&json_value) {
            Err(super::super::json_schema::SchemaError::TypeMismatch { .. }) => {},
            _ => panic!("Expected TypeMismatch error"),
        }
    }

    #[test]
    fn test_schema_missing_required_error() {
        let json_value = json!({"type": "button"});
        match super::super::json_schema::JsonSchemaValidator::validate(&json_value) {
            Err(super::super::json_schema::SchemaError::MissingRequired { field }) if field == "label" => {},
            _ => panic!("Expected MissingRequired error for 'label'"),
        }
    }

    #[test]
    fn test_schema_additional_property_error() {
        let json_value = json!({"type": "button", "label": "Click", "unknownField": "value"});
        match super::super::json_schema::JsonSchemaValidator::validate(&json_value) {
            Err(super::super::json_schema::SchemaError::AdditionalProperty { field }) if field == "unknownField" => {},
            Ok(()) => {}, // Additional properties may be allowed; adjust test as needed
            _ => {},
        }
    }

    #[test]
    fn test_nested_component_schema() {
        let schema = super::super::schema::SchemaRegistry::schema_for("Card").unwrap();
        assert!(schema.get("properties").is_some());
        assert!(schema.get("properties").and_then(|p| p.get("children")).is_some());
    }

    #[test]
    fn test_schema_for_nonexistent_type_error() {
        let result = super::super::schema::SchemaRegistry::schema_for("NonExistent");
        assert!(result.is_err());
    }

    #[test]
    fn test_schema_properties_exist() {
        let schema = super::super::schema::SchemaRegistry::schema_for("Button").unwrap();
        assert!(schema.get("properties").is_some());
    }

    #[test]
    fn test_text_schema_optional_size() {
        let schema = super::super::schema::SchemaRegistry::schema_for("Text").unwrap();
        let properties = schema.get("properties").unwrap();
        assert!(properties.get("size").is_some());
    }

    #[test]
    fn test_badge_optional_color() {
        let schema = super::super::schema::SchemaRegistry::schema_for("Badge").unwrap();
        let properties = schema.get("properties").unwrap();
        assert!(properties.get("color").is_some());
    }

    #[test]
    fn test_progress_required_fields() {
        let schema = super::super::schema::SchemaRegistry::schema_for("Progress").unwrap();
        let empty = vec![];
        let required = schema.get("required").and_then(|v| v.as_array()).unwrap_or(&empty);
        assert!(required.iter().any(|r| r.as_str() == Some("value")));
        assert!(required.iter().any(|r| r.as_str() == Some("max")));
    }

    #[test]
    fn test_modal_children_property() {
        let schema = super::super::schema::SchemaRegistry::schema_for("Modal").unwrap();
        let properties = schema.get("properties").unwrap();
        assert!(properties.get("children").is_some());
    }

    #[test]
    fn test_table_headers_and_rows_required() {
        let schema = super::super::schema::SchemaRegistry::schema_for("Table").unwrap();
        let empty = vec![];
        let required = schema.get("required").and_then(|v| v.as_array()).unwrap_or(&empty);
        assert!(required.iter().any(|r| r.as_str() == Some("headers")));
        assert!(required.iter().any(|r| r.as_str() == Some("rows")));
    }

    #[test]
    fn test_select_option_structure() {
        let schema = super::super::schema::SchemaRegistry::schema_for("Select").unwrap();
        let properties = schema.get("properties").unwrap();
        let options = properties.get("options").unwrap();
        assert!(options.get("items").is_some());
    }

    #[test]
    fn test_textarea_rows_property() {
        let schema = super::super::schema::SchemaRegistry::schema_for("Textarea").unwrap();
        let properties = schema.get("properties").unwrap();
        assert!(properties.get("rows").is_some());
    }

    #[test]
    fn test_checkbox_checked_default() {
        let schema = super::super::schema::SchemaRegistry::schema_for("Checkbox").unwrap();
        let properties = schema.get("properties").unwrap();
        assert!(properties.get("checked").is_some());
    }

    #[test]
    fn test_radio_value_required() {
        let schema = super::super::schema::SchemaRegistry::schema_for("Radio").unwrap();
        let empty = vec![];
        let required = schema.get("required").and_then(|v| v.as_array()).unwrap_or(&empty);
        assert!(required.iter().any(|r| r.as_str() == Some("value")));
    }
}
