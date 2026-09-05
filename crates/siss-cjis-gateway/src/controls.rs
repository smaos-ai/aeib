use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ControlCategory {
    AccessControl,
    AuditLogging,
    IdentityManagement,
    EncryptionAndKeyManagement,
    DataRetention,
    IncidentResponse,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CJISControl {
    pub id: String,
    pub category: ControlCategory,
    pub title: String,
    pub description: String,
}

impl CJISControl {
    pub fn new(id: &str, category: ControlCategory, title: &str, description: &str) -> Self {
        Self {
            id: id.to_string(),
            category,
            title: title.to_string(),
            description: description.to_string(),
        }
    }
}
