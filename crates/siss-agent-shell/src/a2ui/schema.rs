use serde::{Deserialize, Serialize};

/// 18 Safe UI Component Primitives for Agent-to-User Interface
///
/// Agents emit these declaratively. Cockpit renders each type.
/// All variants implement Serialize/Deserialize for JSON transmission.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum A2UIComponent {
    // === DISPLAY (8 types) ===

    /// Plain text display
    Text {
        content: String,
        #[serde(default)]
        size: String, // "sm" | "md" | "lg"
    },

    /// Badge/label with color
    Badge {
        label: String,
        #[serde(default)]
        color: String, // "blue" | "red" | "green" | "yellow"
    },

    /// Alert message (info/warn/error)
    Alert {
        message: String,
        #[serde(default)]
        level: String, // "info" | "warn" | "error"
    },

    /// Progress bar with percentage
    Progress {
        value: u32,
        max: u32,
        #[serde(default)]
        label: Option<String>,
    },

    /// Horizontal divider line
    Divider,

    /// Hyperlink
    Link {
        text: String,
        href: String,
    },

    /// Hover tooltip
    Tooltip {
        text: String,
        content: String,
    },

    /// Breadcrumb navigation
    Breadcrumb {
        items: Vec<String>,
    },

    // === INTERACTIVE FORMS (6 types, all require id) ===

    /// Text input field (required: id)
    Input {
        id: String,
        label: String,
        #[serde(default)]
        placeholder: String,
        #[serde(default)]
        required: bool,
    },

    /// Multi-line text area (required: id)
    Textarea {
        id: String,
        label: String,
        #[serde(default)]
        rows: u32,
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
    },

    /// Radio button group (required: id)
    Radio {
        id: String,
        label: String,
        options: Vec<RadioOption>,
    },

    /// Clickable button (required: id)
    Button {
        id: String,
        label: String,
        #[serde(default)]
        action: String, // "submit" | "reset" | "custom"
    },

    // === LAYOUT (4 types) ===

    /// Card container with title
    Card {
        title: String,
        children: Vec<A2UIComponent>,
    },

    /// Grid layout with N columns
    Grid {
        columns: u32,
        children: Vec<A2UIComponent>,
    },

    /// Modal dialog (required: id)
    Modal {
        id: String,
        title: String,
        children: Vec<A2UIComponent>,
    },

    /// Data table with headers and rows
    Table {
        headers: Vec<String>,
        rows: Vec<Vec<String>>,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SelectOption {
    pub value: String,
    pub label: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RadioOption {
    pub value: String,
    pub label: String,
}
