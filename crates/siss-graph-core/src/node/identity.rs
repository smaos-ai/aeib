use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use crate::node::NodeId;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Tenant {
    pub id: NodeId,
    pub tenant_id: NodeId,
    pub name: String,
    pub created_at: DateTime<Utc>,
}

impl Tenant {
    pub fn new(name: String) -> Self {
        let id = NodeId::new();
        Self {
            id,
            tenant_id: id, // self-referential: a Tenant is its own isolation root
            name,
            created_at: Utc::now(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct User {
    pub id: NodeId,
    pub tenant_id: NodeId,
    pub email: String,
    pub created_at: DateTime<Utc>,
}

impl User {
    pub fn new(email: String, tenant_id: NodeId) -> Self {
        Self {
            id: NodeId::new(),
            tenant_id,
            email,
            created_at: Utc::now(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Team {
    pub id: NodeId,
    pub tenant_id: NodeId,
    pub name: String,
    pub created_at: DateTime<Utc>,
}

impl Team {
    pub fn new(name: String, tenant_id: NodeId) -> Self {
        Self {
            id: NodeId::new(),
            tenant_id,
            name,
            created_at: Utc::now(),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum PersonaKind {
    HumanRole,
    AiAgent,
    SystemDaemon,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Persona {
    pub id: NodeId,
    pub tenant_id: NodeId,
    pub name: String,
    pub kind: PersonaKind,
    pub is_frozen: bool,
    pub spawned_by: Option<NodeId>,
    pub created_at: DateTime<Utc>,
}

impl Persona {
    pub fn new(name: String, kind: PersonaKind, tenant_id: NodeId) -> Self {
        Self {
            id: NodeId::new(),
            tenant_id,
            name,
            kind,
            is_frozen: false,
            spawned_by: None,
            created_at: Utc::now(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_tenant() {
        let tenant = Tenant::new("Acme Corp".into());
        assert_eq!(tenant.name, "Acme Corp");
        assert!(!tenant.id.0.is_nil());
        assert!(!tenant.tenant_id.0.is_nil());
        assert_eq!(tenant.id, tenant.tenant_id);
    }

    #[test]
    fn test_create_user() {
        let tenant_id = NodeId::new();
        let user = User::new("alice@example.com".into(), tenant_id);
        assert_eq!(user.email, "alice@example.com");
        assert_eq!(user.tenant_id, tenant_id);
    }

    #[test]
    fn test_create_team() {
        let tenant_id = NodeId::new();
        let team = Team::new("Engineering".into(), tenant_id);
        assert_eq!(team.name, "Engineering");
        assert_eq!(team.tenant_id, tenant_id);
    }

    #[test]
    fn test_create_persona() {
        let tenant_id = NodeId::new();
        let persona = Persona::new(
            "GovernanceGatekeeper".into(),
            PersonaKind::AiAgent,
            tenant_id,
        );
        assert_eq!(persona.name, "GovernanceGatekeeper");
        assert_eq!(persona.kind, PersonaKind::AiAgent);
        assert_eq!(persona.tenant_id, tenant_id);
        assert!(persona.spawned_by.is_none());
    }
}
