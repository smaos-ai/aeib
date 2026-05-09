use uuid::Uuid;
use serde::{Serialize, Deserialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct NodeId(pub Uuid);

impl NodeId {
    pub fn new() -> Self {
        Self(Uuid::new_v4())
    }
}

impl Default for NodeId {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum NodeType {
    Tenant,
    Persona,
    Tool,
    AgentCard,
    TrustPolicy,
}

impl NodeType {
    pub fn as_str(&self) -> &'static str {
        match self {
            NodeType::Tenant => "tenant",
            NodeType::Persona => "persona",
            NodeType::Tool => "tool",
            NodeType::AgentCard => "agent_card",
            NodeType::TrustPolicy => "trust_policy",
        }
    }
}

pub mod identity;
pub mod resource;
pub mod memory;
pub mod transaction;
pub mod governance;
pub mod execution;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_trust_policy_node_type_exists() {
        let node_type = NodeType::TrustPolicy;
        assert_eq!(node_type.as_str(), "trust_policy");
    }
}
