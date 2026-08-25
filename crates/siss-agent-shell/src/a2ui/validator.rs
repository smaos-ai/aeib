use crate::a2ui::schema::A2UIComponent;
use regex::Regex;
use std::collections::{HashMap, HashSet};

/// Validation error types with context
#[derive(Debug, Clone, PartialEq)]
pub enum ValidationError {
    ExceedsMaxDepth(usize),
    ExceedsComponentCount(usize),
    CircularReference(String),
    InvalidTextContent(String),
    MissingRequiredField(String),
    InvalidColorFormat(String),
    InvalidIdFormat(String),
    InvalidSizeFormat(String),
    InvalidAlertLevel(String),
    DuplicateFormId(String),
    InvalidProgressRange(u32, u32),
    EmptySelectOptions,
    InvalidGridColumns,
    InvalidTextareaRows,
    TextContentTooLarge(usize),
    MessageTooLarge(usize),
    ModalMissingButtons,
    Other(String),
}

impl std::fmt::Display for ValidationError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ValidationError::ExceedsMaxDepth(d) => {
                write!(
                    formatter,
                    "Component nesting exceeds maximum depth of {} levels",
                    d
                )
            }
            ValidationError::ExceedsComponentCount(c) => {
                write!(formatter, "Number of components exceeds limit of {}", c)
            }
            ValidationError::CircularReference(id) => {
                write!(
                    formatter,
                    "Circular reference detected in component: {}",
                    id
                )
            }
            ValidationError::InvalidTextContent(msg) => {
                write!(formatter, "Invalid text content: {}", msg)
            }
            ValidationError::MissingRequiredField(field_name) => {
                write!(formatter, "Missing required field: {}", field_name)
            }
            ValidationError::InvalidColorFormat(c) => {
                write!(formatter, "Invalid color format: {}", c)
            }
            ValidationError::InvalidIdFormat(id) => write!(formatter, "Invalid ID format: {}", id),
            ValidationError::InvalidSizeFormat(s) => {
                write!(formatter, "Invalid size format: {}", s)
            }
            ValidationError::InvalidAlertLevel(l) => {
                write!(formatter, "Invalid alert level: {}", l)
            }
            ValidationError::DuplicateFormId(id) => write!(formatter, "Duplicate form ID: {}", id),
            ValidationError::InvalidProgressRange(v, m) => {
                write!(formatter, "Progress value {} exceeds max {}", v, m)
            }
            ValidationError::EmptySelectOptions => {
                write!(formatter, "Select must have at least one option")
            }
            ValidationError::InvalidGridColumns => {
                write!(formatter, "Grid must have at least 1 column")
            }
            ValidationError::InvalidTextareaRows => write!(formatter, "Textarea rows must be > 0"),
            ValidationError::TextContentTooLarge(size) => {
                write!(
                    formatter,
                    "Text content exceeds max size of 10KB (got {} bytes)",
                    size
                )
            }
            ValidationError::MessageTooLarge(size) => {
                write!(
                    formatter,
                    "Message exceeds max size of 10KB (got {} bytes)",
                    size
                )
            }
            ValidationError::ModalMissingButtons => {
                write!(
                    formatter,
                    "Modal with content must have at least one action button"
                )
            }
            ValidationError::Other(msg) => write!(formatter, "{}", msg),
        }
    }
}

/// A2UI Validator with depth, count, and circular reference protection
pub struct A2UIValidator {
    max_depth: usize,      // Max 10 levels
    max_components: usize, // Max 1000 components per request
    max_text_size: usize,  // Max 10KB per text field
}

impl Default for A2UIValidator {
    fn default() -> Self {
        Self {
            max_depth: 10,
            max_components: 1000,
            max_text_size: 10240, // 10KB
        }
    }
}

impl A2UIValidator {
    pub fn new(max_depth: usize, max_components: usize) -> Self {
        Self {
            max_depth,
            max_components,
            max_text_size: 10240,
        }
    }

    /// Legacy validate function (backward compatible)
    pub fn validate(component: &A2UIComponent) -> Result<(), String> {
        Self::default()
            .validate_component(component)
            .map_err(|e| e.to_string())
    }

    /// Validate a single component with internal depth tracking
    pub fn validate_component(&self, component: &A2UIComponent) -> Result<(), ValidationError> {
        self.validate_component_internal(component, 0)
    }

