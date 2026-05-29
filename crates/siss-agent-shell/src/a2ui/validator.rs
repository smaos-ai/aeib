use crate::a2ui::schema::A2UIComponent;
use regex::Regex;
use std::collections::HashMap;

pub struct A2UIValidator;

impl A2UIValidator {
    /// Validate A2UIComponent against 18-primitive schema (fail-closed)
    pub fn validate(component: &A2UIComponent) -> Result<(), String> {
        match component {
            // Display components
            A2UIComponent::Text { id, content, .. } => {
                Self::validate_id(id)?;
                if content.is_empty() {
                    return Err("Text content must not be empty".to_string());
                }
                Ok(())
            }
            A2UIComponent::Badge { id, label, .. } => {
                Self::validate_id(id)?;
                if label.is_empty() {
                    return Err("Badge label must not be empty".to_string());
                }
                Ok(())
            }
            A2UIComponent::Alert { id, message, .. } => {
                Self::validate_id(id)?;
                if message.is_empty() {
                    return Err("Alert message must not be empty".to_string());
                }
                Ok(())
            }
            A2UIComponent::Progress { id, value, max, .. } => {
                Self::validate_id(id)?;
                if value > max {
                    return Err("Progress value cannot exceed max".to_string());
                }
                Ok(())
            }
            A2UIComponent::Divider { id } => {
                Self::validate_id(id)?;
                Ok(())
            }
            A2UIComponent::Link { id, label, href } => {
                Self::validate_id(id)?;
                if label.is_empty() {
                    return Err("Link label must not be empty".to_string());
                }
                if href.is_empty() {
                    return Err("Link href must not be empty".to_string());
                }
                Ok(())
            }
            A2UIComponent::Tooltip { id, text, content } => {
                Self::validate_id(id)?;
                if text.is_empty() {
                    return Err("Tooltip text must not be empty".to_string());
                }
                if content.is_empty() {
                    return Err("Tooltip content must not be empty".to_string());
                }
                Ok(())
            }
            A2UIComponent::Breadcrumb { id, .. } => {
                Self::validate_id(id)?;
                Ok(())
            }
            // Form components
            A2UIComponent::Input { id, label, .. } => {
                Self::validate_id(id)?;
                if label.is_empty() {
                    return Err("Input label must not be empty".to_string());
                }
                Ok(())
            }
            A2UIComponent::Textarea { id, label, .. } => {
                Self::validate_id(id)?;
                if label.is_empty() {
                    return Err("Textarea label must not be empty".to_string());
                }
                Ok(())
            }
            A2UIComponent::Select { id, label, .. } => {
                Self::validate_id(id)?;
                if label.is_empty() {
                    return Err("Select label must not be empty".to_string());
                }
                Ok(())
            }
            A2UIComponent::Checkbox { id, label, .. } => {
                Self::validate_id(id)?;
                if label.is_empty() {
                    return Err("Checkbox label must not be empty".to_string());
                }
                Ok(())
            }
            A2UIComponent::Radio { id, label, value, .. } => {
                Self::validate_id(id)?;
                if label.is_empty() {
                    return Err("Radio label must not be empty".to_string());
                }
                if value.is_empty() {
                    return Err("Radio value must not be empty".to_string());
                }
                Ok(())
            }
            A2UIComponent::Button { id, label, .. } => {
                Self::validate_id(id)?;
                if label.is_empty() {
                    return Err("Button label must not be empty".to_string());
                }
                Ok(())
            }
            // Layout components
            A2UIComponent::Card { id, children, .. } => {
                Self::validate_id(id)?;
                for child in children {
                    Self::validate(child)?;
                }
                Ok(())
            }
            A2UIComponent::Grid { id, children, .. } => {
                Self::validate_id(id)?;
                for child in children {
                    Self::validate(child)?;
                }
                Ok(())
            }
            A2UIComponent::Modal { id, title, content, children } => {
                Self::validate_id(id)?;
                if title.is_empty() {
                    return Err("Modal title must not be empty".to_string());
                }
                if content.is_empty() {
                    return Err("Modal content must not be empty".to_string());
                }
                for child in children {
                    Self::validate(child)?;
                }
                Ok(())
            }
            A2UIComponent::Table { id, .. } => {
                Self::validate_id(id)?;
                Ok(())
            }
        }
    }

    fn validate_id(id: &str) -> Result<(), String> {
        if id.is_empty() {
            Err("Component ID must not be empty".to_string())
        } else {
            Ok(())
        }
    }

    // === CONTEXT-AWARE VALIDATION (Wave 2) ===

