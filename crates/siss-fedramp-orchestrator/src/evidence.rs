use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ControlEvidence {
    pub control_id: String,
    pub implementation_path: String,
    pub timestamp: DateTime<Utc>,
    pub validated: bool,
}

impl ControlEvidence {
    pub fn new(control_id: &str, implementation_path: &str) -> Self {
        Self {
            control_id: control_id.to_string(),
            implementation_path: implementation_path.to_string(),
            timestamp: Utc::now(),
            validated: false,
        }
    }

    pub fn validate(&mut self) {
        self.validated = true;
    }

    pub fn is_valid(&self) -> bool {
        self.validated
    }
}