    /// Validate event with component count check
    pub fn validate_event(&self, components: &[A2UIComponent]) -> Result<(), ValidationError> {
        if components.len() > self.max_components {
            return Err(ValidationError::ExceedsComponentCount(self.max_components));
        }

        for component in components {
            self.validate_component(component)?;
        }

        Ok(())
    }

    /// Check for circular references across all components
    pub fn check_circular_refs(&self, components: &[A2UIComponent]) -> Result<(), ValidationError> {
        let mut visited = HashSet::new();
        let mut rec_stack = HashSet::new();

        for component in components {
            self.check_circular_refs_internal(component, &mut visited, &mut rec_stack)?;
        }

        Ok(())
    }

    fn check_circular_refs_internal(
        &self,
        component: &A2UIComponent,
        visited: &mut HashSet<String>,
        rec_stack: &mut HashSet<String>,
    ) -> Result<(), ValidationError> {
        let id = self.get_component_id(component);

        if rec_stack.contains(&id) {
            return Err(ValidationError::CircularReference(id));
        }

        if visited.contains(&id) {
            return Ok(());
        }

        visited.insert(id.clone());
        rec_stack.insert(id.clone());

        // Traverse children
        match component {
            A2UIComponent::Card { children, .. }
            | A2UIComponent::Grid { children, .. }
            | A2UIComponent::Modal { children, .. } => {
                for child in children {
                    self.check_circular_refs_internal(child, visited, rec_stack)?;
                }
            }
            _ => {}
        }

        rec_stack.remove(&id);
        Ok(())
    }

    fn get_component_id(&self, component: &A2UIComponent) -> String {
        match component {
            A2UIComponent::Text { id, .. } => id.clone(),
            A2UIComponent::Badge { id, .. } => id.clone(),
            A2UIComponent::Alert { id, .. } => id.clone(),
            A2UIComponent::Progress { id, .. } => id.clone(),
            A2UIComponent::Divider { id } => id.clone(),
            A2UIComponent::Link { id, .. } => id.clone(),
            A2UIComponent::Tooltip { id, .. } => id.clone(),
            A2UIComponent::Breadcrumb { id, .. } => id.clone(),
            A2UIComponent::Input { id, .. } => id.clone(),
            A2UIComponent::Textarea { id, .. } => id.clone(),
            A2UIComponent::Select { id, .. } => id.clone(),
            A2UIComponent::Checkbox { id, .. } => id.clone(),
            A2UIComponent::Radio { id, .. } => id.clone(),
            A2UIComponent::Button { id, .. } => id.clone(),
            A2UIComponent::Card { id, .. } => id.clone(),
            A2UIComponent::Grid { id, .. } => id.clone(),
            A2UIComponent::Modal { id, .. } => id.clone(),
            A2UIComponent::Table { id, .. } => id.clone(),
        }
    }

