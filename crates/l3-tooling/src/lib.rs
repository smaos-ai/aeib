//! L3 Tooling Layer — Tool Registry with Fail-Closed Permit Gates

use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum PermitDecision {
    #[serde(rename = "allowed")]
    Allowed,
    #[serde(rename = "blocked")]
    Blocked,
}

#[derive(Debug, Clone)]
pub struct ToolDefinition {
    pub name: String,
    pub description: String,
    pub required_articles: Vec<String>,
    pub annex_category: String,
    pub risk_level: String,
}

pub struct ToolRegistry {
    tools: HashMap<String, ToolDefinition>,
    agent_policies: HashMap<String, HashSet<String>>,
}

impl ToolRegistry {
    pub fn new() -> Self {
        Self {
            tools: HashMap::new(),
            agent_policies: HashMap::new(),
        }
    }

    pub fn register_tool(&mut self, tool: ToolDefinition) {
        self.tools.insert(tool.name.clone(), tool);
    }

    pub fn register_agent_policy(&mut self, agent_id: String, articles: Vec<String>) {
        self.agent_policies.insert(agent_id, articles.into_iter().collect());
    }

    pub fn permit_gate(
        &self,
        tool_name: &str,
        agent_id: &str,
    ) -> (PermitDecision, String, serde_json::Value) {
        if !self.tools.contains_key(tool_name) {
            return (
                PermitDecision::Blocked,
                format!("Tool '{}' not found in registry", tool_name),
                serde_json::json!({"evidence_type": "tool_not_found"}),
            );
        }

        let tool = &self.tools[tool_name];
        let agent_articles = self
            .agent_policies
            .get(agent_id)
            .cloned()
            .unwrap_or_default();

        let required_articles: HashSet<_> = tool.required_articles.iter().cloned().collect();
        let missing: Vec<_> = required_articles.difference(&agent_articles).cloned().collect();

        if !missing.is_empty() {
            return (
                PermitDecision::Blocked,
                format!("Agent lacks authority for {}", missing.join(", ")),
                serde_json::json!({"evidence_type": "missing_articles", "missing": missing}),
            );
        }

        (
            PermitDecision::Allowed,
            format!("Tool '{}' authorized for {}", tool_name, agent_id),
            serde_json::json!({"evidence_type": "tool_authorized", "tool": tool_name}),
        )
    }
}
