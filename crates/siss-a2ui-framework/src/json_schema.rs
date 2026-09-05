use serde_json::Value;
use thiserror::Error;

#[derive(Debug, Clone, Error, PartialEq)]
pub enum SchemaError {
    #[error("Type mismatch: expected {expected}, got {got}")]
    TypeMismatch { expected: String, got: String },
    #[error("Missing required field: {field}")]
    MissingRequired { field: String },
    #[error("Additional property not allowed: {field}")]
    AdditionalProperty { field: String },
    #[error("Validation failed: {reason}")]
    ValidationFailed { reason: String },
}

pub struct JsonSchemaValidator;

impl JsonSchemaValidator {
    pub fn validate(json: &Value) -> Result<(), SchemaError> {
        if !json.is_object() {
            return Err(SchemaError::ValidationFailed {
                reason: "Expected JSON object".to_string(),
            });
        }

        let obj = json.as_object().unwrap();

        // Check for type mismatches: numeric values in fields that should be strings
        for (key, value) in obj.iter() {
            match (key.as_str(), value) {
                // Numeric value for string fields
                (field, Value::Number(_)) if field == "label" || field == "content" || field == "value" => {
                    return Err(SchemaError::TypeMismatch {
                        expected: "string".to_string(),
                        got: "number".to_string(),
                    });
                }
                _ => {}
            }
        }

        // Check for required fields based on object type
        if let Some(type_field) = obj.get("type").and_then(|v| v.as_str()) {
            match type_field {
                "button" => {
                    if !obj.contains_key("label") {
                        return Err(SchemaError::MissingRequired {
                            field: "label".to_string(),
                        });
                    }
                }
                _ => {}
            }
        }

        Ok(())
    }

    pub fn validate_button(json: &Value) -> Result<(), SchemaError> {
        let obj = json.as_object().ok_or(SchemaError::ValidationFailed {
            reason: "Expected object".to_string(),
        })?;

        // Check required fields
        if !obj.contains_key("label") {
            return Err(SchemaError::MissingRequired {
                field: "label".to_string(),
            });
        }

        if !obj.contains_key("id") {
            return Err(SchemaError::MissingRequired {
                field: "id".to_string(),
            });
        }

        Ok(())
    }

    pub fn validate_input(json: &Value) -> Result<(), SchemaError> {
        let obj = json.as_object().ok_or(SchemaError::ValidationFailed {
            reason: "Expected object".to_string(),
        })?;

        if !obj.contains_key("label") {
            return Err(SchemaError::MissingRequired {
                field: "label".to_string(),
            });
        }

        if !obj.contains_key("id") {
            return Err(SchemaError::MissingRequired {
                field: "id".to_string(),
            });
        }

        Ok(())
    }
}
