use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::node::NodeId;

pub mod rebac;
pub mod ap2;
pub mod execution_edges;
pub mod cognitive;

/// Every edge type in the SISS graph.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum EdgeType {
    // Identity & Governance
    MemberOf,
    ActsAs,
    BelongsTo,
    // Access Control
    CanRead,
    CanWrite,
    CanExecute,
    DenyRead,
    DenyWrite,
    DenyExecute,
    // AP2
    AuthorizedBy,
    ReceiptedBy,
    // Execution
    InitiatedBy,
    GovernedBy,
    Produced,
    ScopedTo,
    Contains,
    Loaded,
    // Governance
    Enforces,
    ViolatedBy,
    AuthoredBy,
    // Cognitive
    DependsOn,
    Uses,
    Supports,
    Extends,
    Contradicts,
    Supersedes,
    // Swarm
    A2aDelegates,
    // A2A Discovery
    HasAgentCard,
}

/// A concrete edge record stored in the database.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EdgeRecord {
    pub id: Uuid,
    pub source_id: NodeId,
    pub target_id: NodeId,
    pub edge_type: EdgeType,
    pub tenant_id: NodeId,
    pub metadata: serde_json::Value,
    pub created_at: DateTime<Utc>,
}

impl EdgeRecord {
    pub fn new(
        source_id: NodeId,
        target_id: NodeId,
        edge_type: EdgeType,
        tenant_id: NodeId,
    ) -> Self {
        Self {
            id: Uuid::new_v4(),
            source_id,
            target_id,
            edge_type,
            tenant_id,
            metadata: serde_json::Value::Null,
            created_at: Utc::now(),
        }
    }

    pub fn with_metadata(mut self, metadata: serde_json::Value) -> Self {
        self.metadata = metadata;
        self
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_edge_record() {
        let tenant_id = NodeId::new();
        let source = NodeId::new();
        let target = NodeId::new();
        let edge = EdgeRecord::new(source, target, EdgeType::CanExecute, tenant_id);
        assert_eq!(edge.source_id, source);
        assert_eq!(edge.target_id, target);
        assert_eq!(edge.edge_type, EdgeType::CanExecute);
        assert_eq!(edge.tenant_id, tenant_id);
    }

    #[test]
    fn test_edge_with_metadata() {
        let tenant_id = NodeId::new();
        let edge = EdgeRecord::new(NodeId::new(), NodeId::new(), EdgeType::CanRead, tenant_id)
            .with_metadata(serde_json::json!({"granted_by": "admin", "expires_at": "2027-01-01"}));
        assert!(edge.metadata.get("granted_by").is_some());
    }

    #[test]
    fn test_tenant_isolation_on_edge() {
        let t1 = NodeId::new();
        let t2 = NodeId::new();
        let edge = EdgeRecord::new(NodeId::new(), NodeId::new(), EdgeType::MemberOf, t1);
        assert_eq!(edge.tenant_id, t1);
        assert_ne!(edge.tenant_id, t2);
    }

    #[test]
    fn test_has_agent_card_edge_type_exists() {
        let edge = EdgeRecord::new(
            NodeId::new(),
            NodeId::new(),
            EdgeType::HasAgentCard,
            NodeId::new(),
        );
        assert_eq!(edge.edge_type, EdgeType::HasAgentCard);
    }
}
