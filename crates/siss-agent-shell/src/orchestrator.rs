/// Phase 40: SwarmProvisioner — atomic worktree + tmux provisioning
/// Fail-closed: both succeed or neither. Atomic ordering enforced.
use siss_graph_core::node::NodeId;
use std::path::{Path, PathBuf};
use thiserror::Error;

/// Trait for tmux session management (abstracted for testing)
#[async_trait::async_trait]
pub trait TmuxSpawner: Send + Sync {
    async fn spawn(&self, name: &str, working_dir: &str) -> Result<(), ProvisionError>;
    async fn kill(&self, name: &str);
}

/// Trait for git worktree management (abstracted for testing)
#[async_trait::async_trait]
pub trait WorktreeCreator: Send + Sync {
    async fn create(&self, path: &Path, branch: &str) -> Result<(), ProvisionError>;
    async fn remove(&self, path: &Path) -> Result<(), ProvisionError>;
}

/// Result of a successful provisioning
#[derive(Debug, Clone)]
pub struct ProvisionedAgent {
    pub session_id: NodeId,
    pub worktree_path: PathBuf,
    pub branch_name: String,
    pub tmux_name: String,
}

/// Provision/deprovision errors
#[derive(Debug, Error, Clone, PartialEq)]
pub enum ProvisionError {
    #[error("worktree creation failed: {0}")]
    WorktreeFailed(String),
    #[error("tmux spawn failed: {0}")]
    TmuxFailed(String),
}

/// SwarmProvisioner — manages atomic provisioning with fail-closed invariant
pub struct SwarmProvisioner<T: TmuxSpawner, W: WorktreeCreator> {
    tmux: T,
    worktree: W,
    worktree_base: PathBuf,
}

impl<T: TmuxSpawner, W: WorktreeCreator> SwarmProvisioner<T, W> {
    pub fn new(tmux: T, worktree: W, worktree_base: PathBuf) -> Self {
        Self {
            tmux,
            worktree,
            worktree_base,
        }
    }

    /// Provision: create_worktree → spawn_tmux (fail-closed: both or neither)
    pub async fn provision(&self, agent_id: NodeId) -> Result<ProvisionedAgent, ProvisionError> {
        let branch_name = format!("agent-{}", agent_id.0);
        let worktree_path = self.worktree_base.join(format!("agent-{}", agent_id.0));
        let tmux_name = format!("siss-agent-{}", agent_id.0);

        // Step 1: Create worktree (fail-closed if this fails)
        self.worktree
            .create(&worktree_path, &branch_name)
            .await
            .map_err(|e| {
                // Worktree creation failed — don't proceed to tmux
                e
            })?;

        // Step 2: Spawn tmux (fail-closed: cleanup worktree if this fails)
        if let Err(e) = self
            .tmux
            .spawn(&tmux_name, worktree_path.to_str().unwrap_or(""))
            .await
        {
            // Tmux spawn failed — cleanup worktree before returning
            let _ = self.worktree.remove(&worktree_path).await;
            return Err(e);
        }

        Ok(ProvisionedAgent {
            session_id: agent_id,
            worktree_path,
            branch_name,
            tmux_name,
        })
    }

    /// Deprovision: kill_tmux → remove_worktree (reverse of provision order)
    pub async fn deprovision(&self, agent: ProvisionedAgent) -> Result<(), ProvisionError> {
        // Step 1: Kill tmux first
        self.tmux.kill(&agent.tmux_name).await;

        // Step 2: Remove worktree
        self.worktree.remove(&agent.worktree_path).await
    }
}