    fn validate_component_internal(
        &self,
        component: &A2UIComponent,
        depth: usize,
    ) -> Result<(), ValidationError> {
        // Check depth limit
        if depth > self.max_depth {
            return Err(ValidationError::ExceedsMaxDepth(self.max_depth));
        }

        match component {
            // Display components
            A2UIComponent::Text { id, content, size } => {
                self.validate_id(id)?;
                if content.is_empty() {
                    return Err(ValidationError::InvalidTextContent(
                        "Text content must not be empty".to_string(),
                    ));
                }
                if content.len() > self.max_text_size {
                    return Err(ValidationError::TextContentTooLarge(content.len()));
                }
                if let Some(s) = size {
                    Self::validate_size_format(s)?;
                }
                Ok(())
            }
            A2UIComponent::Badge { id, label, color } => {
                self.validate_id(id)?;
                if label.is_empty() {
                    return Err(ValidationError::InvalidTextContent(
                        "Badge label must not be empty".to_string(),
                    ));
                }
                if let Some(c) = color {
                    Self::validate_color_format(c)?;
                }
                Ok(())
            }
            A2UIComponent::Alert { id, message, level } => {
                self.validate_id(id)?;
                if message.is_empty() {
                    return Err(ValidationError::InvalidTextContent(
                        "Alert message must not be empty".to_string(),
                    ));
                }
                if message.len() > self.max_text_size {
                    return Err(ValidationError::MessageTooLarge(message.len()));
                }
                Self::validate_alert_level(level)?;
                Ok(())
            }
            A2UIComponent::Progress { id, value, max, .. } => {
                self.validate_id(id)?;
                if value > max {
                    return Err(ValidationError::InvalidProgressRange(*value, *max));
                }
                Ok(())
            }
            A2UIComponent::Divider { id } => self.validate_id(id),
            A2UIComponent::Link { id, label, href } => {
                self.validate_id(id)?;
                if label.is_empty() {
                    return Err(ValidationError::InvalidTextContent(
                        "Link label must not be empty".to_string(),
                    ));
                }
                if href.is_empty() {
                    return Err(ValidationError::InvalidTextContent(
                        "Link href must not be empty".to_string(),
                    ));
                }
                Ok(())
            }
            A2UIComponent::Tooltip { id, text, content } => {
                self.validate_id(id)?;
                if text.is_empty() {
                    return Err(ValidationError::InvalidTextContent(
                        "Tooltip text must not be empty".to_string(),
                    ));
                }
                if content.is_empty() {
                    return Err(ValidationError::InvalidTextContent(
                        "Tooltip content must not be empty".to_string(),
                    ));
                }
                Ok(())
            }
            A2UIComponent::Breadcrumb { id, .. } => self.validate_id(id),
            // Form components
            A2UIComponent::Input { id, label, .. } => {
                self.validate_id(id)?;
                if label.is_empty() {
                    return Err(ValidationError::InvalidTextContent(
                        "Input label must not be empty".to_string(),
                    ));
                }
                Ok(())
            }
            A2UIComponent::Textarea { id, label, rows } => {
                self.validate_id(id)?;
                if label.is_empty() {
                    return Err(ValidationError::InvalidTextContent(
                        "Textarea label must not be empty".to_string(),
                    ));
                }
                if let Some(row_count) = rows {
                    if *row_count == 0 {
                        return Err(ValidationError::InvalidTextareaRows);
                    }
                }
                Ok(())
            }
            A2UIComponent::Select { id, label, options } => {
                self.validate_id(id)?;
                if label.is_empty() {
                    return Err(ValidationError::InvalidTextContent(
                        "Select label must not be empty".to_string(),
                    ));
                }
                if options.is_empty() {
                    return Err(ValidationError::EmptySelectOptions);
                }
                if options.len() > 100 {
                    return Err(ValidationError::Other(format!(
                        "Select options exceed limit of 100 (found {})",
                        options.len()
                    )));
                }
                Ok(())
            }
            A2UIComponent::Checkbox { id, label, .. } => {
                self.validate_id(id)?;
                if label.is_empty() {
                    return Err(ValidationError::InvalidTextContent(
                        "Checkbox label must not be empty".to_string(),
                    ));
                }
                Ok(())
            }
            A2UIComponent::Radio {
                id, label, value, ..
            } => {
                self.validate_id(id)?;
                if label.is_empty() {
                    return Err(ValidationError::InvalidTextContent(
                        "Radio label must not be empty".to_string(),
                    ));
                }
                if value.is_empty() {
                    return Err(ValidationError::InvalidTextContent(
                        "Radio value must not be empty".to_string(),
                    ));
                }
                Ok(())
            }
            A2UIComponent::Button { id, label, .. } => {
                self.validate_id(id)?;
                if label.is_empty() {
                    return Err(ValidationError::InvalidTextContent(
                        "Button label must not be empty".to_string(),
                    ));
                }
                Ok(())
            }
            // Layout components
            A2UIComponent::Card { id, children, .. } => {
                self.validate_id(id)?;
                for child in children {
                    self.validate_component_internal(child, depth + 1)?;
                }
                Ok(())
            }
            A2UIComponent::Grid {
                id,
                columns,
                children,
            } => {
                self.validate_id(id)?;
                if *columns == 0 {
                    return Err(ValidationError::InvalidGridColumns);
                }
                for child in children {
                    self.validate_component_internal(child, depth + 1)?;
                }
                Ok(())
            }
            A2UIComponent::Modal {
                id,
                title,
                content,
                children,
            } => {
                self.validate_id(id)?;
                if title.is_empty() {
                    return Err(ValidationError::InvalidTextContent(
                        "Modal title must not be empty".to_string(),
                    ));
                }
                if content.is_empty() {
                    return Err(ValidationError::InvalidTextContent(
                        "Modal content must not be empty".to_string(),
                    ));
                }
                if content.len() > self.max_text_size {
                    return Err(ValidationError::MessageTooLarge(content.len()));
                }

                // Validate modal has action buttons if it has substantial content
                if !content.is_empty() && content.len() > 5 {
                    let has_button = children
                        .iter()
                        .any(|child| matches!(child, A2UIComponent::Button { .. }));
                    if !has_button {
                        return Err(ValidationError::ModalMissingButtons);
                    }
                }

                for child in children {
                    self.validate_component_internal(child, depth + 1)?;
                }
                Ok(())
            }
            A2UIComponent::Table { id, .. } => self.validate_id(id),
        }
    }

