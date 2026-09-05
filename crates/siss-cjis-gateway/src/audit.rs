use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum AuditResult {
    Success,
    Failure,
    Partial,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditEvent {
    pub timestamp: DateTime<Utc>,
    pub user_id: String,
    pub action: String,
    pub resource: String,
    pub result: AuditResult,
}

impl AuditEvent {
    pub fn new(user_id: &str, action: &str, resource: &str, result: AuditResult) -> Self {
        Self {
            timestamp: Utc::now(),
            user_id: user_id.to_string(),
            action: action.to_string(),
            resource: resource.to_string(),
            result,
        }
    }
}

#[derive(Debug, Clone)]
pub struct AuditLog {
    events: Vec<AuditEvent>,
}

impl AuditLog {
    pub fn new() -> Self {
        Self {
            events: Vec::new(),
        }
    }

    pub fn record(&mut self, event: AuditEvent) {
        self.events.push(event);
    }

    pub fn get_events(&self) -> &[AuditEvent] {
        &self.events
    }
}

impl Default for AuditLog {
    fn default() -> Self {
        Self::new()
    }
}
