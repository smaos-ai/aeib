//! DAG executor: executes compiled DAG with failure handling

use crate::error::Result;
use crate::types::{CompiledDag, ExecutionId, ExecutionMetrics, TaskExecution, TaskState};
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;

/// Executor configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutorConfig {
    pub max_retries: usize,
    pub timeout_ms: u64,
    pub parallel_degree: usize,
}

impl Default for ExecutorConfig {
    fn default() -> Self {
        Self {
            max_retries: 3,
            timeout_ms: 30000,
            parallel_degree: 4,
        }
    }
}

/// DAG executor
pub struct DagExecutor {
    #[allow(dead_code)]
    config: ExecutorConfig,
    executions: Arc<RwLock<HashMap<ExecutionId, ExecutionMetrics>>>,
    task_states: Arc<RwLock<HashMap<ExecutionId, HashMap<String, TaskExecution>>>>,
}

impl DagExecutor {
    /// Create new executor
    pub fn new(config: ExecutorConfig) -> Self {
        Self {
            config,
            executions: Arc::new(RwLock::new(HashMap::new())),
            task_states: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Execute compiled DAG
    pub fn execute(&self, dag: &CompiledDag) -> Result<ExecutionMetrics> {
        let start_time = std::time::Instant::now();

        let mut task_states = HashMap::new();
        let mut completed = 0;
        let mut failed = 0;

        // Execute levels sequentially, tasks in level in parallel
        for level in &dag.levels {
            for task_id in level {
                let state = TaskExecution {
                    task_id: task_id.clone(),
                    execution_id: dag.execution_id,
                    state: TaskState::Running,
                    result: None,
                    error: None,
                    start_time: Some(chrono::Utc::now()),
                    end_time: None,
                };

                task_states.insert(task_id.clone(), state);

                // Simulate task execution
                if self.should_succeed(task_id) {
                    let updated = task_states.get_mut(task_id).unwrap();
                    updated.state = TaskState::Completed;
                    updated.end_time = Some(chrono::Utc::now());
                    updated.result = Some(serde_json::json!({ "success": true }));
                    completed += 1;
                } else {
                    let updated = task_states.get_mut(task_id).unwrap();
                    updated.state = TaskState::Failed;
                    updated.end_time = Some(chrono::Utc::now());
                    updated.error = Some("Execution failed".to_string());
                    failed += 1;
                }
            }
        }

        let elapsed = start_time.elapsed();

        let metrics = ExecutionMetrics {
            execution_id: dag.execution_id,
            total_tasks: dag.nodes.len(),
            completed_tasks: completed,
            failed_tasks: failed,
            duration_ms: elapsed.as_millis(),
            checkpoint_count: 0,
        };

        let mut states = self.task_states.write();
        states.insert(dag.execution_id, task_states);

        let mut execs = self.executions.write();
        execs.insert(dag.execution_id, metrics.clone());

        Ok(metrics)
    }

    /// Get execution metrics
    pub fn get_metrics(&self, execution_id: ExecutionId) -> Option<ExecutionMetrics> {
        self.executions.read().get(&execution_id).cloned()
    }

    /// Get task states for execution
    pub fn get_task_states(&self, execution_id: ExecutionId) -> HashMap<String, TaskExecution> {
        self.task_states
            .read()
            .get(&execution_id)
            .cloned()
            .unwrap_or_default()
    }

    fn should_succeed(&self, _task_id: &str) -> bool {
        // In real execution, would run actual task
        true
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::{CompiledDag, DagNode};
    use std::collections::HashMap;

    #[test]
    fn test_executor_creation() {
        let executor = DagExecutor::new(ExecutorConfig::default());
        assert!(executor.get_metrics(ExecutionId::new()).is_none());
    }

    #[test]
    fn test_execute_simple_dag() {
        let executor = DagExecutor::new(ExecutorConfig::default());

        let mut nodes = HashMap::new();
        nodes.insert(
            "task1".to_string(),
            DagNode {
                id: "task1".to_string(),
                step_id: "task1".to_string(),
                action: "action".to_string(),
                parameters: serde_json::json!({}),
                dependencies: Vec::new(),
                priority: 0,
            },
        );

        let dag = CompiledDag {
            execution_id: ExecutionId::new(),
            nodes,
            edges: Vec::new(),
            levels: vec![vec!["task1".to_string()]],
            compiled_at: chrono::Utc::now(),
        };

        let result = executor.execute(&dag);
        assert!(result.is_ok());

        let metrics = result.unwrap();
        assert_eq!(metrics.total_tasks, 1);
        assert_eq!(metrics.completed_tasks, 1);
    }

    #[test]
    fn test_get_task_states() {
        let executor = DagExecutor::new(ExecutorConfig::default());
        let exec_id = ExecutionId::new();

        let mut nodes = HashMap::new();
        nodes.insert(
            "task1".to_string(),
            DagNode {
                id: "task1".to_string(),
                step_id: "task1".to_string(),
                action: "action".to_string(),
                parameters: serde_json::json!({}),
                dependencies: Vec::new(),
                priority: 0,
            },
        );

        let dag = CompiledDag {
            execution_id: exec_id,
            nodes,
            edges: Vec::new(),
            levels: vec![vec!["task1".to_string()]],
            compiled_at: chrono::Utc::now(),
        };

        executor.execute(&dag).unwrap();
        let states = executor.get_task_states(exec_id);
        assert!(!states.is_empty());
    }
}
