//! Task queue management with dependency tracking and persistence

use crate::Result;
use crate::lock::FileLock;
use crate::types::{Id, Task, TaskStatus};
use std::collections::{HashMap, VecDeque};
use std::path::Path;
use std::time::Duration;
use tokio::fs;

/// In-memory task queue with file persistence
pub struct TaskQueue {
    tasks: VecDeque<Task>,
    by_id: HashMap<Id, usize>, // Index in VecDeque
    queue_file: String,
    lock_path: String,
}

impl TaskQueue {
    /// Create new empty queue
    pub fn new(queue_file: String) -> Self {
        Self {
            tasks: VecDeque::new(),
            by_id: HashMap::new(),
            lock_path: format!("{}.lock", queue_file),
            queue_file,
        }
    }

    /// Load queue from file
    pub async fn load(queue_file: String) -> Result<Self> {
        let lock_path = format!("{}.lock", queue_file);

        // Ensure parent directory exists
        if let Some(parent) = Path::new(&queue_file).parent() {
            if parent.to_string_lossy().len() > 0 {
                fs::create_dir_all(parent).await.ok();
            }
        }

        let _lock = FileLock::acquire(&lock_path, Duration::from_secs(5)).await?;

        let mut queue = Self::new(queue_file);

        if Path::new(&queue.queue_file).exists() {
            let content = fs::read_to_string(&queue.queue_file).await?;
            let tasks: Vec<Task> = serde_json::from_str(&content)?;
            for (idx, task) in tasks.into_iter().enumerate() {
                queue.by_id.insert(task.id, idx);
                queue.tasks.push_back(task);
            }
        }

        _lock.release().await?;
        Ok(queue)
    }

    /// Save queue to file
    pub async fn save(&self) -> Result<()> {
        let _lock = FileLock::acquire(&self.lock_path, Duration::from_secs(5)).await?;

        let tasks: Vec<_> = self.tasks.iter().cloned().collect();
        let content = serde_json::to_string_pretty(&tasks)?;

        fs::create_dir_all(
            Path::new(&self.queue_file)
                .parent()
                .unwrap_or_else(|| Path::new(".")),
        )
        .await?;

        fs::write(&self.queue_file, content).await?;
        _lock.release().await?;
        Ok(())
    }

    /// Add task to queue
    pub fn enqueue(&mut self, task: Task) -> Result<()> {
        if self.by_id.contains_key(&task.id) {
            return Err(crate::DispatchError::QueueError(
                "Task already in queue".to_string(),
            ));
        }

        let idx = self.tasks.len();
        self.by_id.insert(task.id, idx);
        self.tasks.push_back(task);
        Ok(())
    }

    /// Get next unassigned task, respecting dependencies
    pub fn next_unassigned(&self) -> Option<Task> {
        for task in &self.tasks {
            if task.status == TaskStatus::Pending && self.can_execute(task) {
                return Some(task.clone());
            }
        }
        None
    }

    /// Check if task has all dependencies met
    fn can_execute(&self, task: &Task) -> bool {
        task.dependencies.iter().all(|dep| {
            if let Some(idx) = self.by_id.get(&dep.task_id) {
                if let Some(t) = self.tasks.get(*idx) {
                    return t.status == TaskStatus::Completed;
                }
            }
            false
        })
    }

    /// Get task by ID
    pub fn get(&self, id: Id) -> Option<&Task> {
        self.by_id.get(&id).and_then(|idx| self.tasks.get(*idx))
    }

    /// Update task status
    pub fn update_status(&mut self, id: Id, status: TaskStatus) -> Result<()> {
        let idx = self
            .by_id
            .get(&id)
            .copied()
            .ok_or_else(|| crate::DispatchError::TaskNotFound(id.to_string()))?;

        if let Some(task) = self.tasks.get_mut(idx) {
            task.status = status;
            Ok(())
        } else {
            Err(crate::DispatchError::TaskNotFound(id.to_string()))
        }
    }

    /// Get all tasks
    pub fn all(&self) -> Vec<Task> {
        self.tasks.iter().cloned().collect()
    }

    /// Get task count
    pub fn len(&self) -> usize {
        self.tasks.len()
    }

    /// Check if queue is empty
    pub fn is_empty(&self) -> bool {
        self.tasks.is_empty()
    }

    /// Detect circular dependencies in task graph
    pub fn check_circular_dependencies(&self) -> Result<()> {
        let mut visited = std::collections::HashSet::new();
        let mut rec_stack = std::collections::HashSet::new();

        for task in &self.tasks {
            if !visited.contains(&task.id) {
                self.dfs(&mut visited, &mut rec_stack, task.id)?;
            }
        }

        Ok(())
    }

    fn dfs(
        &self,
        visited: &mut std::collections::HashSet<Id>,
        rec_stack: &mut std::collections::HashSet<Id>,
        node: Id,
    ) -> Result<()> {
        visited.insert(node);
        rec_stack.insert(node);

        if let Some(task) = self.get(node) {
            for dep in &task.dependencies {
                if !visited.contains(&dep.task_id) {
                    self.dfs(visited, rec_stack, dep.task_id)?;
                } else if rec_stack.contains(&dep.task_id) {
                    return Err(crate::DispatchError::CircularDependency);
                }
            }
        }

        rec_stack.remove(&node);
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;

    #[tokio::test]
    async fn test_enqueue_and_get() {
        let mut queue = TaskQueue::new(".test_queue.json".to_string());
        let task = Task {
            id: uuid::Uuid::new_v4(),
            name: "test".to_string(),
            description: None,
            specification: serde_json::json!({}),
            status: TaskStatus::Pending,
            assigned_to: None,
            retry_count: 0,
            created_at: Utc::now(),
            started_at: None,
            completed_at: None,
            dependencies: vec![],
        };

        queue.enqueue(task.clone()).unwrap();
        assert_eq!(queue.len(), 1);
        assert_eq!(queue.get(task.id), Some(&task));
    }

    #[tokio::test]
    async fn test_circular_dependency_detection() {
        let task1_id = uuid::Uuid::new_v4();
        let task2_id = uuid::Uuid::new_v4();

        let mut queue = TaskQueue::new(".test_queue.json".to_string());

        let task1 = Task {
            id: task1_id,
            name: "task1".to_string(),
            description: None,
            specification: serde_json::json!({}),
            status: TaskStatus::Pending,
            assigned_to: None,
            retry_count: 0,
            created_at: Utc::now(),
            started_at: None,
            completed_at: None,
            dependencies: vec![crate::types::TaskDependency {
                task_id: task2_id,
                dep_type: crate::types::DependencyType::BlockedBy,
            }],
        };

        let task2 = Task {
            id: task2_id,
            name: "task2".to_string(),
            description: None,
            specification: serde_json::json!({}),
            status: TaskStatus::Pending,
            assigned_to: None,
            retry_count: 0,
            created_at: Utc::now(),
            started_at: None,
            completed_at: None,
            dependencies: vec![crate::types::TaskDependency {
                task_id: task1_id,
                dep_type: crate::types::DependencyType::BlockedBy,
            }],
        };

        queue.enqueue(task1).unwrap();
        queue.enqueue(task2).unwrap();

        let result = queue.check_circular_dependencies();
        assert!(matches!(
            result,
            Err(crate::DispatchError::CircularDependency)
        ));
    }
}
