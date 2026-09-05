use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum DataClassification {
    Public,
    Internal,
    Confidential,
    HighImpact,
}

impl DataClassification {
    pub fn requires_encryption(&self) -> bool {
        matches!(self, DataClassification::Confidential | DataClassification::HighImpact)
    }

    pub fn requires_audit(&self) -> bool {
        matches!(self, DataClassification::Confidential | DataClassification::HighImpact)
    }

    pub fn level_number(&self) -> u8 {
        match self {
            DataClassification::Public => 1,
            DataClassification::Internal => 2,
            DataClassification::Confidential => 3,
            DataClassification::HighImpact => 4,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AccessPolicy {
    role: String,
    control_id: String,
    valid: bool,
}

impl AccessPolicy {
    pub fn new(role: &str, control_id: &str) -> Self {
        Self {
            role: role.to_string(),
            control_id: control_id.to_string(),
            valid: true,
        }
    }

    pub fn role(&self) -> &str {
        &self.role
    }

    pub fn control_id(&self) -> &str {
        &self.control_id
    }

    pub fn is_valid(&self) -> bool {
        self.valid
    }

    pub fn invalidate(&mut self) {
        self.valid = false;
    }
}
