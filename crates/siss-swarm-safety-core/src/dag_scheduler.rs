//! DAG Scheduler: Heterogeneous DAG scheduling for parallel agent workflows

use crate::error::{Error, Result};
use crate::types::{Dag, ExecutionRecord, ExecutionStatus, TaskId};
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, VecDeque};
use std::sync::Arc;

/// Schedule configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScheduleConfig {
    pub max_parallel_tasks: usize,
    pub task_timeout_ms: u64,
    pub enable_preemption: bool,
}

impl Default for ScheduleConfig {
    fn default() -> Self {
        Self {
            max_parallel_tasks: 10,
            task_timeout_ms: 30000,
            enable_preemption: false,
        }
    }
}

/// DAG Scheduler: manages safe execution of heterogeneous DAGs
pub struct DagScheduler {
    #[allow(dead_code)]
    config: ScheduleConfig,
    dag: Arc<RwLock<Option<Dag>>>,
    execution_records: Arc<RwLock<Vec<ExecutionRecord>>>,
    #[allow(dead_code)]
    ready_queue: Arc<RwLock<VecDeque<TaskId>>>,
    running_tasks: Arc<RwLock<HashMap<TaskId, ExecutionRecord>>>,
}

impl DagScheduler {
    /// Create new DAG scheduler
    pub fn new(config: ScheduleConfig) -> Self {
        Self {
            config,
            dag: Arc::new(RwLock::new(None)),
            execution_records: Arc::new(RwLock::new(Vec::new())),
            ready_queue: Arc::new(RwLock::new(VecDeque::new())),
            running_tasks: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Load DAG for scheduling
    pub fn load_dag(&self, dag: Dag) -> Result<()> {
        // Validate DAG is acyclic
        self.validate_dag(&dag)?;

        let mut current_dag = self.dag.write();
        *current_dag = Some(dag);

        Ok(())
    }

    /// Generate schedule from loaded DAG
    pub fn generate_schedule(&self) -> Result<Vec<Vec<TaskId>>> {
        let dag = self
            .dag
            .read()
            .clone()
            .ok_or(Error::InvalidSchedule("No DAG loaded".to_string()))?;

        // Topological sort with level-based scheduling
        let mut schedule: Vec<Vec<TaskId>> = Vec::new();
        let mut in_degree: HashMap<TaskId, usize> = HashMap::new();
        let mut adjacency: HashMap<TaskId, Vec<TaskId>> = HashMap::new();

        // Initialize in-degree and adjacency
        for task_id in dag.tasks.keys() {
            in_degree.insert(*task_id, 0);
            adjacency.insert(*task_id, Vec::new());
        }

        for (from, to) in &dag.edges {
            *in_degree.get_mut(to).unwrap() += 1;
            adjacency.get_mut(from).unwrap().push(*to);
        }

        // Kahn's algorithm with level tracking
        let mut queue: VecDeque<TaskId> = in_degree
            .iter()
            .filter(|(_, &deg)| deg == 0)
            .map(|(&id, _)| id)
            .collect();

        while !queue.is_empty() {
            let level_size = queue.len();
            let mut level_tasks = Vec::new();

            for _ in 0..level_size {
                if let Some(task_id) = queue.pop_front() {
                    level_tasks.push(task_id);

                    for &next in adjacency.get(&task_id).unwrap_or(&Vec::new()) {
                        *in_degree.get_mut(&next).unwrap() -= 1;
                        if in_degree[&next] == 0 {
                            queue.push_back(next);
                        }
                    }
                }
            }

            if !level_tasks.is_empty() {
                schedule.push(level_tasks);
            }
        }

        // Check if all tasks were scheduled (DAG is acyclic)
        if schedule.iter().map(|level| level.len()).sum::<usize>() != dag.tasks.len() {
            return Err(Error::InvalidDag("DAG contains cycles".to_string()));
        }

        Ok(schedule)
    }

    /// Record task execution result
    pub fn record_execution(&self, record: ExecutionRecord) -> Result<()> {
        let mut records = self.execution_records.write();
        records.push(record);
        Ok(())
    }

    /// Get execution history
    pub fn get_execution_history(&self) -> Vec<ExecutionRecord> {
        self.execution_records.read().clone()
    }

    /// Get current running tasks
    pub fn running_task_count(&self) -> usize {
        self.running_tasks.read().len()
    }

    /// Check if all tasks completed
    pub fn is_complete(&self) -> bool {
        let dag = self.dag.read();
        if let Some(dag) = dag.as_ref() {
            let records = self.execution_records.read();
            let completed: usize = records
                .iter()
                .filter(|r| r.status == ExecutionStatus::Completed)
                .count();
            completed == dag.tasks.len()
        } else {
            false
        }
    }

    /// Validate DAG structure
    fn validate_dag(&self, dag: &Dag) -> Result<()> {
        if dag.tasks.is_empty() {
            return Err(Error::InvalidDag("DAG has no tasks".to_string()));
        }

        // Check all edges reference valid tasks
        for (from, to) in &dag.edges {
            if !dag.tasks.contains_key(from) || !dag.tasks.contains_key(to) {
                return Err(Error::InvalidDag(
                    "Edge references non-existent task".to_string(),
                ));
            }
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use uuid::Uuid;

    #[test]
    fn test_scheduler_creation() {
        let scheduler = DagScheduler::new(ScheduleConfig::default());
        assert_eq!(scheduler.running_task_count(), 0);
    }

    #[test]
    fn test_load_dag() {
        use crate::types::{AgentId, SecurityLevel, Task};

        let mut dag = Dag {
            id: Uuid::new_v4(),
            tasks: HashMap::new(),
            edges: Vec::new(),
        };

        let task_id = TaskId::new();
        dag.tasks.insert(
            task_id,
            Task {
                id: task_id,
                agent_id: AgentId::new(),
                name: "test_task".to_string(),
                security_level: SecurityLevel::Public,
                depends_on: Vec::new(),
                timeout_ms: 1000,
                payload: serde_json::json!({}),
            },
        );

        let scheduler = DagScheduler::new(ScheduleConfig::default());
        let result = scheduler.load_dag(dag);
        assert!(result.is_ok());
    }

    #[test]
    fn test_generate_schedule() {
        use crate::types::{AgentId, SecurityLevel, Task};

        let mut dag = Dag {
            id: Uuid::new_v4(),
            tasks: HashMap::new(),
            edges: Vec::new(),
        };

        let task1 = TaskId::new();
        let task2 = TaskId::new();
        let task3 = TaskId::new();

        dag.tasks.insert(
            task1,
            Task {
                id: task1,
                agent_id: AgentId::new(),
                name: "task1".to_string(),
                security_level: SecurityLevel::Public,
                depends_on: Vec::new(),
                timeout_ms: 1000,
                payload: serde_json::json!({}),
            },
        );

        dag.tasks.insert(
            task2,
            Task {
                id: task2,
                agent_id: AgentId::new(),
                name: "task2".to_string(),
                security_level: SecurityLevel::Public,
                depends_on: vec![task1],
                timeout_ms: 1000,
                payload: serde_json::json!({}),
            },
        );

        dag.tasks.insert(
            task3,
            Task {
                id: task3,
                agent_id: AgentId::new(),
                name: "task3".to_string(),
                security_level: SecurityLevel::Public,
                depends_on: vec![task2],
                timeout_ms: 1000,
                payload: serde_json::json!({}),
            },
        );

        dag.edges.push((task1, task2));
        dag.edges.push((task2, task3));

        let scheduler = DagScheduler::new(ScheduleConfig::default());
        scheduler.load_dag(dag).unwrap();

        let schedule = scheduler.generate_schedule().unwrap();
        assert_eq!(schedule.len(), 3);
        assert_eq!(schedule[0].len(), 1);
        assert_eq!(schedule[1].len(), 1);
        assert_eq!(schedule[2].len(), 1);
    }

    #[test]
    fn test_parallel_schedule() {
        use crate::types::{AgentId, SecurityLevel, Task};

        let mut dag = Dag {
            id: Uuid::new_v4(),
            tasks: HashMap::new(),
            edges: Vec::new(),
        };

        let task1 = TaskId::new();
        let task2 = TaskId::new();
        let task3 = TaskId::new();

        dag.tasks.insert(
            task1,
            Task {
                id: task1,
                agent_id: AgentId::new(),
                name: "task1".to_string(),
                security_level: SecurityLevel::Public,
                depends_on: Vec::new(),
                timeout_ms: 1000,
                payload: serde_json::json!({}),
            },
        );

        // task2 and task3 depend on task1, can run in parallel
        dag.tasks.insert(
            task2,
            Task {
                id: task2,
                agent_id: AgentId::new(),
                name: "task2".to_string(),
                security_level: SecurityLevel::Public,
                depends_on: vec![task1],
                timeout_ms: 1000,
                payload: serde_json::json!({}),
            },
        );

        dag.tasks.insert(
            task3,
            Task {
                id: task3,
                agent_id: AgentId::new(),
                name: "task3".to_string(),
                security_level: SecurityLevel::Public,
                depends_on: vec![task1],
                timeout_ms: 1000,
                payload: serde_json::json!({}),
            },
        );

        dag.edges.push((task1, task2));
        dag.edges.push((task1, task3));

        let scheduler = DagScheduler::new(ScheduleConfig::default());
        scheduler.load_dag(dag).unwrap();

        let schedule = scheduler.generate_schedule().unwrap();
        assert_eq!(schedule.len(), 2);
        assert_eq!(schedule[0].len(), 1); // task1
        assert_eq!(schedule[1].len(), 2); // task2 and task3 in parallel
    }
}
