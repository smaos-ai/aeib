//! Agent lifecycle management - worktree creation, task execution, cleanup

use crate::git::GitManager;
use crate::types::{Agent, AgentStatus, Task};
use crate::{DispatchError, Result};
use chrono::Utc;
use std::path::PathBuf;
use tokio::fs;
use tokio::process::Command;
use uuid::Uuid;

/// Agent executor - manages worktree lifecycle
pub struct AgentExecutor {
    agent: Agent,
    git: GitManager,
    #[allow(dead_code)]
    repo_path: String,
    worktree_base: String,
}

impl AgentExecutor {
    /// Create new agent executor
    pub fn new(index: u32, repo_path: String, worktree_base: String) -> Self {
        let agent = Agent {
            id: Uuid::new_v4(),
            index,
            status: AgentStatus::Idle,
            assigned_task: None,
            worktree_path: None,
            created_at: Utc::now(),
            last_heartbeat: Utc::now(),
        };

        Self {
            agent,
            git: GitManager::new(&repo_path),
            repo_path,
            worktree_base,
        }
    }

    /// Get agent info
    pub fn agent(&self) -> &Agent {
        &self.agent
    }

    /// Initialize worktree for task execution
    pub async fn initialize_worktree(&mut self, task: &Task) -> Result<()> {
        self.agent.status = AgentStatus::WorktreeInitializing;
        self.agent.assigned_task = Some(task.id);

        let branch_name = format!("agent-{}-task-{}", self.agent.index, task.id);
        let worktree_path = format!("{}/{}", self.worktree_base, branch_name);

        self.git
            .create_worktree(&worktree_path, &branch_name)
            .await?;

        self.agent.worktree_path = Some(worktree_path.clone());
        self.agent.status = AgentStatus::TaskInProgress;

        Ok(())
    }

    /// Write task specification to worktree for agent to read
    pub async fn write_task_specification(&self, task: &Task) -> Result<()> {
        let worktree_path =
            self.agent.worktree_path.as_ref().ok_or_else(|| {
                DispatchError::WorktreeError("No worktree initialized".to_string())
            })?;

        let spec_dir = PathBuf::from(worktree_path).join(".dispatcher");
        fs::create_dir_all(&spec_dir).await?;

        let spec_file = spec_dir.join("task.json");
        let spec_content = serde_json::to_string_pretty(&task)?;
        fs::write(&spec_file, spec_content).await?;

        Ok(())
    }

    /// Execute task in isolated worktree
    pub async fn execute_task(&mut self, task: &Task) -> Result<()> {
        self.agent.status = AgentStatus::TaskInProgress;

        let worktree_path =
            self.agent.worktree_path.as_ref().ok_or_else(|| {
                DispatchError::WorktreeError("No worktree initialized".to_string())
            })?;

        // Write task spec
        self.write_task_specification(task).await?;

        // TODO: Implement actual task execution
        // For now, just run a placeholder command
        let output = Command::new("true")
            .current_dir(worktree_path)
            .output()
            .await
            .map_err(|e| DispatchError::ProcessError(e.to_string()))?;

        if !output.status.success() {
            self.agent.status = AgentStatus::Failed;
            return Err(DispatchError::ProcessError(
                "Task execution failed".to_string(),
            ));
        }

        self.agent.status = AgentStatus::TaskCompleted;
        Ok(())
    }

    /// Poll agent for task completion
    pub async fn check_completion(&mut self) -> Result<bool> {
        self.agent.last_heartbeat = Utc::now();

        match self.agent.status {
            AgentStatus::TaskCompleted | AgentStatus::Failed => Ok(true),
            _ => Ok(false),
        }
    }

    /// Commit changes and prepare for merge
    pub async fn prepare_merge(&mut self) -> Result<()> {
        let worktree_path =
            self.agent.worktree_path.as_ref().ok_or_else(|| {
                DispatchError::WorktreeError("No worktree initialized".to_string())
            })?;

        let task_id = self
            .agent
            .assigned_task
            .ok_or_else(|| DispatchError::WorktreeError("No task assigned".to_string()))?;

        let commit_msg = format!("Task {}: changes from agent {}", task_id, self.agent.index);

        self.git.commit_changes(worktree_path, &commit_msg).await?;

        self.agent.status = AgentStatus::MergingChanges;
        Ok(())
    }

    /// Extract changed files from worktree
    pub async fn get_changed_files(&self) -> Result<Vec<String>> {
        let worktree_path =
            self.agent.worktree_path.as_ref().ok_or_else(|| {
                DispatchError::WorktreeError("No worktree initialized".to_string())
            })?;

        self.git.get_modified_files(worktree_path).await
    }

    /// Cleanup worktree
    pub async fn cleanup(&mut self) -> Result<()> {
        if let Some(worktree_path) = &self.agent.worktree_path {
            self.git.remove_worktree(worktree_path).await?;
            self.agent.worktree_path = None;
        }

        self.agent.assigned_task = None;
        self.agent.status = AgentStatus::Idle;
        self.agent.last_heartbeat = Utc::now();

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_agent_creation() {
        let executor = AgentExecutor::new(0, ".".to_string(), "./.claude/worktrees".to_string());
        assert_eq!(executor.agent.index, 0);
        assert_eq!(executor.agent.status, AgentStatus::Idle);
        assert!(executor.agent.assigned_task.is_none());
    }

    #[test]
    fn test_agent_id_unique() {
        let executor1 = AgentExecutor::new(0, ".".to_string(), "./.claude/worktrees".to_string());
        let executor2 = AgentExecutor::new(1, ".".to_string(), "./.claude/worktrees".to_string());
        assert_ne!(executor1.agent.id, executor2.agent.id);
    }
}
