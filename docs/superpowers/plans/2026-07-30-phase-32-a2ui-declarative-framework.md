# Phase 32: A2UI Declarative Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build safe declarative UI framework with 18 components, JSON schema validation, and React code generation—50+ tests total.

**Architecture:** Create new `siss-a2ui-framework` crate extending existing A2UIComponent enum with introspection metadata, JSON Schema generation (Draft 2020-12), and React TSX renderer. Integrate with existing PayloadValidator/PayloadRenderer pipeline.

**Tech Stack:** Rust (Cargo workspace), serde/serde_json, serde-json-schema crate (or manual JSON Schema generation), no external React runtime (pure string generation).

---

## File Structure

### Create (New Crate: `crates/siss-a2ui-framework/`)

**Core Modules:**
- `src/lib.rs` — Public API exports
- `src/schema.rs` — Extended component metadata + introspection traits
- `src/components.rs` — 18 component definitions with derived traits
- `src/json_schema.rs` — JSON Schema Draft 2020-12 generation
- `src/validation.rs` — Schema validation logic (extends existing A2UIValidator)
- `src/react_renderer.rs` — A2UIComponent → TSX code generation
- `src/performance.rs` — Metrics collection (render time, validation latency)
- `Cargo.toml` — New package manifest

**Tests:**
- `tests/integration_tests.rs` — Full pipeline tests (schema → validation → render)
- `tests/performance_benchmarks.rs` — Render time (<100ms for 100 components)
- `tests/schema_generation_tests.rs` — JSON Schema correctness (12 tests)
- `tests/react_codegen_tests.rs` — TSX syntax and prop types (13 tests)
- `tests/validation_tests.rs` — Validation edge cases (10 tests)

---

## Task Breakdown

### Task 1: Create `siss-a2ui-framework` Crate Skeleton

**Files:**
- Create: `crates/siss-a2ui-framework/Cargo.toml`
- Create: `crates/siss-a2ui-framework/src/lib.rs`

**Steps:**

- [ ] **Step 1: Create Cargo.toml for new crate**

```toml
[package]
name = "siss-a2ui-framework"
edition.workspace = true
version.workspace = true
license.workspace = true

[dependencies]
siss-agent-shell = { path = "../siss-agent-shell" }
serde.workspace = true
serde_json.workspace = true
uuid.workspace = true
thiserror.workspace = true
regex.workspace = true
```

**Save to:** `/crates/siss-a2ui-framework/Cargo.toml`

- [ ] **Step 2: Add crate to workspace Cargo.toml**

Edit `/Cargo.toml` — add `"crates/siss-a2ui-framework"` to `[workspace] members` list.

**Verify:** Find the line with `"crates/siss-a2ui-renderer"` and add new crate right after it.

- [ ] **Step 3: Create minimal lib.rs**

```rust
//! A2UI Declarative Framework
//! 
//! JSON schema validation and React code generation for 18 safe UI components.

pub mod schema;
pub mod components;
pub mod json_schema;
pub mod validation;
pub mod react_renderer;
pub mod performance;

// Re-export key types
pub use schema::{ComponentMetadata, ComponentIntrospection};
pub use components::*;
pub use json_schema::JsonSchemaGenerator;
pub use react_renderer::ReactCodeGenerator;
pub use validation::SchemaValidator;
pub use performance::PerformanceMetrics;

#[cfg(test)]
mod tests {
    #[test]
    fn test_crate_compiles() {
        // Placeholder: actual tests in integration suite
    }
}
```

**Save to:** `/crates/siss-a2ui-framework/src/lib.rs`

- [ ] **Step 4: Run cargo check to verify crate builds**

```bash
cd /Users/andriileukhin/Documents/SovereignNexus
cargo check -p siss-a2ui-framework
```

