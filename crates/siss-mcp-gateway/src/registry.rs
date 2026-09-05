use serde::{Deserialize, Serialize};
use thiserror::Error;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SkillRegistry {
    pub id: Uuid,
    pub skills: Vec<SkillEntry>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SkillEntry {
    pub name: String,
    pub version: String,
    pub enabled: bool,
}

#[derive(Debug, Error)]
pub enum RegistryError {
    #[error("Skill not found: {0}")]
    SkillNotFound(String),

    #[error("Invalid skill: {0}")]
    InvalidSkill(String),

    #[error("Registry error: {0}")]
    RegistryFailed(String),
}

impl SkillRegistry {
    pub fn new() -> Self {
        Self {
            id: Uuid::new_v4(),
            skills: Vec::new(),
        }
    }

    pub fn register_skill(&mut self, name: String, version: String) -> Result<(), RegistryError> {
        self.skills.push(SkillEntry {
            name,
            version,
            enabled: true,
        });
        Ok(())
    }

    pub fn get_skill(&self, name: &str) -> Result<&SkillEntry, RegistryError> {
        self.skills
            .iter()
            .find(|s| s.name == name)
            .ok_or_else(|| RegistryError::SkillNotFound(name.to_string()))
    }

    pub fn list_skills(&self) -> Vec<&SkillEntry> {
        self.skills.iter().collect()
    }

    pub fn remove_skill(&mut self, name: &str) -> Result<(), RegistryError> {
        let initial_len = self.skills.len();
        self.skills.retain(|s| s.name != name);
        if self.skills.len() < initial_len {
            Ok(())
        } else {
            Err(RegistryError::SkillNotFound(name.to_string()))
        }
    }
}

impl Default for SkillRegistry {
    fn default() -> Self {
        Self::new()
    }
}
