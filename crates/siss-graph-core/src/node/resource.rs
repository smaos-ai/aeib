use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use crate::node::NodeId;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum RiskClass {
    Low,
    Medium,
    High,
    Critical,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Tool {
    pub id: NodeId,
    pub tenant_id: NodeId,
    pub name: String,
    pub tool_uri: String,
    pub risk_class: RiskClass,
    pub version: String,
    pub created_at: DateTime<Utc>,
}

impl Tool {
    pub fn new(name: String, tool_uri: String, risk_class: RiskClass, tenant_id: NodeId) -> Self {
        Self {
            id: NodeId::new(),
            tenant_id,
            name,
            tool_uri,
            risk_class,
            version: "0.1.0".into(),
            created_at: Utc::now(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Skill {
    pub id: NodeId,
    pub tenant_id: NodeId,
    pub name: String,
    pub definition: String,
    pub required_tools: Vec<NodeId>,
    pub version: String,
    pub created_at: DateTime<Utc>,
}

impl Skill {
    pub fn new(name: String, definition: String, required_tools: Vec<NodeId>, tenant_id: NodeId) -> Self {
        Self {
            id: NodeId::new(),
            tenant_id,
            name,
            definition,
            required_tools,
            version: "0.1.0".into(),
            created_at: Utc::now(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Document {
    pub id: NodeId,
    pub tenant_id: NodeId,
    pub name: String,
    pub mime_type: String,
    pub source_uri: Option<String>,
    pub content_hash: Vec<u8>,
    pub created_at: DateTime<Utc>,
}

impl Document {
    pub fn new(
        name: String,
        mime_type: String,
        source_uri: Option<String>,
        content_hash: Vec<u8>,
        tenant_id: NodeId,
    ) -> Self {
        Self {
            id: NodeId::new(),
            tenant_id,
            name,
            mime_type,
            source_uri,
            content_hash,
            created_at: Utc::now(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_tool() {
        let tenant_id = NodeId::new();
        let tool = Tool::new(
            "mcp-filesystem".into(),
            "mcp://localhost:3000/fs".into(),
            RiskClass::Medium,
            tenant_id,
        );
        assert_eq!(tool.name, "mcp-filesystem");
        assert_eq!(tool.tool_uri, "mcp://localhost:3000/fs");
        assert_eq!(tool.risk_class, RiskClass::Medium);
        assert_eq!(tool.tenant_id, tenant_id);
    }

    #[test]
    fn test_create_skill() {
        let tenant_id = NodeId::new();
        let tool_a = NodeId::new();
        let tool_b = NodeId::new();
        let skill = Skill::new(
            "code-review".into(),
            "Review code for bugs and style".into(),
            vec![tool_a, tool_b],
            tenant_id,
        );
        assert_eq!(skill.name, "code-review");
        assert_eq!(skill.required_tools.len(), 2);
        assert_eq!(skill.tenant_id, tenant_id);
    }

    #[test]
    fn test_create_document() {
        let tenant_id = NodeId::new();
        let doc = Document::new(
            "spec.md".into(),
            "text/markdown".into(),
            Some("file:///docs/spec.md".into()),
            vec![0xDE, 0xAD],
            tenant_id,
        );
        assert_eq!(doc.name, "spec.md");
        assert_eq!(doc.mime_type, "text/markdown");
        assert_eq!(doc.content_hash, vec![0xDE, 0xAD]);
    }
}