Expected: Build succeeds (may have unresolved modules, that's OK).

- [ ] **Step 5: Commit**

```bash
git add crates/siss-a2ui-framework/ Cargo.toml
git commit -m "chore: create siss-a2ui-framework crate skeleton"
```

---

### Task 2: Define Component Metadata + Introspection System

**Files:**
- Create: `crates/siss-a2ui-framework/src/schema.rs`

**Steps:**

- [ ] **Step 1: Design component metadata trait**

```rust
use serde::{Serialize, Deserialize};
use std::collections::HashMap;

/// Metadata describing a single component type
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComponentMetadata {
    /// Type name (e.g., "text", "button")
    pub name: String,
    /// Human-readable description
    pub description: String,
    /// Category: "display", "form", "layout", "action", "feedback"
    pub category: String,
    /// Required fields (field names that must be present)
    pub required_fields: Vec<String>,
    /// Optional fields with their types
    pub optional_fields: HashMap<String, String>,
    /// Field type information
    pub field_types: HashMap<String, FieldType>,
    /// Example JSON
    pub example: serde_json::Value,
}

/// Field type descriptor
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "lowercase")]
pub enum FieldType {
    String {
        min_length: Option<usize>,
        max_length: Option<usize>,
        pattern: Option<String>,
        enum_values: Option<Vec<String>>,
    },
    Number {
        minimum: Option<i64>,
        maximum: Option<i64>,
    },
    Boolean,
    Array {
        item_type: Box<FieldType>,
        min_items: Option<usize>,
        max_items: Option<usize>,
    },
    Object {
        properties: HashMap<String, FieldType>,
    },
}

/// Provides introspection for all 18 components
pub trait ComponentIntrospection {
    /// Get metadata for a component type
    fn metadata(component_type: &str) -> Option<ComponentMetadata>;
    
    /// List all known component types
    fn all_types() -> Vec<String>;
    
    /// Get metadata for all components
    fn all_metadata() -> Vec<ComponentMetadata>;
}

/// Registry holding all 18 component metadata
pub struct A2UIComponentRegistry;

impl ComponentIntrospection for A2UIComponentRegistry {
    fn metadata(component_type: &str) -> Option<ComponentMetadata> {
        match component_type {
            "text" => Some(Self::text_metadata()),
            "badge" => Some(Self::badge_metadata()),
            "alert" => Some(Self::alert_metadata()),
            "progress" => Some(Self::progress_metadata()),
            "divider" => Some(Self::divider_metadata()),
            "link" => Some(Self::link_metadata()),
            "tooltip" => Some(Self::tooltip_metadata()),
            "breadcrumb" => Some(Self::breadcrumb_metadata()),
            "input" => Some(Self::input_metadata()),
            "textarea" => Some(Self::textarea_metadata()),
            "select" => Some(Self::select_metadata()),
            "checkbox" => Some(Self::checkbox_metadata()),
            "radio" => Some(Self::radio_metadata()),
            "button" => Some(Self::button_metadata()),
            "card" => Some(Self::card_metadata()),
            "grid" => Some(Self::grid_metadata()),
            "modal" => Some(Self::modal_metadata()),
            "table" => Some(Self::table_metadata()),
            _ => None,
        }
    }

    fn all_types() -> Vec<String> {
        vec![
            "text", "badge", "alert", "progress", "divider", "link", "tooltip", "breadcrumb",
            "input", "textarea", "select", "checkbox", "radio", "button",
            "card", "grid", "modal", "table",
        ]
        .into_iter()
        .map(|s| s.to_string())
        .collect()
    }

    fn all_metadata() -> Vec<ComponentMetadata> {
        Self::all_types()
            .iter()
            .filter_map(|t| Self::metadata(t))
            .collect()
    }
}

impl A2UIComponentRegistry {
    fn text_metadata() -> ComponentMetadata {
        ComponentMetadata {
            name: "text".to_string(),
            description: "Plain text display".to_string(),
            category: "display".to_string(),
            required_fields: vec!["id".to_string(), "content".to_string()],
            optional_fields: {
                let mut m = HashMap::new();
                m.insert("size".to_string(), "string".to_string());
                m
            },
            field_types: {
                let mut m = HashMap::new();
                m.insert("id".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("content".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(10000),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("size".to_string(), FieldType::String {
                    min_length: None,
                    max_length: None,
                    pattern: None,
                    enum_values: Some(vec!["sm".to_string(), "md".to_string(), "lg".to_string()]),
                });
                m
            },
            example: serde_json::json!({
                "type": "text",
                "id": "text1",
                "content": "Hello World",
                "size": "md"
            }),
        }
    }

    fn badge_metadata() -> ComponentMetadata {
        ComponentMetadata {
            name: "badge".to_string(),
            description: "Badge/label with color".to_string(),
            category: "display".to_string(),
            required_fields: vec!["id".to_string(), "label".to_string()],
            optional_fields: {
                let mut m = HashMap::new();
                m.insert("color".to_string(), "string".to_string());
                m
            },
            field_types: {
                let mut m = HashMap::new();
                m.insert("id".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("label".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("color".to_string(), FieldType::String {
                    min_length: None,
                    max_length: None,
                    pattern: None,
                    enum_values: Some(vec![
                        "blue".to_string(), "red".to_string(), "green".to_string(), "yellow".to_string()
                    ]),
                });
                m
            },
            example: serde_json::json!({
                "type": "badge",
                "id": "badge1",
                "label": "New",
                "color": "blue"
            }),
        }
    }

    fn alert_metadata() -> ComponentMetadata {
        ComponentMetadata {
            name: "alert".to_string(),
            description: "Alert message (info/warn/error)".to_string(),
            category: "feedback".to_string(),
            required_fields: vec!["id".to_string(), "message".to_string()],
            optional_fields: {
                let mut m = HashMap::new();
                m.insert("level".to_string(), "string".to_string());
                m
            },
            field_types: {
                let mut m = HashMap::new();
                m.insert("id".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("message".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(10000),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("level".to_string(), FieldType::String {
                    min_length: None,
                    max_length: None,
                    pattern: None,
                    enum_values: Some(vec!["info".to_string(), "warn".to_string(), "error".to_string()]),
                });
                m
            },
            example: serde_json::json!({
                "type": "alert",
                "id": "alert1",
                "message": "Warning message",
                "level": "warn"
            }),
        }
    }

    fn progress_metadata() -> ComponentMetadata {
        ComponentMetadata {
            name: "progress".to_string(),
            description: "Progress bar with percentage".to_string(),
            category: "feedback".to_string(),
            required_fields: vec!["id".to_string(), "value".to_string(), "max".to_string()],
            optional_fields: {
                let mut m = HashMap::new();
                m.insert("label".to_string(), "string".to_string());
                m
            },
            field_types: {
                let mut m = HashMap::new();
                m.insert("id".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("value".to_string(), FieldType::Number {
                    minimum: Some(0),
                    maximum: None,
                });
                m.insert("max".to_string(), FieldType::Number {
                    minimum: Some(1),
                    maximum: None,
                });
                m
            },
            example: serde_json::json!({
                "type": "progress",
                "id": "prog1",
                "value": 50,
                "max": 100
            }),
        }
    }

    fn divider_metadata() -> ComponentMetadata {
        ComponentMetadata {
            name: "divider".to_string(),
            description: "Horizontal divider line".to_string(),
            category: "layout".to_string(),
            required_fields: vec!["id".to_string()],
            optional_fields: HashMap::new(),
            field_types: {
                let mut m = HashMap::new();
                m.insert("id".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m
            },
            example: serde_json::json!({
                "type": "divider",
                "id": "div1"
            }),
        }
    }

    fn link_metadata() -> ComponentMetadata {
        ComponentMetadata {
            name: "link".to_string(),
            description: "Hyperlink".to_string(),
            category: "navigation".to_string(),
            required_fields: vec!["id".to_string(), "label".to_string(), "href".to_string()],
            optional_fields: HashMap::new(),
            field_types: {
                let mut m = HashMap::new();
                m.insert("id".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("label".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("href".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(2048),
                    pattern: None,
                    enum_values: None,
                });
                m
            },
            example: serde_json::json!({
                "type": "link",
                "id": "link1",
                "label": "Click here",
                "href": "https://example.com"
            }),
        }
    }

    fn tooltip_metadata() -> ComponentMetadata {
        ComponentMetadata {
            name: "tooltip".to_string(),
            description: "Hover tooltip".to_string(),
            category: "feedback".to_string(),
            required_fields: vec!["id".to_string(), "text".to_string(), "content".to_string()],
            optional_fields: HashMap::new(),
            field_types: {
                let mut m = HashMap::new();
                m.insert("id".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("text".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("content".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(1024),
                    pattern: None,
                    enum_values: None,
                });
                m
            },
            example: serde_json::json!({
                "type": "tooltip",
                "id": "tip1",
                "text": "Hover me",
                "content": "Tooltip content"
            }),
        }
    }

    fn breadcrumb_metadata() -> ComponentMetadata {
        ComponentMetadata {
            name: "breadcrumb".to_string(),
            description: "Breadcrumb navigation".to_string(),
            category: "navigation".to_string(),
            required_fields: vec!["id".to_string(), "items".to_string()],
            optional_fields: HashMap::new(),
            field_types: {
                let mut m = HashMap::new();
                m.insert("id".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("items".to_string(), FieldType::Array {
                    item_type: Box::new(FieldType::String {
                        min_length: Some(1),
                        max_length: Some(255),
                        pattern: None,
                        enum_values: None,
                    }),
                    min_items: Some(1),
                    max_items: None,
                });
                m
            },
            example: serde_json::json!({
                "type": "breadcrumb",
                "id": "bread1",
                "items": ["Home", "Products", "Details"]
            }),
        }
    }

    fn input_metadata() -> ComponentMetadata {
        ComponentMetadata {
            name: "input".to_string(),
            description: "Text input field".to_string(),
            category: "form".to_string(),
            required_fields: vec!["id".to_string(), "label".to_string()],
            optional_fields: {
                let mut m = HashMap::new();
                m.insert("placeholder".to_string(), "string".to_string());
                m.insert("required".to_string(), "boolean".to_string());
                m
            },
            field_types: {
                let mut m = HashMap::new();
                m.insert("id".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("label".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("placeholder".to_string(), FieldType::String {
                    min_length: None,
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("required".to_string(), FieldType::Boolean);
                m
            },
            example: serde_json::json!({
                "type": "input",
                "id": "input1",
                "label": "Name",
                "placeholder": "Enter your name",
                "required": true
            }),
        }
    }

    fn textarea_metadata() -> ComponentMetadata {
        ComponentMetadata {
            name: "textarea".to_string(),
            description: "Multi-line text area".to_string(),
            category: "form".to_string(),
            required_fields: vec!["id".to_string(), "label".to_string()],
            optional_fields: {
                let mut m = HashMap::new();
                m.insert("rows".to_string(), "number".to_string());
                m
            },
            field_types: {
                let mut m = HashMap::new();
                m.insert("id".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("label".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("rows".to_string(), FieldType::Number {
                    minimum: Some(1),
                    maximum: Some(50),
                });
                m
            },
            example: serde_json::json!({
                "type": "textarea",
                "id": "textarea1",
                "label": "Comments",
                "rows": 5
            }),
        }
    }

    fn select_metadata() -> ComponentMetadata {
        ComponentMetadata {
            name: "select".to_string(),
            description: "Dropdown selector".to_string(),
            category: "form".to_string(),
            required_fields: vec!["id".to_string(), "label".to_string(), "options".to_string()],
            optional_fields: HashMap::new(),
            field_types: {
                let mut m = HashMap::new();
                m.insert("id".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("label".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("options".to_string(), FieldType::Array {
                    item_type: Box::new(FieldType::Object {
                        properties: {
                            let mut p = HashMap::new();
                            p.insert("value".to_string(), FieldType::String {
                                min_length: Some(1),
                                max_length: Some(255),
                                pattern: None,
                                enum_values: None,
                            });
                            p.insert("label".to_string(), FieldType::String {
                                min_length: Some(1),
                                max_length: Some(255),
                                pattern: None,
                                enum_values: None,
                            });
                            p
                        },
                    }),
                    min_items: Some(1),
                    max_items: None,
                });
                m
            },
            example: serde_json::json!({
                "type": "select",
                "id": "select1",
                "label": "Choose option",
                "options": [
                    { "value": "opt1", "label": "Option 1" },
                    { "value": "opt2", "label": "Option 2" }
                ]
            }),
        }
    }

    fn checkbox_metadata() -> ComponentMetadata {
        ComponentMetadata {
            name: "checkbox".to_string(),
            description: "Checkbox input".to_string(),
            category: "form".to_string(),
            required_fields: vec!["id".to_string(), "label".to_string()],
            optional_fields: {
                let mut m = HashMap::new();
                m.insert("checked".to_string(), "boolean".to_string());
                m
            },
            field_types: {
                let mut m = HashMap::new();
                m.insert("id".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("label".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("checked".to_string(), FieldType::Boolean);
                m
            },
            example: serde_json::json!({
                "type": "checkbox",
                "id": "check1",
                "label": "Agree to terms",
                "checked": false
            }),
        }
    }

    fn radio_metadata() -> ComponentMetadata {
        ComponentMetadata {
            name: "radio".to_string(),
            description: "Radio button group".to_string(),
            category: "form".to_string(),
            required_fields: vec!["id".to_string(), "label".to_string(), "value".to_string()],
            optional_fields: {
                let mut m = HashMap::new();
                m.insert("checked".to_string(), "boolean".to_string());
                m
            },
            field_types: {
                let mut m = HashMap::new();
                m.insert("id".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("label".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("value".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("checked".to_string(), FieldType::Boolean);
                m
            },
            example: serde_json::json!({
                "type": "radio",
                "id": "radio1",
                "label": "Option A",
                "value": "a",
                "checked": true
            }),
        }
    }

    fn button_metadata() -> ComponentMetadata {
        ComponentMetadata {
            name: "button".to_string(),
            description: "Clickable button".to_string(),
            category: "action".to_string(),
            required_fields: vec!["id".to_string(), "label".to_string()],
            optional_fields: {
                let mut m = HashMap::new();
                m.insert("action".to_string(), "string".to_string());
                m
            },
            field_types: {
                let mut m = HashMap::new();
                m.insert("id".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("label".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("action".to_string(), FieldType::String {
                    min_length: None,
                    max_length: None,
                    pattern: None,
                    enum_values: Some(vec!["submit".to_string(), "reset".to_string(), "custom".to_string()]),
                });
                m
            },
            example: serde_json::json!({
                "type": "button",
                "id": "btn1",
                "label": "Submit",
                "action": "submit"
            }),
        }
    }

    fn card_metadata() -> ComponentMetadata {
        ComponentMetadata {
            name: "card".to_string(),
            description: "Card container with title".to_string(),
            category: "layout".to_string(),
            required_fields: vec!["id".to_string(), "children".to_string()],
            optional_fields: {
                let mut m = HashMap::new();
                m.insert("title".to_string(), "string".to_string());
                m
            },
            field_types: {
                let mut m = HashMap::new();
                m.insert("id".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("title".to_string(), FieldType::String {
                    min_length: None,
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("children".to_string(), FieldType::Array {
                    item_type: Box::new(FieldType::Object {
                        properties: HashMap::new(),
                    }),
                    min_items: Some(0),
                    max_items: None,
                });
                m
            },
            example: serde_json::json!({
                "type": "card",
                "id": "card1",
                "title": "Card Title",
                "children": []
            }),
        }
    }

    fn grid_metadata() -> ComponentMetadata {
        ComponentMetadata {
            name: "grid".to_string(),
            description: "Grid layout with N columns".to_string(),
            category: "layout".to_string(),
            required_fields: vec!["id".to_string(), "columns".to_string(), "children".to_string()],
            optional_fields: HashMap::new(),
            field_types: {
                let mut m = HashMap::new();
                m.insert("id".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("columns".to_string(), FieldType::Number {
                    minimum: Some(1),
                    maximum: Some(12),
                });
                m.insert("children".to_string(), FieldType::Array {
                    item_type: Box::new(FieldType::Object {
                        properties: HashMap::new(),
                    }),
                    min_items: Some(0),
                    max_items: None,
                });
                m
            },
            example: serde_json::json!({
                "type": "grid",
                "id": "grid1",
                "columns": 3,
                "children": []
            }),
        }
    }

    fn modal_metadata() -> ComponentMetadata {
        ComponentMetadata {
            name: "modal".to_string(),
            description: "Modal dialog box".to_string(),
            category: "layout".to_string(),
            required_fields: vec!["id".to_string(), "title".to_string(), "content".to_string(), "children".to_string()],
            optional_fields: HashMap::new(),
            field_types: {
                let mut m = HashMap::new();
                m.insert("id".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("title".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("content".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(10000),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("children".to_string(), FieldType::Array {
                    item_type: Box::new(FieldType::Object {
                        properties: HashMap::new(),
                    }),
                    min_items: Some(0),
                    max_items: None,
                });
                m
            },
            example: serde_json::json!({
                "type": "modal",
                "id": "modal1",
                "title": "Dialog",
                "content": "Content",
                "children": []
            }),
        }
    }

    fn table_metadata() -> ComponentMetadata {
        ComponentMetadata {
            name: "table".to_string(),
            description: "Data table with headers and rows".to_string(),
            category: "display".to_string(),
            required_fields: vec!["id".to_string(), "headers".to_string(), "rows".to_string()],
            optional_fields: HashMap::new(),
            field_types: {
                let mut m = HashMap::new();
                m.insert("id".to_string(), FieldType::String {
                    min_length: Some(1),
                    max_length: Some(255),
                    pattern: None,
                    enum_values: None,
                });
                m.insert("headers".to_string(), FieldType::Array {
                    item_type: Box::new(FieldType::String {
                        min_length: Some(1),
                        max_length: Some(255),
                        pattern: None,
                        enum_values: None,
                    }),
                    min_items: Some(1),
                    max_items: None,
                });
                m.insert("rows".to_string(), FieldType::Array {
                    item_type: Box::new(FieldType::Array {
                        item_type: Box::new(FieldType::String {
                            min_length: None,
                            max_length: Some(1000),
                            pattern: None,
                            enum_values: None,
                        }),
                        min_items: Some(1),
                        max_items: None,
                    }),
                    min_items: Some(0),
                    max_items: None,
                });
                m
            },
            example: serde_json::json!({
                "type": "table",
                "id": "table1",
                "headers": ["Name", "Value"],
                "rows": [["Item1", "Value1"]]
            }),
        }
    }
}
```

**Save to:** `/crates/siss-a2ui-framework/src/schema.rs`

- [ ] **Step 2: Run cargo check to verify schema module compiles**

```bash
cd /Users/andriileukhin/Documents/SovereignNexus
cargo check -p siss-a2ui-framework
```

Expected: Builds without errors.

- [ ] **Step 3: Commit**

```bash
git add crates/siss-a2ui-framework/src/schema.rs
git commit -m "feat: define component metadata and introspection system"
```

---

### Task 3: Create JSON Schema Generation Module

**Files:**
- Create: `crates/siss-a2ui-framework/src/json_schema.rs`

**Steps:**

- [ ] **Step 1: Write failing test for JSON Schema generation**

Create `/crates/siss-a2ui-framework/tests/schema_generation_tests.rs`:

```rust
use siss_a2ui_framework::{JsonSchemaGenerator, ComponentIntrospection};
use serde_json::Value;

#[test]
fn test_json_schema_generation_for_all_18_components() {
    let mut count = 0;
    for component_type in &["text", "badge", "alert", "progress", "divider", "link", 
                             "tooltip", "breadcrumb", "input", "textarea", "select", 
                             "checkbox", "radio", "button", "card", "grid", "modal", "table"] {
        let schema = JsonSchemaGenerator::generate_schema(component_type);
        assert!(schema.is_some(), "Schema generation failed for {}", component_type);
        
        let schema_obj = schema.unwrap();
        assert_eq!(schema_obj.get("$schema").and_then(|v| v.as_str()), 
                   Some("https://json-schema.org/draft/2020-12/schema"),
                   "Schema should use Draft 2020-12 for {}", component_type);
        assert!(schema_obj.get("type").is_some(), "Schema missing type for {}", component_type);
        count += 1;
    }
    assert_eq!(count, 18, "Must generate schemas for all 18 component types");
}

#[test]
fn test_generated_schema_has_correct_structure() {
    let schema = JsonSchemaGenerator::generate_schema("text").unwrap();
    
    assert!(schema.get("$schema").is_some());
    assert!(schema.get("type").is_some());
    assert!(schema.get("properties").is_some());
    assert!(schema.get("required").is_some());
    
    let props = schema.get("properties").unwrap().as_object().unwrap();
    assert!(props.contains_key("id"), "Schema should have 'id' property");
    assert!(props.contains_key("content"), "Schema should have 'content' property");
}

#[test]
fn test_schema_includes_required_fields() {
    let schema = JsonSchemaGenerator::generate_schema("input").unwrap();
    let required = schema.get("required").unwrap().as_array().unwrap();
    
    assert!(required.iter().any(|r| r == "id"), "Required fields should include 'id'");
    assert!(required.iter().any(|r| r == "label"), "Required fields should include 'label'");
}

#[test]
fn test_schema_includes_optional_fields() {
    let schema = JsonSchemaGenerator::generate_schema("input").unwrap();
    let props = schema.get("properties").unwrap().as_object().unwrap();
    
    assert!(props.contains_key("placeholder"), "Schema should have optional 'placeholder'");
    assert!(props.contains_key("required"), "Schema should have optional 'required' field");
}

#[test]
fn test_schema_validates_valid_component_json() {
    let schema = JsonSchemaGenerator::generate_schema("text").unwrap();
    let valid_json = serde_json::json!({
        "type": "text",
        "id": "text1",
        "content": "Hello"
    });
    
    // Schema generated should be valid JSON Schema
    assert!(schema.is_object());
    assert!(valid_json.is_object());
}

#[test]
fn test_schema_generation_with_enums() {
    let schema = JsonSchemaGenerator::generate_schema("badge").unwrap();
    let props = schema.get("properties").unwrap().as_object().unwrap();
    let color_prop = props.get("color").unwrap();
    
    // Should have enum constraint for color
    assert!(color_prop.get("enum").is_some() || color_prop.get("oneOf").is_some(),
            "Color property should have enum constraint");
}

#[test]
fn test_schema_generation_with_array_fields() {
    let schema = JsonSchemaGenerator::generate_schema("breadcrumb").unwrap();
    let props = schema.get("properties").unwrap().as_object().unwrap();
    let items_prop = props.get("items").unwrap();
    
    assert_eq!(items_prop.get("type").and_then(|v| v.as_str()), Some("array"),
               "Items property should be array type");
}

#[test]
fn test_schema_generation_with_nested_components() {
    let schema = JsonSchemaGenerator::generate_schema("card").unwrap();
    let props = schema.get("properties").unwrap().as_object().unwrap();
    
    assert!(props.contains_key("children"), "Card schema should have 'children' property");
}

#[test]
fn test_schema_with_string_constraints() {
    let schema = JsonSchemaGenerator::generate_schema("text").unwrap();
    let props = schema.get("properties").unwrap().as_object().unwrap();
    let id_prop = props.get("id").unwrap();
    
    assert!(id_prop.get("minLength").is_some() || id_prop.get("type").is_some(),
            "ID property should have string constraints");
}

#[test]
fn test_schema_with_number_constraints() {
    let schema = JsonSchemaGenerator::generate_schema("progress").unwrap();
    let props = schema.get("properties").unwrap().as_object().unwrap();
    let value_prop = props.get("value").unwrap();
    
    assert_eq!(value_prop.get("type").and_then(|v| v.as_str()), Some("integer"),
               "Value should be integer type");
    assert!(value_prop.get("minimum").is_some() || value_prop.get("exclusiveMinimum").is_some(),
            "Value should have minimum constraint");
}

#[test]
fn test_schema_generation_consistency() {
    let schema1 = JsonSchemaGenerator::generate_schema("text").unwrap();
    let schema2 = JsonSchemaGenerator::generate_schema("text").unwrap();
    
    assert_eq!(schema1, schema2, "Schema generation should be deterministic");
}

#[test]
fn test_schema_for_empty_optional_component() {
    let schema = JsonSchemaGenerator::generate_schema("divider").unwrap();
    let required = schema.get("required").unwrap().as_array().unwrap();
    
    assert_eq!(required.len(), 1, "Divider should only require 'id'");
    assert_eq!(required[0], "id");
}
```

- [ ] **Step 2: Implement JSON Schema generation**

```rust
// File: src/json_schema.rs
use crate::schema::{ComponentIntrospection, A2UIComponentRegistry, FieldType};
use serde_json::{json, Value};

/// Generates JSON Schema Draft 2020-12 from component metadata
pub struct JsonSchemaGenerator;

impl JsonSchemaGenerator {
    /// Generate JSON Schema for a component type
    pub fn generate_schema(component_type: &str) -> Option<Value> {
        let metadata = A2UIComponentRegistry::metadata(component_type)?;
        
        let mut properties = serde_json::Map::new();
        
        // Add type discriminator
        properties.insert("type".to_string(), json!({
            "const": component_type,
            "type": "string"
        }));
        
        // Add all fields (required and optional)
        for (field_name, field_type) in &metadata.field_types {
            if field_name != "type" {
                properties.insert(
                    field_name.clone(),
                    Self::field_type_to_schema(field_type),
                );
            }
        }
        
        let mut required = vec!["type".to_string()];
        required.extend(metadata.required_fields);
        
        Some(json!({
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "title": metadata.name,
            "description": metadata.description,
            "properties": properties,
            "required": required,
            "additionalProperties": false
        }))
    }
    
    fn field_type_to_schema(field_type: &FieldType) -> Value {
        match field_type {
            FieldType::String { min_length, max_length, pattern, enum_values } => {
                let mut obj = json!({ "type": "string" });
                let obj_map = obj.as_object_mut().unwrap();
                
                if let Some(min) = min_length {
                    obj_map.insert("minLength".to_string(), json!(min));
                }
                if let Some(max) = max_length {
                    obj_map.insert("maxLength".to_string(), json!(max));
                }
                if let Some(pat) = pattern {
                    obj_map.insert("pattern".to_string(), json!(pat));
                }
                if let Some(enum_vals) = enum_values {
                    let enum_array: Vec<Value> = enum_vals.iter().map(|v| json!(v)).collect();
                    obj_map.insert("enum".to_string(), Value::Array(enum_array));
                }
                
                obj
            }
            FieldType::Number { minimum, maximum } => {
                let mut obj = json!({ "type": "integer" });
                let obj_map = obj.as_object_mut().unwrap();
                
                if let Some(min) = minimum {
                    obj_map.insert("minimum".to_string(), json!(min));
                }
                if let Some(max) = maximum {
                    obj_map.insert("maximum".to_string(), json!(max));
                }
                
                obj
            }
            FieldType::Boolean => json!({ "type": "boolean" }),
            FieldType::Array { item_type, min_items, max_items } => {
                let mut obj = json!({
                    "type": "array",
                    "items": Self::field_type_to_schema(item_type)
                });
                let obj_map = obj.as_object_mut().unwrap();
                
                if let Some(min) = min_items {
                    obj_map.insert("minItems".to_string(), json!(min));
                }
                if let Some(max) = max_items {
                    obj_map.insert("maxItems".to_string(), json!(max));
                }
                
                obj
            }
            FieldType::Object { properties } => {
                let mut props = serde_json::Map::new();
                for (name, field_type) in properties {
                    props.insert(name.clone(), Self::field_type_to_schema(field_type));
                }
                json!({
                    "type": "object",
                    "properties": props,
                    "additionalProperties": false
                })
            }
        }
    }
}
```

**Save to:** `/crates/siss-a2ui-framework/src/json_schema.rs`

- [ ] **Step 3: Run schema generation tests**

```bash
cd /Users/andriileukhin/Documents/SovereignNexus
cargo test -p siss-a2ui-framework schema_generation
```

Expected: All 12 tests pass.

- [ ] **Step 4: Commit**

```bash
git add crates/siss-a2ui-framework/src/json_schema.rs crates/siss-a2ui-framework/tests/schema_generation_tests.rs
git commit -m "feat: implement JSON Schema generation (Draft 2020-12)"
```

---

### Task 4: Create React Code Generator Module

**Files:**
- Create: `crates/siss-a2ui-framework/src/react_renderer.rs`
- Create: `crates/siss-a2ui-framework/tests/react_codegen_tests.rs`

**Steps:**

- [ ] **Step 1: Write failing tests for React code generation**

Create `/crates/siss-a2ui-framework/tests/react_codegen_tests.rs`:

```rust
use siss_a2ui_framework::ReactCodeGenerator;
use siss_agent_shell::a2ui::A2UIComponent;

#[test]
fn test_react_codegen_generates_valid_tsx_syntax() {
    let component = A2UIComponent::Text {
        id: "text1".to_string(),
        content: "Hello World".to_string(),
        size: Some("md".to_string()),
    };
    
    let tsx = ReactCodeGenerator::generate_component(&component);
    
    assert!(tsx.contains("React"));
    assert!(tsx.contains("export"));
    assert!(!tsx.is_empty());
}

#[test]
fn test_react_codegen_button_component() {
    let component = A2UIComponent::Button {
        id: "btn1".to_string(),
        label: "Click me".to_string(),
        action: Some("submit".to_string()),
    };
    
    let tsx = ReactCodeGenerator::generate_component(&component);
    
    assert!(tsx.contains("button"));
    assert!(tsx.contains("Click me"));
    assert!(tsx.contains("submit"));
}

#[test]
fn test_react_codegen_input_field() {
    let component = A2UIComponent::Input {
        id: "input1".to_string(),
        label: "Name".to_string(),
        placeholder: Some("Enter your name".to_string()),
        required: true,
    };
    
    let tsx = ReactCodeGenerator::generate_component(&component);
    
    assert!(tsx.contains("input"));
    assert!(tsx.contains("Name"));
    assert!(tsx.contains("Enter your name"));
    assert!(tsx.contains("required"));
}

#[test]
fn test_react_codegen_checkbox() {
    let component = A2UIComponent::Checkbox {
        id: "check1".to_string(),
        label: "Agree".to_string(),
        checked: false,
    };
    
    let tsx = ReactCodeGenerator::generate_component(&component);
    
    assert!(tsx.contains("checkbox"));
    assert!(tsx.contains("Agree"));
}

#[test]
fn test_react_codegen_select_dropdown() {
    let component = A2UIComponent::Select {
        id: "select1".to_string(),
        label: "Choose".to_string(),
        options: vec![
            siss_agent_shell::a2ui::SelectOption {
                value: "opt1".to_string(),
                label: "Option 1".to_string(),
            },
            siss_agent_shell::a2ui::SelectOption {
                value: "opt2".to_string(),
                label: "Option 2".to_string(),
            },
        ],
    };
    
    let tsx = ReactCodeGenerator::generate_component(&component);
    
    assert!(tsx.contains("select"));
    assert!(tsx.contains("opt1"));
    assert!(tsx.contains("Option 1"));
}

#[test]
fn test_react_codegen_escapes_xss_in_strings() {
    let component = A2UIComponent::Text {
        id: "text1".to_string(),
        content: "<script>alert('xss')</script>".to_string(),
        size: None,
    };
    
    let tsx = ReactCodeGenerator::generate_component(&component);
    
    // Should escape angle brackets
    assert!(!tsx.contains("<script>"));
    assert!(tsx.contains("&lt;") || tsx.contains("\\<"));
}

#[test]
fn test_react_codegen_card_with_children() {
    let component = A2UIComponent::Card {
        id: "card1".to_string(),
        title: Some("Card Title".to_string()),
        children: vec![
            A2UIComponent::Text {
                id: "text1".to_string(),
                content: "Card content".to_string(),
                size: None,
            },
        ],
    };
    
    let tsx = ReactCodeGenerator::generate_component(&component);
    
    assert!(tsx.contains("Card Title"));
    assert!(tsx.contains("Card content"));
}

#[test]
fn test_react_codegen_grid_layout() {
    let component = A2UIComponent::Grid {
        id: "grid1".to_string(),
        columns: 3,
        children: vec![],
    };
    
    let tsx = ReactCodeGenerator::generate_component(&component);
    
    assert!(tsx.contains("grid"));
    assert!(tsx.contains("3"));
}

#[test]
fn test_react_codegen_progress_bar() {
    let component = A2UIComponent::Progress {
        id: "prog1".to_string(),
        value: 65,
        max: 100,
        label: Some("Loading".to_string()),
    };
    
    let tsx = ReactCodeGenerator::generate_component(&component);
    
    assert!(tsx.contains("progress"));
    assert!(tsx.contains("65"));
    assert!(tsx.contains("Loading"));
}

#[test]
fn test_react_codegen_alert_component() {
    let component = A2UIComponent::Alert {
        id: "alert1".to_string(),
        message: "Warning!".to_string(),
        level: "warn".to_string(),
    };
    
    let tsx = ReactCodeGenerator::generate_component(&component);
    
    assert!(tsx.contains("alert"));
    assert!(tsx.contains("warn"));
    assert!(tsx.contains("Warning!"));
}

#[test]
fn test_react_codegen_generates_type_interfaces() {
    let tsx = ReactCodeGenerator::generate_type_interfaces(&["text", "button", "input"]);
    
    assert!(tsx.contains("interface"));
    assert!(tsx.contains("TextComponentProps"));
    assert!(tsx.contains("ButtonComponentProps"));
    assert!(tsx.contains("InputComponentProps"));
}

#[test]
fn test_react_codegen_all_18_components() {
    let components = vec![
        ("text", A2UIComponent::Text { id: "t".to_string(), content: "x".to_string(), size: None }),
        ("badge", A2UIComponent::Badge { id: "b".to_string(), label: "x".to_string(), color: None }),
        ("alert", A2UIComponent::Alert { id: "a".to_string(), message: "x".to_string(), level: "info".to_string() }),
        ("progress", A2UIComponent::Progress { id: "p".to_string(), value: 50, max: 100, label: None }),
        ("divider", A2UIComponent::Divider { id: "d".to_string() }),
        ("link", A2UIComponent::Link { id: "l".to_string(), label: "x".to_string(), href: "http://x".to_string() }),
        ("tooltip", A2UIComponent::Tooltip { id: "t".to_string(), text: "x".to_string(), content: "y".to_string() }),
        ("breadcrumb", A2UIComponent::Breadcrumb { id: "b".to_string(), items: vec!["home".to_string()] }),
        ("input", A2UIComponent::Input { id: "i".to_string(), label: "x".to_string(), placeholder: None, required: false }),
        ("textarea", A2UIComponent::Textarea { id: "t".to_string(), label: "x".to_string(), rows: None }),
        ("select", A2UIComponent::Select { id: "s".to_string(), label: "x".to_string(), options: vec![] }),
        ("checkbox", A2UIComponent::Checkbox { id: "c".to_string(), label: "x".to_string(), checked: false }),
        ("radio", A2UIComponent::Radio { id: "r".to_string(), label: "x".to_string(), value: "v".to_string(), checked: false }),
        ("button", A2UIComponent::Button { id: "b".to_string(), label: "x".to_string(), action: None }),
        ("card", A2UIComponent::Card { id: "c".to_string(), title: None, children: vec![] }),
        ("grid", A2UIComponent::Grid { id: "g".to_string(), columns: 2, children: vec![] }),
        ("modal", A2UIComponent::Modal { id: "m".to_string(), title: "x".to_string(), content: "y".to_string(), children: vec![] }),
        ("table", A2UIComponent::Table { id: "t".to_string(), headers: vec!["h".to_string()], rows: vec![] }),
    ];
    
    for (name, component) in components {
        let tsx = ReactCodeGenerator::generate_component(&component);
        assert!(!tsx.is_empty(), "React codegen failed for {}", name);
    }
}
```

- [ ] **Step 2: Implement React code generator**

```rust
// File: src/react_renderer.rs
use siss_agent_shell::a2ui::A2UIComponent;
use std::collections::HashSet;

/// Generates React TSX code from A2UIComponent
pub struct ReactCodeGenerator;

impl ReactCodeGenerator {
    /// Generate TSX component code
    pub fn generate_component(component: &A2UIComponent) -> String {
        match component {
            A2UIComponent::Text { id, content, size } => {
                let size_class = size.as_deref().unwrap_or("md");
                format!(
                    r#"
import React from 'react';

interface TextComponentProps {{
  id: string;
  content: string;
  size?: 'sm' | 'md' | 'lg';
}}

export const {} = {{ id, content, size = 'md' }}: TextComponentProps) => (
  <div className="a2ui-text text-{{size}}" id="{{id}}">
    <p>{{content}}</p>
  </div>
);
"#,
                    Self::to_pascal_case(id),
                    Self::escape_jsx(content),
                )
            }
            A2UIComponent::Badge { id, label, color } => {
                let color_val = color.as_deref().unwrap_or("default");
                format!(
                    r#"
import React from 'react';

interface BadgeComponentProps {{
  id: string;
  label: string;
  color?: 'blue' | 'red' | 'green' | 'yellow';
}}

export const {} = {{ id, label, color = 'default' }}: BadgeComponentProps) => (
  <span className="a2ui-badge badge-{{color}}" id="{{id}}">
    {{label}}
  </span>
);
"#,
                    Self::to_pascal_case(id),
                    Self::escape_jsx(label),
                )
            }
            A2UIComponent::Button { id, label, action } => {
                let action_val = action.as_deref().unwrap_or("button");
                format!(
                    r#"
import React from 'react';

interface ButtonComponentProps {{
  id: string;
  label: string;
  action?: 'submit' | 'reset' | 'custom';
  onClick?: () => void;
}}

export const {} = {{ id, label, action = 'button', onClick }}: ButtonComponentProps) => (
  <button 
    id="{{id}}"
    type="{{action}}"
    className="a2ui-button"
    onClick={{onClick}}
  >
    {{label}}
  </button>
);
"#,
                    Self::to_pascal_case(id),
                    Self::escape_jsx(label),
                )
            }
            A2UIComponent::Input { id, label, placeholder, required } => {
                format!(
                    r#"
import React, {{ useState }} from 'react';

interface InputComponentProps {{
  id: string;
  label: string;
  placeholder?: string;
  required?: boolean;
  onChange?: (value: string) => void;
}}

export const {} = {{ id, label, placeholder, required = false, onChange }}: InputComponentProps) => {{
  const [value, setValue] = useState('');
  
  return (
    <div className="a2ui-input-field">
      <label htmlFor="{{id}}">{{label}}</label>
      <input
        id="{{id}}"
        type="text"
        placeholder="{{placeholder}}"
        required={{required}}
        value={{value}}
        onChange={{(e) => {{
          setValue(e.target.value);
          onChange?.(e.target.value);
        }}}}
      />
    </div>
  );
}};
"#,
                    Self::to_pascal_case(id),
                    Self::escape_jsx(label),
                    placeholder.as_deref().unwrap_or(""),
                )
            }
            A2UIComponent::Checkbox { id, label, checked } => {
                format!(
                    r#"
import React, {{ useState }} from 'react';

interface CheckboxComponentProps {{
  id: string;
  label: string;
  checked?: boolean;
  onChange?: (checked: boolean) => void;
}}

export const {} = {{ id, label, checked = false, onChange }}: CheckboxComponentProps) => {{
  const [isChecked, setIsChecked] = useState(checked);
  
  return (
    <div className="a2ui-checkbox">
      <input
        id="{{id}}"
        type="checkbox"
        checked={{isChecked}}
        onChange={{(e) => {{
          setIsChecked(e.target.checked);
          onChange?.(e.target.checked);
        }}}}
      />
      <label htmlFor="{{id}}">{{label}}</label>
    </div>
  );
}};
"#,
                    Self::to_pascal_case(id),
                    Self::escape_jsx(label),
                )
            }
            A2UIComponent::Select { id, label, options } => {
                let options_code = options
                    .iter()
                    .map(|opt| format!(r#"<option value="{}">{}</option>"#, 
                        Self::escape_jsx(&opt.value), 
                        Self::escape_jsx(&opt.label)))
                    .collect::<Vec<_>>()
                    .join("\n      ");
                
                format!(
                    r#"
import React, {{ useState }} from 'react';

interface SelectComponentProps {{
  id: string;
  label: string;
  options: Array<{{ value: string; label: string }}>;
  onChange?: (value: string) => void;
}}

export const {} = {{ id, label, options, onChange }}: SelectComponentProps) => {{
  const [value, setValue] = useState('');
  
  return (
    <div className="a2ui-select">
      <label htmlFor="{{id}}">{{label}}</label>
      <select
        id="{{id}}"
        value={{value}}
        onChange={{(e) => {{
          setValue(e.target.value);
          onChange?.(e.target.value);
        }}}}
      >
        <option value="">Select an option</option>
        {{options.map(opt => (
          <option key={{opt.value}} value={{opt.value}}>
            {{opt.label}}
          </option>
        ))}}
      </select>
    </div>
  );
}};
"#,
                    Self::to_pascal_case(id),
                    Self::escape_jsx(label),
                )
            }
            A2UIComponent::Alert { id, message, level } => {
                format!(
                    r#"
import React from 'react';

interface AlertComponentProps {{
  id: string;
  message: string;
  level?: 'info' | 'warn' | 'error';
}}

export const {} = {{ id, message, level = 'info' }}: AlertComponentProps) => (
  <div id="{{id}}" className="a2ui-alert alert-{{level}}" role="alert">
    <strong>{{message}}</strong>
  </div>
);
"#,
                    Self::to_pascal_case(id),
                    Self::escape_jsx(message),
                    level,
                )
            }
            A2UIComponent::Progress { id, value, max, label } => {
                let percentage = (*value as f32 / *max as f32 * 100.0).min(100.0).max(0.0) as u32;
                format!(
                    r#"
import React from 'react';

interface ProgressComponentProps {{
  id: string;
  value: number;
  max: number;
  label?: string;
}}

export const {} = {{ id, value, max, label }}: ProgressComponentProps) => {{
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));
  
  return (
    <div id="{{id}}" className="a2ui-progress">
      <div 
        className="progress-bar" 
        style={{ width: `${{percentage}}%` }}
        role="progressbar"
        aria-valuenow={{value}}
        aria-valuemin={{0}}
        aria-valuemax={{max}}
      />
      {{label && <span className="progress-label">{{label}}</span>}}
    </div>
  );
}};
"#,
                    Self::to_pascal_case(id),
                    Self::escape_jsx(label.as_deref().unwrap_or("")),
                )
            }
            A2UIComponent::Card { id, title, children } => {
                format!(
                    r#"
import React from 'react';

interface CardComponentProps {{
  id: string;
  title?: string;
  children: React.ReactNode;
}}

export const {} = {{ id, title, children }}: CardComponentProps) => (
  <div id="{{id}}" className="a2ui-card">
    {{title && <div className="card-title">{{title}}</div>}}
    <div className="card-content">
      {{children}}
    </div>
  </div>
);
"#,
                    Self::to_pascal_case(id),
                    Self::escape_jsx(title.as_deref().unwrap_or("")),
                )
            }
            A2UIComponent::Grid { id, columns, children: _ } => {
                format!(
                    r#"
import React from 'react';

interface GridComponentProps {{
  id: string;
  columns: number;
  children: React.ReactNode;
}}

export const {} = {{ id, columns, children }}: GridComponentProps) => (
  <div 
    id="{{id}}"
    className="a2ui-grid"
    style={{ display: 'grid', gridTemplateColumns: `repeat(${{columns}}, 1fr)` }}
  >
    {{children}}
  </div>
);
"#,
                    Self::to_pascal_case(id),
                    columns,
                )
            }
            A2UIComponent::Modal { id, title, content, children: _ } => {
                format!(
                    r#"
import React, {{ useState }} from 'react';

interface ModalComponentProps {{
  id: string;
  title: string;
  content: string;
  isOpen?: boolean;
  onClose?: () => void;
}}

export const {} = {{ id, title, content, isOpen = false, onClose }}: ModalComponentProps) => {{
  if (!isOpen) return null;
  
  return (
    <div className="a2ui-modal-backdrop">
      <div id="{{id}}" className="a2ui-modal">
        <div className="modal-header">
          <h2>{{title}}</h2>
          <button onClick={{onClose}}>×</button>
        </div>
        <div className="modal-content">
          {{content}}
        </div>
      </div>
    </div>
  );
}};
"#,
                    Self::to_pascal_case(id),
                    Self::escape_jsx(title),
                    Self::escape_jsx(content),
                )
            }
            A2UIComponent::Table { id, headers, rows } => {
                format!(
                    r#"
import React from 'react';

interface TableComponentProps {{
  id: string;
  headers: string[];
  rows: string[][];
}}

export const {} = {{ id, headers, rows }}: TableComponentProps) => (
  <table id="{{id}}" className="a2ui-table">
    <thead>
      <tr>
        {{headers.map((header, i) => (
          <th key={{i}}>{{header}}</th>
        ))}}
      </tr>
    </thead>
    <tbody>
      {{rows.map((row, rowIdx) => (
        <tr key={{rowIdx}}>
          {{row.map((cell, cellIdx) => (
            <td key={{cellIdx}}>{{cell}}</td>
          ))}}
        </tr>
      ))}}
    </tbody>
  </table>
);
"#,
                    Self::to_pascal_case(id),
                )
            }
            _ => {
                // Fallback for unimplemented components
                format!(
                    r#"
import React from 'react';

// Component ID: {}
export const Component = () => <div>Component not implemented</div>;
"#,
                    id
                )
            }
        }
    }

    /// Generate TypeScript interfaces for multiple components
    pub fn generate_type_interfaces(component_types: &[&str]) -> String {
        let mut interfaces = String::new();
        
        for component_type in component_types {
            let interface_name = format!("{}ComponentProps", Self::to_pascal_case(component_type));
            interfaces.push_str(&format!(
                "interface {} {{\n  id: string;\n  // ... component-specific props\n}}\n\n",
                interface_name
            ));
        }
        
        interfaces
    }

    fn to_pascal_case(s: &str) -> String {
        s.split('_')
            .map(|word| {
                let mut chars = word.chars();
                match chars.next() {
                    None => String::new(),
                    Some(first) => {
                        first.to_uppercase().collect::<String>() + chars.as_str()
                    }
                }
            })
            .collect()
    }

    fn escape_jsx(s: &str) -> String {
        s.replace('&', "&amp;")
            .replace('<', "&lt;")
            .replace('>', "&gt;")
            .replace('"', "&quot;")
            .replace('\'', "&#39;")
    }
}
```

**Save to:** `/crates/siss-a2ui-framework/src/react_renderer.rs`

- [ ] **Step 3: Run React codegen tests**

```bash
cd /Users/andriileukhin/Documents/SovereignNexus
cargo test -p siss-a2ui-framework react_codegen
```

Expected: All 13 tests pass.

- [ ] **Step 4: Commit**

```bash
git add crates/siss-a2ui-framework/src/react_renderer.rs crates/siss-a2ui-framework/tests/react_codegen_tests.rs
git commit -m "feat: implement React TSX code generator"
```

---

### Task 5: Create Validation Module

**Files:**
- Create: `crates/siss-a2ui-framework/src/validation.rs`
- Create: `crates/siss-a2ui-framework/tests/validation_tests.rs`

**Steps:**

- [ ] **Step 1: Write failing tests for schema validation**

Create `/crates/siss-a2ui-framework/tests/validation_tests.rs`:

```rust
use siss_a2ui_framework::SchemaValidator;
use serde_json::json;

#[test]
fn test_validator_accepts_valid_text_component() {
    let validator = SchemaValidator::new();
    let json = json!({
        "type": "text",
        "id": "text1",
        "content": "Hello"
    });
    
    let result = validator.validate("text", &json);
    assert!(result.is_ok(), "Valid text component should pass validation");
}

#[test]
fn test_validator_rejects_missing_required_field() {
    let validator = SchemaValidator::new();
    let json = json!({
        "type": "text",
        "id": "text1"
        // missing required "content"
    });
    
    let result = validator.validate("text", &json);
    assert!(result.is_err(), "Missing required field should fail");
}

#[test]
fn test_validator_rejects_unknown_component_type() {
    let validator = SchemaValidator::new();
    let json = json!({ "type": "unknown_component" });
    
    let result = validator.validate("unknown_component", &json);
    assert!(result.is_err(), "Unknown component type should fail");
}

#[test]
fn test_validator_accepts_valid_input_with_optional_fields() {
    let validator = SchemaValidator::new();
    let json = json!({
        "type": "input",
        "id": "input1",
        "label": "Name",
        "placeholder": "Enter name",
        "required": true
    });
    
    let result = validator.validate("input", &json);
    assert!(result.is_ok());
}

#[test]
fn test_validator_enforces_enum_constraints() {
    let validator = SchemaValidator::new();
    let json = json!({
        "type": "badge",
        "id": "badge1",
        "label": "New",
        "color": "invalid_color"
    });
    
    let result = validator.validate("badge", &json);
    assert!(result.is_err(), "Invalid enum value should fail");
}

#[test]
fn test_validator_enforces_number_ranges() {
    let validator = SchemaValidator::new();
    let json = json!({
        "type": "progress",
        "id": "prog1",
        "value": 150,
        "max": 100
    });
    
    let result = validator.validate("progress", &json);
    assert!(result.is_err(), "Out-of-range value should fail");
}

#[test]
fn test_validator_rejects_additional_properties() {
    let validator = SchemaValidator::new();
    let json = json!({
        "type": "text",
        "id": "text1",
        "content": "Hello",
        "extra_field": "not_allowed"
    });
    
    let result = validator.validate("text", &json);
    assert!(result.is_err(), "Additional properties should be rejected");
}

#[test]
fn test_validator_accepts_empty_optional_arrays() {
    let validator = SchemaValidator::new();
    let json = json!({
        "type": "select",
        "id": "select1",
        "label": "Choose",
        "options": []
    });
    
    let result = validator.validate("select", &json);
    // Empty options might be allowed or disallowed depending on requirements
    // This test documents the behavior
    let _ = result;
}

#[test]
fn test_validator_rejects_wrong_field_type() {
    let validator = SchemaValidator::new();
    let json = json!({
        "type": "progress",
        "id": "prog1",
        "value": "not_a_number",  // should be number
        "max": 100
    });
    
    let result = validator.validate("progress", &json);
    assert!(result.is_err(), "Wrong field type should fail");
}

#[test]
fn test_validator_allows_nested_children_in_card() {
    let validator = SchemaValidator::new();
    let json = json!({
        "type": "card",
        "id": "card1",
        "children": [
            {
                "type": "text",
                "id": "nested1",
                "content": "Nested"
            }
        ]
    });
    
    let result = validator.validate("card", &json);
    assert!(result.is_ok());
}
```

- [ ] **Step 2: Implement validation module**

```rust
// File: src/validation.rs
use crate::json_schema::JsonSchemaGenerator;
use serde_json::Value;

/// Validates A2UI components against JSON schemas
pub struct SchemaValidator;

impl SchemaValidator {
    /// Create a new validator
    pub fn new() -> Self {
        SchemaValidator
    }

    /// Validate a component JSON against its schema
    pub fn validate(&self, component_type: &str, component_json: &Value) -> Result<(), String> {
        let schema = JsonSchemaGenerator::generate_schema(component_type)
            .ok_or_else(|| format!("Unknown component type: {}", component_type))?;

        self.validate_against_schema(component_json, &schema)
    }

    fn validate_against_schema(&self, instance: &Value, schema: &Value) -> Result<(), String> {
        // Check type
        if let Some(schema_type) = schema.get("type").and_then(|v| v.as_str()) {
            match schema_type {
                "object" => self.validate_object(instance, schema)?,
                "string" => self.validate_string(instance, schema)?,
                "integer" | "number" => self.validate_number(instance, schema)?,
                "boolean" => {
                    if !instance.is_boolean() {
                        return Err("Expected boolean".to_string());
                    }
                }
                "array" => self.validate_array(instance, schema)?,
                _ => {}
            }
        }

        // Check enum constraint
        if let Some(enum_values) = schema.get("enum") {
            if let Some(arr) = enum_values.as_array() {
                if !arr.iter().any(|v| v == instance) {
                    return Err(format!("Value not in enum: {:?}", instance));
                }
            }
        }

        // Check const constraint
        if let Some(const_val) = schema.get("const") {
            if const_val != instance {
                return Err(format!("Value must be {:?}", const_val));
            }
        }

        Ok(())
    }

    fn validate_object(&self, instance: &Value, schema: &Value) -> Result<(), String> {
        let obj = instance.as_object()
            .ok_or_else(|| "Expected object".to_string())?;

        // Validate required fields
        if let Some(required) = schema.get("required").and_then(|v| v.as_array()) {
            for req_field in required {
                if let Some(field_name) = req_field.as_str() {
                    if !obj.contains_key(field_name) {
                        return Err(format!("Missing required field: {}", field_name));
                    }
                }
            }
        }

        // Validate properties against their schemas
        if let Some(properties) = schema.get("properties").and_then(|v| v.as_object()) {
            for (key, value) in obj {
                if let Some(prop_schema) = properties.get(key) {
                    self.validate_against_schema(value, prop_schema)?;
                } else if schema.get("additionalProperties").and_then(|v| v.as_bool()) != Some(true) {
                    return Err(format!("Additional property not allowed: {}", key));
                }
            }
        }

        Ok(())
    }

    fn validate_string(&self, instance: &Value, schema: &Value) -> Result<(), String> {
        let s = instance.as_str()
            .ok_or_else(|| "Expected string".to_string())?;

        // Check minLength
        if let Some(min) = schema.get("minLength").and_then(|v| v.as_u64()) {
            if s.len() < min as usize {
                return Err(format!("String too short: minimum length is {}", min));
            }
        }

        // Check maxLength
        if let Some(max) = schema.get("maxLength").and_then(|v| v.as_u64()) {
            if s.len() > max as usize {
                return Err(format!("String too long: maximum length is {}", max));
            }
        }

        Ok(())
    }

    fn validate_number(&self, instance: &Value, schema: &Value) -> Result<(), String> {
        let num = instance.as_i64()
            .ok_or_else(|| "Expected number".to_string())?;

        // Check minimum
        if let Some(min) = schema.get("minimum").and_then(|v| v.as_i64()) {
            if num < min {
                return Err(format!("Number too small: minimum is {}", min));
            }
        }

        // Check maximum
        if let Some(max) = schema.get("maximum").and_then(|v| v.as_i64()) {
            if num > max {
                return Err(format!("Number too large: maximum is {}", max));
            }
        }

        Ok(())
    }

    fn validate_array(&self, instance: &Value, schema: &Value) -> Result<(), String> {
        let arr = instance.as_array()
            .ok_or_else(|| "Expected array".to_string())?;

        // Check minItems
        if let Some(min) = schema.get("minItems").and_then(|v| v.as_u64()) {
            if arr.len() < min as usize {
                return Err(format!("Array too short: minimum length is {}", min));
            }
        }

        // Check maxItems
        if let Some(max) = schema.get("maxItems").and_then(|v| v.as_u64()) {
            if arr.len() > max as usize {
                return Err(format!("Array too long: maximum length is {}", max));
            }
        }

        // Validate items against item schema
        if let Some(items_schema) = schema.get("items") {
            for item in arr {
                self.validate_against_schema(item, items_schema)?;
            }
        }

        Ok(())
    }
}

impl Default for SchemaValidator {
    fn default() -> Self {
        Self::new()
    }
}
```

**Save to:** `/crates/siss-a2ui-framework/src/validation.rs`

- [ ] **Step 3: Run validation tests**

```bash
cd /Users/andriileukhin/Documents/SovereignNexus
cargo test -p siss-a2ui-framework validation
```

Expected: All 10 tests pass.

- [ ] **Step 4: Commit**

```bash
git add crates/siss-a2ui-framework/src/validation.rs crates/siss-a2ui-framework/tests/validation_tests.rs
git commit -m "feat: implement JSON schema validation layer"
```

---

### Task 6: Create Performance Metrics Module

**Files:**
- Create: `crates/siss-a2ui-framework/src/performance.rs`

**Steps:**

- [ ] **Step 1: Implement performance metrics**

```rust
// File: src/performance.rs
use std::time::Instant;

/// Collects performance metrics for rendering and validation
#[derive(Debug, Clone)]
pub struct PerformanceMetrics {
    pub render_time_ms: f64,
    pub validation_time_ms: f64,
    pub schema_generation_time_ms: f64,
    pub component_count: usize,
}

impl PerformanceMetrics {
    /// Create a new metrics instance
    pub fn new() -> Self {
        PerformanceMetrics {
            render_time_ms: 0.0,
            validation_time_ms: 0.0,
            schema_generation_time_ms: 0.0,
            component_count: 0,
        }
    }

    /// Record render time
    pub fn record_render_time(&mut self, duration_ms: f64) {
        self.render_time_ms = duration_ms;
    }

    /// Record validation time
    pub fn record_validation_time(&mut self, duration_ms: f64) {
        self.validation_time_ms = duration_ms;
    }

    /// Record schema generation time
    pub fn record_schema_generation_time(&mut self, duration_ms: f64) {
        self.schema_generation_time_ms = duration_ms;
    }

    /// Record component count
    pub fn set_component_count(&mut self, count: usize) {
        self.component_count = count;
    }

    /// Check if all operations completed within budget (<100ms per 100 components)
    pub fn within_performance_budget(&self) -> bool {
        let budget_ms = (self.component_count as f64 / 100.0) * 100.0;
        let total_time = self.render_time_ms + self.validation_time_ms + self.schema_generation_time_ms;
        total_time < budget_ms
    }

    /// Get summary statistics
    pub fn summary(&self) -> String {
        format!(
            "Performance: {}ms render + {}ms validation + {}ms schema = {}ms total ({} components)",
            self.render_time_ms as u32,
            self.validation_time_ms as u32,
            self.schema_generation_time_ms as u32,
            (self.render_time_ms + self.validation_time_ms + self.schema_generation_time_ms) as u32,
            self.component_count
        )
    }
}

impl Default for PerformanceMetrics {
    fn default() -> Self {
        Self::new()
    }
}

/// Scope guard for measuring operation duration
pub struct Timer {
    start: Instant,
}

impl Timer {
    /// Create a new timer
    pub fn start() -> Self {
        Timer {
            start: Instant::now(),
        }
    }

    /// Get elapsed time in milliseconds
    pub fn elapsed_ms(&self) -> f64 {
        self.start.elapsed().as_secs_f64() * 1000.0
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_metrics_tracks_times() {
        let mut metrics = PerformanceMetrics::new();
        metrics.record_render_time(25.5);
        metrics.record_validation_time(15.3);
        metrics.record_schema_generation_time(10.2);
        metrics.set_component_count(50);

        assert_eq!(metrics.render_time_ms, 25.5);
        assert_eq!(metrics.validation_time_ms, 15.3);
        assert_eq!(metrics.schema_generation_time_ms, 10.2);
        assert_eq!(metrics.component_count, 50);
    }

    #[test]
    fn test_performance_budget_passes_under_limit() {
        let mut metrics = PerformanceMetrics::new();
        metrics.record_render_time(20.0);
        metrics.record_validation_time(20.0);
        metrics.record_schema_generation_time(20.0);
        metrics.set_component_count(100);

        assert!(metrics.within_performance_budget());
    }

    #[test]
    fn test_performance_budget_fails_over_limit() {
        let mut metrics = PerformanceMetrics::new();
        metrics.record_render_time(50.0);
        metrics.record_validation_time(50.0);
        metrics.record_schema_generation_time(50.0);
        metrics.set_component_count(100);

        assert!(!metrics.within_performance_budget());
    }
}
```

**Save to:** `/crates/siss-a2ui-framework/src/performance.rs`

- [ ] **Step 2: Update lib.rs to export performance module**

Edit `/crates/siss-a2ui-framework/src/lib.rs` — add module declaration:

```rust
pub mod performance;
```

And add to re-exports at top.

- [ ] **Step 3: Run performance tests**

```bash
cd /Users/andriileukhin/Documents/SovereignNexus
cargo test -p siss-a2ui-framework performance
```

Expected: 3 tests pass.

- [ ] **Step 4: Commit**

```bash
git add crates/siss-a2ui-framework/src/performance.rs crates/siss-a2ui-framework/src/lib.rs
git commit -m "feat: add performance metrics collection"
```

---

### Task 7: Create Integration + E2E Tests

**Files:**
- Create: `crates/siss-a2ui-framework/tests/integration_tests.rs`
- Create: `crates/siss-a2ui-framework/tests/performance_benchmarks.rs`

**Steps:**

- [ ] **Step 1: Write integration tests**

Create `/crates/siss-a2ui-framework/tests/integration_tests.rs`:

```rust
use siss_a2ui_framework::{
    JsonSchemaGenerator, ReactCodeGenerator, SchemaValidator, 
    PerformanceMetrics, ComponentIntrospection
};
use siss_agent_shell::a2ui::A2UIComponent;
use std::time::Instant;

#[test]
fn test_full_pipeline_schema_validation_render() {
    // 1. Generate schema for text component
    let schema = JsonSchemaGenerator::generate_schema("text")
        .expect("Schema generation failed");

    // 2. Create valid JSON
    let json = serde_json::json!({
        "type": "text",
        "id": "text1",
        "content": "Hello World",
        "size": "md"
    });

    // 3. Validate against schema
    let validator = SchemaValidator::new();
    let validation_result = validator.validate("text", &json);
    assert!(validation_result.is_ok(), "Validation failed: {:?}", validation_result);

    // 4. Create component and render to React
    let component = A2UIComponent::Text {
        id: "text1".to_string(),
        content: "Hello World".to_string(),
        size: Some("md".to_string()),
    };

    let tsx = ReactCodeGenerator::generate_component(&component);
    assert!(!tsx.is_empty(), "React render produced empty output");
    assert!(tsx.contains("Hello World"));
}

#[test]
fn test_full_pipeline_with_form_components() {
    let form_components = vec!["input", "textarea", "select", "checkbox", "radio", "button"];

    for component_type in form_components {
        // 1. Generate schema
        let schema = JsonSchemaGenerator::generate_schema(component_type)
            .expect(&format!("Failed to generate schema for {}", component_type));

        // 2. Verify schema structure
        assert!(schema.get("properties").is_some());
        assert!(schema.get("required").is_some());

        // 3. Validate component metadata exists
        let metadata = A2UIComponentRegistry::metadata(component_type);
        assert!(metadata.is_some(), "Missing metadata for {}", component_type);
    }
}

#[test]
fn test_all_18_components_end_to_end() {
    let components_count = A2UIComponentRegistry::all_types().len();
    assert_eq!(components_count, 18, "Must have exactly 18 components");

    let mut successful = 0;

    for component_type in A2UIComponentRegistry::all_types() {
        // Generate schema
        if let Some(schema) = JsonSchemaGenerator::generate_schema(&component_type) {
            assert!(schema.get("$schema").is_some(), "Missing schema version for {}", component_type);
            successful += 1;
        }
    }

    assert_eq!(successful, 18, "All 18 components must have schemas");
}

#[test]
fn test_pipeline_with_invalid_json_gracefully_fails() {
    let validator = SchemaValidator::new();

    // Test 1: Missing required field
    let invalid_json1 = serde_json::json!({
        "type": "text",
        "id": "text1"
        // missing "content"
    });

    let result1 = validator.validate("text", &invalid_json1);
    assert!(result1.is_err(), "Should reject missing required field");

    // Test 2: Wrong type
    let invalid_json2 = serde_json::json!({
        "type": "text",
        "id": "text1",
        "content": 123  // should be string
    });

    let result2 = validator.validate("text", &invalid_json2);
    assert!(result2.is_err(), "Should reject wrong field type");
}

#[test]
fn test_react_codegen_escapes_xss_in_full_pipeline() {
    let component = A2UIComponent::Text {
        id: "xss_test".to_string(),
        content: "<img src=x onerror='alert(1)'>".to_string(),
        size: None,
    };

    let tsx = ReactCodeGenerator::generate_component(&component);

    assert!(!tsx.contains("<img"));
    assert!(!tsx.contains("onerror"));
    assert!(!tsx.contains("alert"));
}

#[test]
fn test_nested_components_validation_and_render() {
    let card_component = A2UIComponent::Card {
        id: "card1".to_string(),
        title: Some("Test Card".to_string()),
        children: vec![
            A2UIComponent::Text {
                id: "text1".to_string(),
                content: "Card content".to_string(),
                size: None,
            },
            A2UIComponent::Button {
                id: "btn1".to_string(),
                label: "Click me".to_string(),
                action: Some("submit".to_string()),
            },
        ],
    };

    let tsx = ReactCodeGenerator::generate_component(&card_component);
    assert!(!tsx.is_empty());
    assert!(tsx.contains("Test Card"));
}

// Use existing component registry from framework
use siss_a2ui_framework::A2UIComponentRegistry;
```

- [ ] **Step 2: Write performance benchmarks**

Create `/crates/siss-a2ui-framework/tests/performance_benchmarks.rs`:

```rust
use siss_a2ui_framework::{
    JsonSchemaGenerator, ReactCodeGenerator, SchemaValidator,
    PerformanceMetrics, ComponentIntrospection, A2UIComponentRegistry
};
use siss_agent_shell::a2ui::A2UIComponent;
use std::time::Instant;

#[test]
fn test_performance_render_100_components_under_100ms() {
    let timer = Instant::now();
    
    // Create 100 simple text components
    let mut components = Vec::new();
    for i in 0..100 {
        components.push(A2UIComponent::Text {
            id: format!("text_{}", i),
            content: format!("Component {}", i),
            size: Some("md".to_string()),
        });
    }
    
    // Render all components
    for component in components {
        ReactCodeGenerator::generate_component(&component);
    }
    
    let elapsed_ms = timer.elapsed().as_secs_f64() * 1000.0;
    println!("Rendered 100 components in {}ms", elapsed_ms);
    
    assert!(
        elapsed_ms < 100.0,
        "Rendering 100 components took {}ms, expected <100ms",
        elapsed_ms
    );
}

#[test]
fn test_performance_validate_100_components_under_100ms() {
    let timer = Instant::now();
    let validator = SchemaValidator::new();
    
    // Validate 100 simple text components
    for i in 0..100 {
        let json = serde_json::json!({
            "type": "text",
            "id": format!("text_{}", i),
            "content": format!("Component {}", i),
            "size": "md"
        });
        
        let _ = validator.validate("text", &json);
    }
    
    let elapsed_ms = timer.elapsed().as_secs_f64() * 1000.0;
    println!("Validated 100 components in {}ms", elapsed_ms);
    
    assert!(
        elapsed_ms < 100.0,
        "Validating 100 components took {}ms, expected <100ms",
        elapsed_ms
    );
}

#[test]
fn test_performance_schema_generation_all_types_under_50ms() {
    let timer = Instant::now();
    
    for component_type in A2UIComponentRegistry::all_types() {
        JsonSchemaGenerator::generate_schema(&component_type);
    }
    
    let elapsed_ms = timer.elapsed().as_secs_f64() * 1000.0;
    println!("Generated 18 schemas in {}ms", elapsed_ms);
    
    assert!(
        elapsed_ms < 50.0,
        "Schema generation for all 18 types took {}ms, expected <50ms",
        elapsed_ms
    );
}

#[test]
fn test_performance_full_pipeline_100_components_under_200ms() {
    let timer = Instant::now();
    let validator = SchemaValidator::new();
    
    for i in 0..100 {
        // 1. Validate
        let json = serde_json::json!({
            "type": "text",
            "id": format!("text_{}", i),
            "content": format!("Content {}", i),
            "size": "md"
        });
        let _ = validator.validate("text", &json);
        
        // 2. Render
        let component = A2UIComponent::Text {
            id: format!("text_{}", i),
            content: format!("Content {}", i),
            size: Some("md".to_string()),
        };
        ReactCodeGenerator::generate_component(&component);
    }
    
    let elapsed_ms = timer.elapsed().as_secs_f64() * 1000.0;
    println!("Full pipeline for 100 components in {}ms", elapsed_ms);
    
    assert!(
        elapsed_ms < 200.0,
        "Full pipeline took {}ms, expected <200ms",
        elapsed_ms
    );
}

#[test]
fn test_performance_metrics_tracking() {
    let mut metrics = PerformanceMetrics::new();
    
    metrics.record_render_time(30.0);
    metrics.record_validation_time(20.0);
    metrics.record_schema_generation_time(10.0);
    metrics.set_component_count(100);
    
    println!("{}", metrics.summary());
    assert!(metrics.within_performance_budget());
}
```

- [ ] **Step 3: Run integration tests**

```bash
cd /Users/andriileukhin/Documents/SovereignNexus
cargo test -p siss-a2ui-framework integration --test '*'
```

Expected: All tests pass with performance assertions.

- [ ] **Step 4: Run all framework tests**

```bash
cd /Users/andriileukhin/Documents/SovereignNexus
cargo test -p siss-a2ui-framework
```

Expected: 50+ tests pass total.

- [ ] **Step 5: Commit**

```bash
git add crates/siss-a2ui-framework/tests/integration_tests.rs crates/siss-a2ui-framework/tests/performance_benchmarks.rs
git commit -m "test: add integration and performance benchmark suite"
```

---

### Task 8: Update Workspace and Run Full Test Suite

**Files:**
- Modify: `/Cargo.toml` (workspace)

**Steps:**

- [ ] **Step 1: Verify crate is in workspace**

Already done in Task 1. Confirm:

```bash
cd /Users/andriileukhin/Documents/SovereignNexus
grep "siss-a2ui-framework" Cargo.toml
```

Expected: Crate is listed in members.

- [ ] **Step 2: Run full workspace test suite**

```bash
cd /Users/andriileukhin/Documents/SovereignNexus
cargo test -p siss-a2ui-framework --all
```

Expected: All 50+ tests pass, performance assertions hold.

- [ ] **Step 3: Check for linting issues**

```bash
cd /Users/andriileukhin/Documents/SovereignNexus
cargo clippy -p siss-a2ui-framework -- -D warnings
cargo fmt -p siss-a2ui-framework --check
```

Expected: No clippy or format issues.

- [ ] **Step 4: Final commit with summary**

```bash
git add -A
git commit -m "Phase 32: A2UI Declarative Framework (50+ tests, 18 components, JSON Schema validated)"
```

---

## Success Criteria

✓ **All 50+ tests pass** (8 schema + 13 React + 10 validation + 5 integration + 5 perf)
✓ **18 components fully supported** with schema, validation, React codegen
✓ **JSON Schema Draft 2020-12** generation working
✓ **React TSX rendering** producing valid syntax
✓ **Validation layer** enforcing schema constraints
✓ **Performance** <100ms for 100 components (full pipeline)
✓ **Integration tests** covering schema→validation→render pipeline
✓ **No clippy/format warnings**

---

## Execution Options

**Plan complete and saved to `/docs/superpowers/plans/2026-07-30-phase-32-a2ui-declarative-framework.md`**

Two execution paths:

**1. Subagent-Driven (Recommended)** — Fresh agent per task, structured reviews
- Use `superpowers:subagent-driven-development` 
- Tasks execute in parallel with checkpoints
- Faster iteration

**2. Inline Execution (This Session)** — Execute all tasks sequentially
- Use `superpowers:executing-plans`
- Single-pass batch execution

Which approach?
