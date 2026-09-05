//! Git operations for worktree management and merging

use crate::{DispatchError, Result};
use std::path::{Path, PathBuf};
use tokio::process::Command;

/// Git wrapper for worktree and merge operations
pub struct GitManager {
    #[allow(dead_code)]
    repo_path: PathBuf,
}

impl GitManager {
    /// Create new git manager
    pub fn new<P: AsRef<Path>>(repo_path: P) -> Self {
        Self {
            repo_path: repo_path.as_ref().to_path_buf(),
        }
    }

    /// Create a new worktree for task execution
    pub async fn create_worktree(&self, worktree_path: &str, branch_name: &str) -> Result<()> {
        let output = Command::new("git")
            .current_dir(&self.repo_path)
            .args(["worktree", "add", worktree_path, "-b", branch_name])
            .output()
            .await
            .map_err(|e| DispatchError::ProcessError(e.to_string()))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr).to_string();
            return Err(DispatchError::WorktreeError(format!(
                "Failed to create worktree: {}",
                stderr
            )));
        }

        Ok(())
    }

    /// Remove a worktree
    pub async fn remove_worktree(&self, worktree_path: &str) -> Result<()> {
        let output = Command::new("git")
            .current_dir(&self.repo_path)
            .args(["worktree", "remove", worktree_path])
            .output()
            .await
            .map_err(|e| DispatchError::ProcessError(e.to_string()))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr).to_string();
            return Err(DispatchError::WorktreeError(format!(
                "Failed to remove worktree: {}",
                stderr
            )));
        }

        Ok(())
    }

    /// Get list of modified files in worktree
    pub async fn get_modified_files(&self, worktree_path: &str) -> Result<Vec<String>> {
        let output = Command::new("git")
            .current_dir(worktree_path)
            .args(["status", "--short"])
            .output()
            .await
            .map_err(|e| DispatchError::ProcessError(e.to_string()))?;

        if !output.status.success() {
            return Ok(Vec::new());
        }

        let stdout = String::from_utf8_lossy(&output.stdout);
        let files: Vec<String> = stdout
            .lines()
            .filter_map(|line| {
                if line.len() > 3 {
                    Some(line[3..].to_string())
                } else {
                    None
                }
            })
            .collect();

        Ok(files)
    }

    /// Check if merge would have conflicts
    pub async fn check_merge_conflicts(
        &self,
        _merge_branch: &str,
        _target_branch: &str,
    ) -> Result<Vec<String>> {
        // Create a test merge in a temporary worktree
        // TODO: Implement dry-run merge with conflict detection
        Ok(Vec::new())
    }

    /// Merge branch into target
    pub async fn merge_branch(&self, merge_branch: &str, target_branch: &str) -> Result<()> {
        // Switch to target branch
        let output = Command::new("git")
            .current_dir(&self.repo_path)
            .args(["checkout", target_branch])
            .output()
            .await
            .map_err(|e| DispatchError::ProcessError(e.to_string()))?;

        if !output.status.success() {
            return Err(DispatchError::GitError(
                "Failed to checkout target branch".to_string(),
            ));
        }

        // Attempt merge
        let output = Command::new("git")
            .current_dir(&self.repo_path)
            .args(["merge", "--no-edit", merge_branch])
            .output()
            .await
            .map_err(|e| DispatchError::ProcessError(e.to_string()))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr).to_string();
            if stderr.contains("CONFLICT") {
                // TODO: Parse conflict markers to identify files
                return Err(DispatchError::MergeConflict {
                    files: vec!["TODO: parse conflicts".to_string()],
                });
            }
            return Err(DispatchError::MergeFailed(stderr));
        }

        Ok(())
    }

    /// Abort merge in progress
    pub async fn abort_merge(&self) -> Result<()> {
        let output = Command::new("git")
            .current_dir(&self.repo_path)
            .args(["merge", "--abort"])
            .output()
            .await
            .map_err(|e| DispatchError::ProcessError(e.to_string()))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr).to_string();
            return Err(DispatchError::RollbackFailed(stderr));
        }

        Ok(())
    }

    /// Get current branch
    pub async fn current_branch(&self) -> Result<String> {
        let output = Command::new("git")
            .current_dir(&self.repo_path)
            .args(["rev-parse", "--abbrev-ref", "HEAD"])
            .output()
            .await
            .map_err(|e| DispatchError::ProcessError(e.to_string()))?;

        if !output.status.success() {
            return Err(DispatchError::GitError(
                "Failed to get current branch".to_string(),
            ));
        }

        Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
    }

    /// Commit changes in worktree
    pub async fn commit_changes(&self, worktree_path: &str, message: &str) -> Result<()> {
        // Add all changes
        let output = Command::new("git")
            .current_dir(worktree_path)
            .args(["add", "."])
            .output()
            .await
            .map_err(|e| DispatchError::ProcessError(e.to_string()))?;

        if !output.status.success() {
            return Err(DispatchError::GitError(
                "Failed to stage changes".to_string(),
            ));
        }

        // Commit
        let output = Command::new("git")
            .current_dir(worktree_path)
            .args(["commit", "-m", message])
            .output()
            .await
            .map_err(|e| DispatchError::ProcessError(e.to_string()))?;

        if !output.status.success() {
            // OK if nothing to commit
            let stderr = String::from_utf8_lossy(&output.stderr).to_string();
            if !stderr.contains("nothing to commit") {
                return Err(DispatchError::GitError(
                    "Failed to commit changes".to_string(),
                ));
            }
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_git_manager_creation() {
        let mgr = GitManager::new(".");
        assert!(mgr.repo_path.to_string_lossy().len() > 0);
    }
}
