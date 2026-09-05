//! Core dispatcher executor - orchestrates parallel agent task execution

use crate::Result;
use crate::agent::AgentExecutor;
use crate::git::GitManager;
use crate::queue::TaskQueue;
use crate::types::{Agent, AgentStatus, ExecutorConfig, MergeResult, Task, TaskStatus};
use std::collections::HashMap;
use std::time::Duration;
use uuid::Uuid;

/// Main dispatcher executor - manages N concurrent agents and task queue
pub struct Executor {
    config: ExecutorConfig,
    queue: TaskQueue,
    agents: HashMap<Uuid, AgentExecutor>,
    #[allow(dead_code)]
    git: GitManager,
}

impl Executor {
    /// Create new executor with config
    pub async fn new(config: ExecutorConfig) -> Result<Self> {
        let queue = TaskQueue::load(config.queue_file.clone()).await?;

        Ok(Self {
            git: GitManager::new(&config.repo_path),
            config,
            queue,
            agents: HashMap::new(),
        })
    }

    /// Spawn N agents and initialize them
    pub async fn spawn_agents(&mut self, count: u32) -> Result<Vec<Agent>> {
        let actual_count = std::cmp::min(count, self.config.max_agents);

        let mut agents = Vec::new();
        for i in 0..actual_count {
            let executor = AgentExecutor::new(
                i,
                self.config.repo_path.clone(),
                self.config.worktree_base.clone(),
            );

            let agent = executor.agent().clone();
            self.agents.insert(agent.id, executor);
            agents.push(agent);
        }

        Ok(agents)
    }

    /// Get agent by ID
    pub fn get_agent(&self, id: Uuid) -> Option<&AgentExecutor> {
        self.agents.get(&id)
    }

    /// Get mutable agent by ID
    fn get_agent_mut(&mut self, id: Uuid) -> Option<&mut AgentExecutor> {
        self.agents.get_mut(&id)
    }

    /// Assign next available task to an idle agent
    pub async fn assign_next_task(&mut self) -> Result<Option<(Uuid, Task)>> {
        // Find idle agent
        let idle_agent_id = self
            .agents
            .iter()
            .find(|(_, executor)| executor.agent().status == AgentStatus::Idle)
            .map(|(id, _)| *id);

        if let Some(agent_id) = idle_agent_id {
            // Find next unassigned task
            if let Some(task) = self.queue.next_unassigned() {
                let executor = self.get_agent_mut(agent_id).unwrap();

                // Initialize worktree
                executor.initialize_worktree(&task).await?;
                executor.execute_task(&task).await?;

                // Update queue
                self.queue.update_status(task.id, TaskStatus::Assigned)?;
                self.queue.save().await?;

                return Ok(Some((agent_id, task)));
            }
        }

        Ok(None)
    }

    /// Poll all agents for task completion
    pub async fn poll_agents(&mut self) -> Result<Vec<(Uuid, Task)>> {
        let mut completed = Vec::new();

        let agent_ids: Vec<_> = self.agents.keys().copied().collect();

        for agent_id in agent_ids {
            if let Some(executor) = self.get_agent_mut(agent_id) {
                if executor.check_completion().await? {
                    if let Some(task_id) = executor.agent().assigned_task {
                        // Get task from queue
                        if let Some(task) = self.queue.get(task_id).cloned() {
                            completed.push((agent_id, task));
                        }
                    }
                }
            }
        }

        Ok(completed)
    }

    /// Prepare completed tasks for merge and cleanup agents
    pub async fn finalize_tasks(&mut self, completed_tasks: Vec<(Uuid, Task)>) -> Result<()> {
        for (agent_id, task) in completed_tasks {
            if let Some(executor) = self.get_agent_mut(agent_id) {
                executor.prepare_merge().await?;
                self.queue.update_status(task.id, TaskStatus::Completed)?;
            }
        }

        self.queue.save().await?;
        Ok(())
    }

