pub mod rebac;

pub use rebac::{ReBAC, Relationship, RelationType, PolicyResource, PolicyAction, DenyReason};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, serde::Serialize, serde::Deserialize)]
pub struct SovereignIdentity(pub uuid::Uuid);

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ReBACError {
    Database(String),
    NotFound,
    AlreadyExists,
    CycleDetected,
    MaxDepthExceeded,
}

impl std::fmt::Display for ReBACError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ReBACError::Database(e) => write!(f, "Database error: {}", e),
            ReBACError::NotFound => write!(f, "Relationship not found"),
            ReBACError::AlreadyExists => write!(f, "Relationship already exists"),
            ReBACError::CycleDetected => write!(f, "Cycle detected in delegation"),
            ReBACError::MaxDepthExceeded => write!(f, "Max delegation depth exceeded"),
        }
    }
}

impl std::error::Error for ReBACError {}
