use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use siss_graph_core::node::NodeId;
use siss_graph_core::node::execution::HardwareTarget;

// ── AgentCardNode ──────────────────────────────────────────────────────────────

/// The authoritative record stored in the SISS Knowledge Graph.
/// `allowed_tools` is populated by the builder from CAN_EXECUTE edges —
/// `fetch_agent_card_node` returns it as an empty vec.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentCardNode {
    pub id: NodeId,
    pub persona_id: NodeId,
    pub tenant_id: NodeId,
    pub name: String,
    pub description: String,
    pub version: String,
    pub url: String,
    pub hardware_affinity: HardwareTarget,
    pub budget_cap: i64,
    pub allowed_tools: Vec<NodeId>,
    pub created_at: DateTime<Utc>,
}

// ── AgentCard (in-memory working type) ────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct AgentCard {
    pub node: AgentCardNode,
    pub skills: Vec<Skill>,
    pub capabilities: Capability,
    pub authentication: Authentication,
}

// ── Supporting types ──────────────────────────────────────────────────────────

/// A single A2A skill — corresponds to one tool the persona can execute.
#[derive(Debug, Clone)]
pub struct Skill {
    /// snake_case identifier, e.g. "mcp_filesystem"
    pub id: String,
    pub name: String,
    pub description: String,
    pub tags: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct Capability {
    /// true because siss-agent-shell emits AG-UI events
    pub streaming: bool,
    /// false in Phase 3
    pub push_notifications: bool,
}

#[derive(Debug, Clone)]
pub struct Authentication {
    /// e.g. ["Bearer"]
    pub schemes: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct SerializeOptions {
    /// When true, include the `x-siss` extension block in the JSON output.
    pub extended: bool,
}

// ── AgentCardError ────────────────────────────────────────────────────────────

#[derive(Debug, thiserror::Error)]
pub enum AgentCardError {
    #[error("persona not found: {persona_id}")]
    PersonaNotFound { persona_id: Uuid },
    #[error("agent card not found for persona: {persona_id}")]
    CardNotFound { persona_id: Uuid },
    #[error("database error: {message}")]
    DatabaseError { message: String },
}

impl From<sqlx::Error> for AgentCardError {
    fn from(e: sqlx::Error) -> Self {
        AgentCardError::DatabaseError { message: e.to_string() }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_persona_not_found_error_message() {
        let id = Uuid::nil();
        let err = AgentCardError::PersonaNotFound { persona_id: id };
        assert_eq!(
            err.to_string(),
            "persona not found: 00000000-0000-0000-0000-000000000000"
        );
    }

    #[test]
    fn test_card_not_found_error_message() {
        let id = Uuid::nil();
        let err = AgentCardError::CardNotFound { persona_id: id };
        assert_eq!(
            err.to_string(),
            "agent card not found for persona: 00000000-0000-0000-0000-000000000000"
        );
    }

    #[test]
    fn test_database_error_message() {
        let err = AgentCardError::DatabaseError { message: "conn refused".into() };
        assert_eq!(err.to_string(), "database error: conn refused");
    }

    #[test]
    fn test_from_sqlx_error() {
        let sqlx_err = sqlx::Error::RowNotFound;
        let err: AgentCardError = sqlx_err.into();
        assert!(matches!(err, AgentCardError::DatabaseError { .. }));
    }

    #[test]
    fn test_agent_card_node_fields() {
        let tenant_id = NodeId::new();
        let persona_id = NodeId::new();
        let node = AgentCardNode {
            id: NodeId::new(),
            persona_id,
            tenant_id,
            name: "TestAgent".into(),
            description: "A test agent".into(),
            version: "0.1.0".into(),
            url: "https://example.com".into(),
            hardware_affinity: HardwareTarget::LocalMlx,
            budget_cap: 50_000,
            allowed_tools: vec![],
            created_at: Utc::now(),
        };
        assert_eq!(node.name, "TestAgent");
        assert_eq!(node.budget_cap, 50_000);
        assert_eq!(node.hardware_affinity, HardwareTarget::LocalMlx);
    }

    #[test]
    fn test_serialize_options_default_not_extended() {
        let opts = SerializeOptions { extended: false };
        assert!(!opts.extended);
    }
}
