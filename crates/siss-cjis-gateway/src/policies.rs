use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AccessPolicy {
    role: String,
    control_id: String,
}

impl AccessPolicy {
    pub fn new(role: &str, control_id: &str) -> Self {
        Self {
            role: role.to_string(),
            control_id: control_id.to_string(),
        }
    }

    pub fn role(&self) -> &str {
        &self.role
    }

    pub fn control_id(&self) -> &str {
        &self.control_id
    }

    pub fn is_valid(&self) -> bool {
        !self.role.is_empty() && !self.control_id.is_empty()
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EncryptionPolicy {
    algorithm: String,
    key_length: u32,
}

impl EncryptionPolicy {
    pub fn new(algorithm: &str) -> Self {
        let key_length = match algorithm {
            "AES-256" => 256,
            "AES-192" => 192,
            "AES-128" => 128,
            _ => 256,
        };

        Self {
            algorithm: algorithm.to_string(),
            key_length,
        }
    }

    pub fn algorithm(&self) -> &str {
        &self.algorithm
    }

    pub fn key_length(&self) -> u32 {
        self.key_length
    }

    pub fn is_valid(&self) -> bool {
        matches!(
            self.algorithm.as_str(),
            "AES-256" | "AES-192" | "AES-128"
        )
    }
}