    fn validate_id(&self, id: &str) -> Result<(), ValidationError> {
        if id.is_empty() {
            return Err(ValidationError::MissingRequiredField(
                "Component ID must not be empty".to_string(),
            ));
        }
        // ID should be alphanumeric with underscores/hyphens
        if !id
            .chars()
            .all(|c| c.is_alphanumeric() || c == '_' || c == '-')
        {
            return Err(ValidationError::InvalidIdFormat(id.to_string()));
        }
        Ok(())
    }

    fn validate_color_format(color: &str) -> Result<(), ValidationError> {
        // Support hex colors and named colors
        if color.starts_with('#') {
            if color.len() != 7 {
                return Err(ValidationError::InvalidColorFormat(color.to_string()));
            }
            if !color[1..].chars().all(|c| c.is_ascii_hexdigit()) {
                return Err(ValidationError::InvalidColorFormat(color.to_string()));
            }
        } else {
            // Named colors
            let valid_colors = [
                "red", "blue", "green", "yellow", "orange", "purple", "pink", "gray", "white",
                "black",
            ];
            if !valid_colors.contains(&color) {
                return Err(ValidationError::InvalidColorFormat(color.to_string()));
            }
        }
        Ok(())
    }

    fn validate_size_format(size: &str) -> Result<(), ValidationError> {
        match size {
            "xs" | "sm" | "md" | "lg" | "xl" | "2xl" | "3xl" => Ok(()),
            _ => Err(ValidationError::InvalidSizeFormat(size.to_string())),
        }
    }

    fn validate_alert_level(level: &str) -> Result<(), ValidationError> {
        match level {
            "info" | "warn" | "error" | "success" => Ok(()),
            _ => Err(ValidationError::InvalidAlertLevel(level.to_string())),
        }
    }

    /// Validate all IDs are unique within the component tree (for form IDs)
    pub fn validate_unique_form_ids(
        &self,
        components: &[A2UIComponent],
    ) -> Result<(), ValidationError> {
        let mut ids = HashSet::new();
        self.collect_ids(components, &mut ids)?;
        Ok(())
    }

    fn collect_ids(
        &self,
        components: &[A2UIComponent],
        seen_ids: &mut HashSet<String>,
    ) -> Result<(), ValidationError> {
        for component in components {
            let id = self.get_component_id(component);
            if !seen_ids.insert(id.clone()) {
                return Err(ValidationError::DuplicateFormId(id));
            }

            // Collect from children recursively
            match component {
                A2UIComponent::Card { children, .. }
                | A2UIComponent::Grid { children, .. }
                | A2UIComponent::Modal { children, .. } => {
                    self.collect_ids(children, seen_ids)?;
                }
                _ => {}
            }
        }
        Ok(())
    }

    // === CONTEXT-AWARE VALIDATION (backward compatible wrappers) ===

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
                let has_button = children
                    .iter()
                    .any(|child| matches!(child, A2UIComponent::Button { .. }));
                if !has_button {
                    return Err(
                        "Modal with content must have at least one action button".to_string()
                    );
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
                                return Err(format!("Field '{}' must be a string", field_name));
                            }
                        }
                        "email" => {
                            if let Some(s) = v.as_str() {
                                Self::validate_field_format(field_name, s, "email")?;
                            } else {
                                return Err(format!("Field '{}' must be a string", field_name));
                            }
                        }
                        "number" | "int" => {
                            if !v.is_number() {
                                return Err(format!("Field '{}' must be a number", field_name));
                            }
                        }
                        "bool" | "boolean" => {
                            if !v.is_boolean() {
                                return Err(format!("Field '{}' must be a boolean", field_name));
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

/// Fail-closed validation implementation for A2UIComponent
/// This allows components to validate themselves with Result<(), ValidationError>
impl A2UIComponent {
    /// Validate this component with fail-closed semantics
    /// Returns Ok(()) if valid, or descriptive ValidationError if invalid
    pub fn validate(&self) -> Result<(), ValidationError> {
        A2UIValidator::default().validate_component(self)
    }
}