    /// Validate form state against required fields
    pub fn validate_form_state(
        form_state: &[(String, serde_json::Value)],
        required_fields: &[(String, bool)],
    ) -> Result<(), String> {
        let state_map: HashMap<String, serde_json::Value> = form_state
            .iter()
            .map(|(k, v)| (k.clone(), v.clone()))
            .collect();

        for (field_name, is_required) in required_fields {
            if *is_required {
                let value = state_map
                    .get(field_name)
                    .ok_or_else(|| format!("Required field '{}' is missing", field_name))?;

                // Check if value is empty (string, null, or empty array)
                match value {
                    serde_json::Value::String(s) if s.is_empty() => {
                        return Err(format!("Required field '{}' cannot be empty", field_name));
                    }
                    serde_json::Value::Null => {
                        return Err(format!("Required field '{}' is null", field_name));
                    }
                    serde_json::Value::Array(a) if a.is_empty() => {
                        return Err(format!("Required field '{}' is empty", field_name));
                    }
                    _ => {}
                }
            }
        }

        Ok(())
    }

    /// Validate cross-field dependency: when condition_field has condition_value,
    /// dependent_field must not be empty
    pub fn validate_cross_field_dependency(
        condition_field: &str,
        condition_value: bool,
        dependent_field: &str,
        form_state: &[(String, serde_json::Value)],
    ) -> Result<(), String> {
        let state_map: HashMap<String, serde_json::Value> = form_state
            .iter()
            .map(|(k, v)| (k.clone(), v.clone()))
            .collect();

        // Check condition field
        let cond = state_map
            .get(condition_field)
            .and_then(|v| v.as_bool())
            .unwrap_or(false);

        // If condition is met, dependent field must not be empty
        if cond == condition_value {
            let dep_value = state_map.get(dependent_field);
            match dep_value {
                None => {
                    return Err(format!(
                        "Field '{}' is required when '{}' is {}",
                        dependent_field, condition_field, condition_value
                    ));
                }
                Some(serde_json::Value::String(s)) if s.is_empty() => {
                    return Err(format!(
                        "Field '{}' cannot be empty when '{}' is {}",
                        dependent_field, condition_field, condition_value
                    ));
                }
                _ => {}
            }
        }

        Ok(())
    }

    /// Validate mutually exclusive fields: exactly one must have a non-empty value
    pub fn validate_mutually_exclusive(
        fields: &[String],
        form_state: &[(String, serde_json::Value)],
    ) -> Result<(), String> {
        let state_map: HashMap<String, serde_json::Value> = form_state
            .iter()
            .map(|(k, v)| (k.clone(), v.clone()))
            .collect();

        let non_empty_count = fields
            .iter()
            .filter(|field| {
                if let Some(value) = state_map.get(*field) {
                    match value {
                        serde_json::Value::String(s) => !s.is_empty(),
                        serde_json::Value::Null => false,
                        _ => true,
                    }
                } else {
                    false
                }
            })
            .count();

        if non_empty_count != 1 {
            return Err(format!(
                "Fields are mutually exclusive: exactly one of {:?} must be provided (found {})",
                fields, non_empty_count
            ));
        }

        Ok(())
    }

    /// Validate field format (email, phone, url)
    pub fn validate_field_format(
        field_name: &str,
        value: &str,
        format_type: &str,
    ) -> Result<(), String> {
        if value.is_empty() {
            return Ok(()); // Empty values are validated separately
        }

        let pattern = match format_type {
            "email" => r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
            "phone" => r"^\+?[0-9\-\(\)\s]{7,}$", // Flexible: +1-555-123-4567, (555) 123-4567, etc. Min 7 chars
            "url" => r"^https?://[^\s/$.?#].[^\s]*$",
            _ => return Err(format!("Unknown format type: {}", format_type)),
        };

        let re = Regex::new(pattern)
            .map_err(|_| format!("Invalid regex pattern for format: {}", format_type))?;

        if !re.is_match(value) {
            return Err(format!(
                "Field '{}' does not match format '{}'",
                field_name, format_type
            ));
        }

        Ok(())
    }

    /// Validate field length constraints
    pub fn validate_field_length(
        field_name: &str,
        min_len: usize,
        max_len: usize,
        value: &str,
    ) -> Result<(), String> {
        let len = value.len();

        if len < min_len {
            return Err(format!(
                "Field '{}' must be at least {} characters (got {})",
                field_name, min_len, len
            ));
        }

        if len > max_len {
            return Err(format!(
                "Field '{}' must not exceed {} characters (got {})",
                field_name, max_len, len
            ));
        }

        Ok(())
    }

    /// Check form state completeness (all required fields are present)
    pub fn check_form_completeness(
        form_state: &[(String, serde_json::Value)],
        required_fields: &[String],
    ) -> Result<(), String> {
        let state_keys: std::collections::HashSet<_> =
            form_state.iter().map(|(k, _)| k.clone()).collect();

        for required in required_fields {
            if !state_keys.contains(required) {
                return Err(format!("Missing required field: '{}'", required));
            }
        }

        Ok(())
    }