    /// Orchestrate merge of completed tasks back to main
    pub async fn merge_completed_tasks(&mut self) -> Result<Vec<MergeResult>> {
        // TODO: Implement topological sort by dependencies
        let completed_tasks: Vec<_> = self
            .queue
            .all()
            .into_iter()
            .filter(|t| t.status == TaskStatus::Completed)
            .collect();

        let mut merge_results = Vec::new();

        for task in completed_tasks {
            let agent_id = task.assigned_to.ok_or_else(|| {
                crate::DispatchError::MergeFailed("Task has no assigned agent".to_string())
            })?;

            let branch_name = format!("agent-{}-task-{}", 0, task.id); // TODO: Get actual agent index

            // Check for conflicts
            let conflicts = self.git.check_merge_conflicts(&branch_name, "main").await?;

            let result = if conflicts.is_empty() {
                // Auto-merge if no conflicts
                match self.git.merge_branch(&branch_name, "main").await {
                    Ok(_) => MergeResult {
                        task_id: task.id,
                        agent_id,
                        success: true,
                        conflicts: vec![],
                        merged_files: Vec::new(),
                        error: None,
                    },
                    Err(e) => {
                        // Abort merge and mark as failed
                        let _ = self.git.abort_merge().await;
                        MergeResult {
                            task_id: task.id,
                            agent_id,
                            success: false,
                            conflicts: vec![],
                            merged_files: Vec::new(),
                            error: Some(e.to_string()),
                        }
                    }
                }
            } else {
                // Flag conflict for manual resolution
                MergeResult {
                    task_id: task.id,
                    agent_id,
                    success: false,
                    conflicts: conflicts.clone(),
                    merged_files: Vec::new(),
                    error: Some(format!("Merge conflict: {:?}", conflicts)),
                }
            };

            merge_results.push(result);
        }

        Ok(merge_results)
    }

    /// Cleanup all agent worktrees
    pub async fn cleanup_agents(&mut self) -> Result<()> {
        for executor in self.agents.values_mut() {
            let _ = executor.cleanup().await;
        }

        Ok(())
    }

    /// Add task to queue
    pub async fn queue_task(&mut self, task: Task) -> Result<()> {
        self.queue.check_circular_dependencies()?;
        self.queue.enqueue(task)?;
        self.queue.save().await?;
        Ok(())
    }

    /// Get queue status
    pub fn queue_status(&self) -> (usize, usize, usize) {
        let all_tasks = self.queue.all();
        let pending = all_tasks
            .iter()
            .filter(|t| t.status == TaskStatus::Pending)
            .count();
        let in_progress = all_tasks
            .iter()
            .filter(|t| t.status == TaskStatus::InProgress)
            .count();
        let completed = all_tasks
            .iter()
            .filter(|t| t.status == TaskStatus::Completed)
            .count();

        (pending, in_progress, completed)
    }

    /// Get all agents status
    pub fn agents_status(&self) -> Vec<Agent> {
        self.agents
            .values()
            .map(|executor| executor.agent().clone())
            .collect()
    }

    /// Run main dispatch loop
    pub async fn run_loop(&mut self, max_iterations: Option<u32>) -> Result<()> {
        let mut iterations = 0;

        loop {
            if let Some(max) = max_iterations {
                if iterations >= max {
                    break;
                }
            }

            // Try to assign tasks to idle agents
            while self.assign_next_task().await?.is_some() {}

            // Poll all agents for completion
            let completed = self.poll_agents().await?;

            // Finalize completed tasks
            if !completed.is_empty() {
                self.finalize_tasks(completed).await?;
            }

            // Check if all tasks are done
            let (pending, in_progress, _) = self.queue_status();
            if pending == 0 && in_progress == 0 {
                break;
            }

            // TODO: Implement configurable polling interval
            tokio::time::sleep(Duration::from_millis(500)).await;
            iterations += 1;
        }

        // Merge all completed tasks
        let merge_results = self.merge_completed_tasks().await?;
        tracing::info!("Merge results: {:?}", merge_results);

        // Cleanup
        self.cleanup_agents().await?;

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_executor_creation() {
        let tempdir = tempfile::tempdir().unwrap();
        let config = ExecutorConfig {
            max_agents: 2,
            queue_file: tempdir
                .path()
                .join("queue.json")
                .to_string_lossy()
                .to_string(),
            ..Default::default()
        };

        let executor = Executor::new(config).await.unwrap();
        assert_eq!(executor.config.max_agents, 2);
    }

    #[tokio::test]
    async fn test_spawn_agents() {
        let tempdir = tempfile::tempdir().unwrap();
        let config = ExecutorConfig {
            max_agents: 3,
            queue_file: tempdir
                .path()
                .join("queue.json")
                .to_string_lossy()
                .to_string(),
            ..Default::default()
        };

        let mut executor = Executor::new(config).await.unwrap();
        let agents = executor.spawn_agents(5).await.unwrap();

        // Should cap at max_agents
        assert_eq!(agents.len(), 3);

        for (i, agent) in agents.iter().enumerate() {
            assert_eq!(agent.index, i as u32);
            assert_eq!(agent.status, AgentStatus::Idle);
        }
    }

    #[tokio::test]
    async fn test_queue_status() {
        let tempdir = tempfile::tempdir().unwrap();
        let config = ExecutorConfig {
            queue_file: tempdir
                .path()
                .join("queue.json")
                .to_string_lossy()
                .to_string(),
            ..Default::default()
        };
        let executor = Executor::new(config).await.unwrap();

        let (pending, in_progress, completed) = executor.queue_status();
        assert_eq!(pending, 0);
        assert_eq!(in_progress, 0);
        assert_eq!(completed, 0);
    }
}
