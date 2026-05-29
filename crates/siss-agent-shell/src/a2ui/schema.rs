use serde::{Deserialize, Serialize};

/// 18 Safe UI Component Primitives for Agent-to-User Interface
///
/// Agents emit these declaratively. Cockpit renders each type.
/// All variants implement Serialize/Deserialize for JSON transmission.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum A2UIComponent {
    // === DISPLAY (8 types) ===

    /// Plain text display
    Text {
        id: String,
        content: String,
        #[serde(default)]
        size: Option<String>, // "sm" | "md" | "lg"
    },

    /// Badge/label with color
    Badge {
        id: String,
        label: String,
        #[serde(default)]
        color: Option<String>, // "blue" | "red" | "green" | "yellow"
    },

    /// Alert message (info/warn/error)
    Alert {
        id: String,
        message: String,
        #[serde(default)]
        level: String, // "info" | "warn" | "error"
    },

    /// Progress bar with percentage
    Progress {
        id: String,
        value: u32,
        max: u32,
        #[serde(default)]
        label: Option<String>,
    },

    /// Horizontal divider line
    Divider {
        id: String,
    },

    /// Hyperlink
    Link {
        id: String,
        label: String,
        href: String,
    },

    /// Hover tooltip
    Tooltip {
        id: String,
        text: String,
        content: String,
    },

    /// Breadcrumb navigation
    Breadcrumb {
        id: String,
        items: Vec<String>,
    },

    // === INTERACTIVE FORMS (6 types, all require id) ===

    /// Text input field (required: id)
    Input {
        id: String,
        label: String,
        #[serde(default)]
        placeholder: Option<String>,
        #[serde(default)]
        required: bool,
    },

    /// Multi-line text area (required: id)
    Textarea {
        id: String,
        label: String,
        #[serde(default)]
        rows: Option<u32>,
    },

    /// Dropdown selector (required: id)
    Select {
        id: String,
        label: String,
        options: Vec<SelectOption>,
    },

    /// Checkbox (required: id)
    Checkbox {
        id: String,
        label: String,
        #[serde(default)]
        checked: bool,
    },

    /// Radio button group (required: id)
    Radio {
        id: String,
        label: String,
        value: String,
        #[serde(default)]
        checked: bool,
    },

    /// Clickable button (required: id)
    Button {
        id: String,
        label: String,
        #[serde(default)]
        action: Option<String>, // "submit" | "reset" | "custom"
    },

    // === LAYOUT (4 types) ===

    /// Card container with title
    Card {
        id: String,
        #[serde(default)]
        title: Option<String>,
        children: Vec<A2UIComponent>,
    },

    /// Grid layout with N columns
    Grid {
        id: String,
        columns: u32,
        children: Vec<A2UIComponent>,
    },

    /// Modal dialog (required: id)
    Modal {
        id: String,
        title: String,
        content: String,
        children: Vec<A2UIComponent>,
    },

    /// Data table with headers and rows
    Table {
        id: String,
        headers: Vec<String>,
        rows: Vec<Vec<String>>,
    },
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SelectOption {
    pub value: String,
    pub label: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RadioOption {
    pub value: String,
    pub label: String,
}
