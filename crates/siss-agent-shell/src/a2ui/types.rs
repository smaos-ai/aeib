use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Form submission from operator back to agent
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FormSubmission {
    pub task_id: Uuid,
    pub form_id: String,
    pub values: serde_json::Value,
}

/// Response wrapper for A2UI components
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct A2UIResponse {
    pub component_type: String,
}
