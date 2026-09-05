use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SwarmAgentCard {
    pub agent_id: Uuid,
    pub name: String,
    pub version: String,
    pub url: String,
    pub skills: Vec<SwarmSkill>,
    pub capabilities: SwarmCapabilities,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SwarmSkill {
    pub id: String,
    pub name: String,
    pub description: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct SwarmCapabilities {
    pub can_stream: bool,
    pub can_push_notifications: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct A2ATask {
    pub task_id: Uuid,
    pub root_agent_id: Uuid,
    pub worker_agent_id: Uuid,
    pub context_refs: Vec<Uuid>,
    pub skill_id: String,
    pub token_budget: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum A2ATaskStatus {
    Pending,
    Running,
    Completed,
    Failed,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct A2ATaskUpdate {
    pub task_id: Uuid,
    pub status: A2ATaskStatus,
    pub artifact_ref: Option<Uuid>,
    pub reason: Option<String>,
}