    /// Validate modal context: modal with content should have action buttons
    pub fn validate_modal_context(modal: &A2UIComponent) -> Result<(), String> {
        if let A2UIComponent::Modal {
            id: _,
            title: _,
            content,
            children,
        } = modal
        {
            // If there's substantial content, there should be buttons for action
            if !content.is_empty() && content.len() > 5 {
                let has_button = children.iter().any(|child| matches!(child, A2UIComponent::Button { .. }));
                if !has_button {
                    return Err("Modal with content must have at least one action button".to_string());
                }
            }
            Ok(())
        } else {
            Err("Not a modal component".to_string())
        }
    }

    /// Validate select context: select with label should have options
    pub fn validate_select_context(select: &A2UIComponent) -> Result<(), String> {
        if let A2UIComponent::Select {
            id: _,
            label: _,
            options,
        } = select
        {
            if options.is_empty() {
                return Err("Select component must have at least one option".to_string());
            }
            Ok(())
        } else {
            Err("Not a select component".to_string())
        }
    }

    /// Validate form submission against schema
    /// Schema format: Vec<(field_name, (field_type, is_required))>
    pub fn validate_submission(
        submission: &serde_json::Value,
        schema: &[(String, (String, bool))],
    ) -> Result<(), String> {
        let obj = submission
            .as_object()
            .ok_or_else(|| "Submission must be a JSON object".to_string())?;

        for (field_name, (field_type, is_required)) in schema {
            let value = obj.get(field_name);

            // Check presence if required
            if *is_required && value.is_none() {
                return Err(format!("Required field '{}' is missing", field_name));
            }

            // If field exists and is not null, validate type
            if let Some(v) = value {
                if !v.is_null() {
                    match field_type.as_str() {
                        "text" | "string" => {
                            if !v.is_string() {
                                return Err(format!(
                                    "Field '{}' must be a string",
                                    field_name
                                ));
                            }
                        }
                        "email" => {
                            if let Some(s) = v.as_str() {
                                Self::validate_field_format(field_name, s, "email")?;
                            } else {
                                return Err(format!(
                                    "Field '{}' must be a string",
                                    field_name
                                ));
                            }
                        }
                        "number" | "int" => {
                            if !v.is_number() {
                                return Err(format!(
                                    "Field '{}' must be a number",
                                    field_name
                                ));
                            }
                        }
                        "bool" | "boolean" => {
                            if !v.is_boolean() {
                                return Err(format!(
                                    "Field '{}' must be a boolean",
                                    field_name
                                ));
                            }
                        }
                        _ => {} // Unknown type, skip type check
                    }
                }
            }
        }

        Ok(())
    }

    /// Validate conditional field: when condition_field == condition_value,
    /// dependent_field must not be empty
    pub fn validate_conditional_field(
        condition_field: &str,
        condition_value: &str,
        dependent_field: &str,
        form_state: &[(String, serde_json::Value)],
    ) -> Result<(), String> {
        let state_map: HashMap<String, serde_json::Value> = form_state
            .iter()
            .map(|(k, v)| (k.clone(), v.clone()))
            .collect();

        // Check condition field value
        let cond = state_map
            .get(condition_field)
            .and_then(|v| v.as_str())
            .unwrap_or("");

        // If condition is met, dependent field must not be empty
        if cond == condition_value {
            let dep_value = state_map.get(dependent_field);
            match dep_value {
                None => {
                    return Err(format!(
                        "Field '{}' is required when '{}' is '{}'",
                        dependent_field, condition_field, condition_value
                    ));
                }
                Some(serde_json::Value::String(s)) if s.is_empty() => {
                    return Err(format!(
                        "Field '{}' cannot be empty when '{}' is '{}'",
                        dependent_field, condition_field, condition_value
                    ));
                }
                _ => {}
            }
        }

        Ok(())
    }

    /// Validate grid context: grid must have positive column count
    pub fn validate_grid_context(grid: &A2UIComponent) -> Result<(), String> {
        if let A2UIComponent::Grid {
            id: _,
            columns,
            children: _,
        } = grid
        {
            if *columns == 0 {
                return Err("Grid must have at least 1 column".to_string());
            }
            Ok(())
        } else {
            Err("Not a grid component".to_string())
        }
    }

    /// Validate textarea context: if rows is specified, must be > 0
    pub fn validate_textarea_context(textarea: &A2UIComponent) -> Result<(), String> {
        if let A2UIComponent::Textarea {
            id: _,
            label: _,
            rows,
        } = textarea
        {
            if let Some(row_count) = rows {
                if *row_count == 0 {
                    return Err("Textarea rows must be greater than 0".to_string());
                }
            }
            Ok(())
        } else {
            Err("Not a textarea component".to_string())
        }
    }
}
