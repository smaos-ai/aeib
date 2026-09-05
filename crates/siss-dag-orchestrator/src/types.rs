//! Core types for DAG orchestration

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

/// Execution ID
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct ExecutionId(pub Uuid);

impl ExecutionId {
    pub fn new() -> Self {
        ExecutionId(Uuid::new_v4())
    }
}

impl Default for ExecutionId {
    fn default() -> Self {
        Self::new()
    }
}

/// Checkpoint ID
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct CheckpointId(pub Uuid);

impl CheckpointId {
    pub fn new() -> Self {
        CheckpointId(Uuid::new_v4())
    }
}

impl Default for CheckpointId {
    fn default() -> Self {
        Self::new()
    }
}

/// Execution intent
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionIntent {
    pub id: ExecutionId,
    pub name: String,
    pub description: String,
    pub steps: Vec<IntentStep>,
    pub constraints: Vec<Constraint>,
    pub created_at: chrono::DateTime<chrono::Utc>,
}

/// Intent step
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IntentStep {
    pub id: String,
    pub action: String,
    pub parameters: serde_json::Value,
    pub dependencies: Vec<String>,
}

/// Execution constraint
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Constraint {
    pub id: String,
    pub constraint_type: String,
    pub value: serde_json::Value,
}

/// Compiled DAG node
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DagNode {
    pub id: String,
    pub step_id: String,
    pub action: String,
    pub parameters: serde_json::Value,
    pub dependencies: Vec<String>,
    pub priority: u8,
}

/// Compiled DAG
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompiledDag {
    pub execution_id: ExecutionId,
    pub nodes: HashMap<String, DagNode>,
    pub edges: Vec<(String, String)>,
    pub levels: Vec<Vec<String>>,
    pub compiled_at: chrono::DateTime<chrono::Utc>,
}

/// Task execution state
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum TaskState {
    Pending,
    Running,
    Completed,
    Failed,
    Recovered,
}

/// Task execution record
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskExecution {
    pub task_id: String,
    pub execution_id: ExecutionId,
    pub state: TaskState,
    pub result: Option<serde_json::Value>,
    pub error: Option<String>,
    pub start_time: Option<chrono::DateTime<chrono::Utc>>,
    pub end_time: Option<chrono::DateTime<chrono::Utc>>,
}

/// Checkpoint snapshot
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Checkpoint {
    pub id: CheckpointId,
    pub execution_id: ExecutionId,
    pub task_states: HashMap<String, TaskExecution>,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub recoverable: bool,
}

/// Execution metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionMetrics {
    pub execution_id: ExecutionId,
    pub total_tasks: usize,
    pub completed_tasks: usize,
    pub failed_tasks: usize,
    pub duration_ms: u128,
    pub checkpoint_count: usize,
}
