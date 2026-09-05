//! Core types for swarm safety

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

/// Unique agent identifier
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct AgentId(pub Uuid);

impl AgentId {
    pub fn new() -> Self {
        AgentId(Uuid::new_v4())
    }
}

impl Default for AgentId {
    fn default() -> Self {
        Self::new()
    }
}

/// Task identifier within a DAG
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct TaskId(pub Uuid);

impl TaskId {
    pub fn new() -> Self {
        TaskId(Uuid::new_v4())
    }
}

impl Default for TaskId {
    fn default() -> Self {
        Self::new()
    }
}

/// Security level for tasks
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub enum SecurityLevel {
    Public = 0,
    Internal = 1,
    Restricted = 2,
    Secret = 3,
}

/// Task definition in DAG
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Task {
    pub id: TaskId,
    pub agent_id: AgentId,
    pub name: String,
    pub security_level: SecurityLevel,
    pub depends_on: Vec<TaskId>,
    pub timeout_ms: u64,
    pub payload: serde_json::Value,
}

/// DAG (Directed Acyclic Graph) structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Dag {
    pub id: Uuid,
    pub tasks: HashMap<TaskId, Task>,
    pub edges: Vec<(TaskId, TaskId)>,
}

/// Execution status of a task
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ExecutionStatus {
    Pending,
    Running,
    Completed,
    Failed,
    Blocked,
    Timeout,
}

/// Execution record
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionRecord {
    pub task_id: TaskId,
    pub agent_id: AgentId,
    pub status: ExecutionStatus,
    pub start_time: Option<chrono::DateTime<chrono::Utc>>,
    pub end_time: Option<chrono::DateTime<chrono::Utc>>,
    pub result: Option<serde_json::Value>,
    pub error: Option<String>,
}

/// RCE pattern definition
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RcePattern {
    pub id: String,
    pub pattern: String,
    pub severity: RceSeverity,
    pub block_by_default: bool,
}

/// RCE severity levels
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum RceSeverity {
    Low,
    Medium,
    High,
    Critical,
}

/// Security boundary constraint
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BoundaryConstraint {
    pub id: String,
    pub source_security_level: SecurityLevel,
    pub target_security_level: SecurityLevel,
    pub allowed: bool,
}

/// Communication metadata (sub-20μs latency tracking)
#[derive(Debug, Clone, Copy)]
pub struct CommMetadata {
    pub send_time_ns: u128,
    pub receive_time_ns: u128,
}

impl CommMetadata {
    pub fn latency_us(&self) -> f64 {
        ((self.receive_time_ns - self.send_time_ns) / 1000) as f64
    }
}
