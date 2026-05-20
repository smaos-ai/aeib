use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

/// Unique identifier for tasks and agents
pub type Id = Uuid;

/// Task specification that can be serialized and passed to agents
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Task {
    pub id: Id,
    pub name: String,
    pub description: Option<String>,
    pub specification: serde_json::Value,
    pub status: TaskStatus,
    pub assigned_to: Option<Id>, // Agent ID
    pub retry_count: u32,
    pub created_at: DateTime<Utc>,
    pub started_at: Option<DateTime<Utc>>,
    pub completed_at: Option<DateTime<Utc>>,
    pub dependencies: Vec<TaskDependency>,
}

/// Task execution status
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum TaskStatus {
    Pending,
    Assigned,
    InProgress,
    Completed,
    Failed,
    RolledBack,
}

/// Dependency relationship between tasks
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TaskDependency {
    pub task_id: Id,
    pub dep_type: DependencyType,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum DependencyType {
    /// Must complete before this task starts
    BlockedBy,
    /// Must start before this task completes
    Blocks,
}

/// Agent lifecycle and status
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Agent {
    pub id: Id,
    pub index: u32, // 0-based agent index for naming
    pub status: AgentStatus,
    pub assigned_task: Option<Id>,
    pub worktree_path: Option<String>,
    pub created_at: DateTime<Utc>,
    pub last_heartbeat: DateTime<Utc>,
}

/// Agent execution status
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum AgentStatus {
    Idle,
    WorktreeInitializing,
    TaskInProgress,
    TaskCompleted,
    MergingChanges,
    Failed,
    Cleanup,
}

/// Merge result from a completed task
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MergeResult {
    pub task_id: Id,
    pub agent_id: Id,
    pub success: bool,
    pub conflicts: Vec<String>,
    pub merged_files: Vec<String>,
    pub error: Option<String>,
}

/// Executor configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutorConfig {
    pub max_agents: u32,
    pub repo_path: String,
    pub worktree_base: String,
    pub queue_file: String,
    pub agents_file: String,
    pub lock_timeout_secs: u64,
    pub task_timeout_secs: u64,
}

impl Default for ExecutorConfig {
    fn default() -> Self {
        Self {
            max_agents: 5,
            repo_path: ".".to_string(),
            worktree_base: "./.claude/worktrees".to_string(),
            queue_file: "./.dispatcher/queue.json".to_string(),
            agents_file: "./.dispatcher/agents.json".to_string(),
            lock_timeout_secs: 30,
            task_timeout_secs: 3600,
        }
    }
}

/// Shared state for task execution
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionState {
    pub tasks: HashMap<Id, Task>,
    pub agents: HashMap<Id, Agent>,
    pub merge_results: Vec<MergeResult>,
}

impl Default for ExecutionState {
    fn default() -> Self {
        Self {
            tasks: HashMap::new(),
            agents: HashMap::new(),
            merge_results: Vec::new(),
        }
    }
}
