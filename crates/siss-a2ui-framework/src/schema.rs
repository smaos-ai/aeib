use serde_json::{json, Value};
use std::collections::HashMap;

pub struct SchemaRegistry;

impl SchemaRegistry {
    pub fn schema_for(type_name: &str) -> Result<Value, String> {
        match type_name {
            "Button" => Ok(Self::button_schema()),
            "Input" => Ok(Self::input_schema()),
            "Select" => Ok(Self::select_schema()),
            "Textarea" => Ok(Self::textarea_schema()),
            "Checkbox" => Ok(Self::checkbox_schema()),
            "Radio" => Ok(Self::radio_schema()),
            "Text" => Ok(Self::text_schema()),
            "Badge" => Ok(Self::badge_schema()),
            "Alert" => Ok(Self::alert_schema()),
            "Progress" => Ok(Self::progress_schema()),
            "Divider" => Ok(Self::divider_schema()),
            "Link" => Ok(Self::link_schema()),
            "Tooltip" => Ok(Self::tooltip_schema()),
            "Breadcrumb" => Ok(Self::breadcrumb_schema()),
            "Card" => Ok(Self::card_schema()),
            "Grid" => Ok(Self::grid_schema()),
            "Modal" => Ok(Self::modal_schema()),
            "Table" => Ok(Self::table_schema()),
            _ => Err(format!("Unknown component type: {}", type_name)),
        }
    }

    pub fn all_schemas() -> HashMap<&'static str, Value> {
        let mut schemas = HashMap::new();
        schemas.insert("Button", Self::button_schema());
        schemas.insert("Input", Self::input_schema());
        schemas.insert("Select", Self::select_schema());
        schemas.insert("Textarea", Self::textarea_schema());
        schemas.insert("Checkbox", Self::checkbox_schema());
        schemas.insert("Radio", Self::radio_schema());
        schemas.insert("Text", Self::text_schema());
        schemas.insert("Badge", Self::badge_schema());
        schemas.insert("Alert", Self::alert_schema());
        schemas.insert("Progress", Self::progress_schema());
        schemas.insert("Divider", Self::divider_schema());
        schemas.insert("Link", Self::link_schema());
        schemas.insert("Tooltip", Self::tooltip_schema());
        schemas.insert("Breadcrumb", Self::breadcrumb_schema());
        schemas.insert("Card", Self::card_schema());
        schemas.insert("Grid", Self::grid_schema());
        schemas.insert("Modal", Self::modal_schema());
        schemas.insert("Table", Self::table_schema());
        schemas
    }

    fn button_schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "id": { "type": "string" },
                "label": { "type": "string" },
                "action": { "type": "string", "enum": ["submit", "reset", "custom"] }
            },
            "required": ["id", "label"]
        })
    }

    fn input_schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "id": { "type": "string" },
                "label": { "type": "string" },
                "placeholder": { "type": "string" },
                "required": { "type": "boolean" }
            },
            "required": ["id", "label"]
        })
    }

    fn select_schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "id": { "type": "string" },
                "label": { "type": "string" },
                "options": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "value": { "type": "string" },
                            "label": { "type": "string" }
                        }
                    }
                }
            },
            "required": ["id", "label", "options"]
        })
    }

    fn textarea_schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "id": { "type": "string" },
                "label": { "type": "string" },
                "rows": { "type": "integer" }
            },
            "required": ["id", "label"]
        })
    }

    fn checkbox_schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "id": { "type": "string" },
                "label": { "type": "string" },
                "checked": { "type": "boolean" }
            },
            "required": ["id", "label"]
        })
    }

    fn radio_schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "id": { "type": "string" },
                "label": { "type": "string" },
                "value": { "type": "string" },
                "checked": { "type": "boolean" }
            },
            "required": ["id", "label", "value"]
        })
    }

    fn text_schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "id": { "type": "string" },
                "content": { "type": "string" },
                "size": { "type": "string", "enum": ["sm", "md", "lg"] }
            },
            "required": ["id", "content"]
        })
    }

    fn badge_schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "id": { "type": "string" },
                "label": { "type": "string" },
                "color": { "type": "string", "enum": ["blue", "red", "green", "yellow"] }
            },
            "required": ["id", "label"]
        })
    }

    fn alert_schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "id": { "type": "string" },
                "message": { "type": "string" },
                "level": { "type": "string", "enum": ["info", "warn", "error"] }
            },
            "required": ["id", "message", "level"]
        })
    }

    fn progress_schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "id": { "type": "string" },
                "value": { "type": "integer" },
                "max": { "type": "integer" },
                "label": { "type": "string" }
            },
            "required": ["id", "value", "max"]
        })
    }

    fn divider_schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "id": { "type": "string" }
            },
            "required": ["id"]
        })
    }

    fn link_schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "id": { "type": "string" },
                "label": { "type": "string" },
                "href": { "type": "string" }
            },
            "required": ["id", "label", "href"]
        })
    }

    fn tooltip_schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "id": { "type": "string" },
                "text": { "type": "string" },
                "content": { "type": "string" }
            },
            "required": ["id", "text", "content"]
        })
    }

    fn breadcrumb_schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "id": { "type": "string" },
                "items": {
                    "type": "array",
                    "items": { "type": "string" }
                }
            },
            "required": ["id", "items"]
        })
    }

    fn card_schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "id": { "type": "string" },
                "title": { "type": "string" },
                "children": {
                    "type": "array",
                    "items": { "type": "object" }
                }
            },
            "required": ["id", "children"]
        })
    }

    fn grid_schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "id": { "type": "string" },
                "columns": { "type": "integer" },
                "children": {
                    "type": "array",
                    "items": { "type": "object" }
                }
            },
            "required": ["id", "columns", "children"]
        })
    }

    fn modal_schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "id": { "type": "string" },
                "title": { "type": "string" },
                "content": { "type": "string" },
                "children": {
                    "type": "array",
                    "items": { "type": "object" }
                }
            },
            "required": ["id", "title", "content", "children"]
        })
    }

    fn table_schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "id": { "type": "string" },
                "headers": {
                    "type": "array",
                    "items": { "type": "string" }
                },
                "rows": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": { "type": "string" }
                    }
                }
            },
            "required": ["id", "headers", "rows"]
        })
    }
}
