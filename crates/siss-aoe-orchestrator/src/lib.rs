/// Phase 71: AoeControlTower — Multi-Agent Orchestration Plane
/// Wraps SwarmProvisioner for spawn/kill/status management of autonomous agents

use async_trait::async_trait;
use siss_agent_shell::orchestrator::{
    ProvisionedAgent, ProvisionError, SwarmProvisioner, TmuxSpawner, WorktreeCreator,
};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use thiserror::Error;
use uuid::Uuid;
#[allow(unused_imports)]
use siss_graph_core::node::NodeId;

/// Agent manifest for deployment
#[derive(Debug, Clone)]
pub struct AgentManifest {
    pub agent_id: Uuid,
    pub branch_name: String,
}

/// Errors from AoeControlTower operations
#[derive(Debug, Error, Clone, PartialEq)]
pub enum TowerError {
    #[error("agent not found: {0}")]
    AgentNotFound(Uuid),
    #[error("provision failed: {0}")]
    ProvisionFailed(String),
}

/// Status of the control tower
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ControlTowerStatus {
    pub running: usize,
    pub total: usize,
}

/// AoeControlTower — manages multi-agent orchestration via SwarmProvisioner
#[allow(dead_code)]
pub struct AoeControlTower<T: TmuxSpawner, W: WorktreeCreator> {
    agents: HashMap<Uuid, ProvisionedAgent>,
    provisioner: SwarmProvisioner<T, W>,
}

impl<T: TmuxSpawner, W: WorktreeCreator> AoeControlTower<T, W> {
    /// Create a new control tower with a provisioner
    pub fn new(provisioner: SwarmProvisioner<T, W>) -> Self {
        Self {
            agents: HashMap::new(),
            provisioner,
        }
    }

    /// Spawn a new agent with the given manifest
    pub async fn spawn_agent(&mut self, manifest: AgentManifest) -> Result<Uuid, TowerError> {
        let id = manifest.agent_id;
        let agent = self.provisioner.provision(NodeId(id))
            .await
            .map_err(|e| TowerError::ProvisionFailed(e.to_string()))?;
        self.agents.insert(id, agent);
        Ok(id)
    }

    /// Kill an agent by ID
    pub async fn kill_agent(&mut self, agent_id: Uuid) -> Result<(), TowerError> {
        let agent = self.agents.get(&agent_id)
            .ok_or(TowerError::AgentNotFound(agent_id))?
            .clone();
        let _ = self.provisioner.deprovision(agent).await;
        self.agents.remove(&agent_id);
        Ok(())
    }

    /// List all active agent IDs
    pub fn list_active(&self) -> Vec<Uuid> {
        self.agents.keys().copied().collect()
    }

    /// Get current status of the tower
    pub fn status(&self) -> ControlTowerStatus {
        ControlTowerStatus {
            running: self.agents.len(),
            total: self.agents.len(),
        }
    }
}

// ============================================================================
// Test Helpers (Mock Implementations)
// ============================================================================

/// Mock TmuxSpawner for testing
#[derive(Debug, Clone)]
pub struct MockTmuxSpawner;

#[async_trait]
impl TmuxSpawner for MockTmuxSpawner {
    async fn spawn(&self, _name: &str, _working_dir: &str) -> Result<(), ProvisionError> {
        Ok(())
    }

    async fn kill(&self, _name: &str) {}
}

/// Mock WorktreeCreator for testing
#[derive(Debug, Clone)]
pub struct MockWorktreeCreator;

#[async_trait]
impl WorktreeCreator for MockWorktreeCreator {
    async fn create(&self, _path: &Path, _branch: &str) -> Result<(), ProvisionError> {
        Ok(())
    }

    async fn remove(&self, _path: &Path) -> Result<(), ProvisionError> {
        Ok(())
    }
}

/// Helper to create a test tower with mock components
pub fn make_tower() -> AoeControlTower<MockTmuxSpawner, MockWorktreeCreator> {
    let provisioner = SwarmProvisioner::new(
        MockTmuxSpawner,
        MockWorktreeCreator,
        PathBuf::from("/tmp/test-worktrees"),
    );
    AoeControlTower::new(provisioner)
}

// ============================================================================
// Tests (RED Phase)
// ============================================================================

#[cfg(test)]
mod tests {
    use uuid::Uuid;

    #[tokio::test]
    async fn test_spawn_agent_creates_provisioned_entry() {
        // ensure spawn_agent adds entry to active list
        use crate::{AgentManifest, make_tower};

        let mut tower = make_tower();
        let manifest = AgentManifest {
            agent_id: Uuid::new_v4(),
            branch_name: "test-branch".to_string(),
        };

        let agent_id = manifest.agent_id;
        let result = tower.spawn_agent(manifest).await;

        assert!(result.is_ok());
        assert_eq!(result.unwrap(), agent_id);
        assert!(tower.list_active().contains(&agent_id));
    }

    #[tokio::test]
    async fn test_kill_agent_removes_from_active_list() {
        // ensure kill_agent removes entry from active list
        use crate::{AgentManifest, make_tower};

        let mut tower = make_tower();
        let manifest = AgentManifest {
            agent_id: Uuid::new_v4(),
            branch_name: "test-branch".to_string(),
        };

        let agent_id = manifest.agent_id;
        tower.spawn_agent(manifest).await.unwrap();
        assert!(tower.list_active().contains(&agent_id));

        let result = tower.kill_agent(agent_id).await;
        assert!(result.is_ok());
        assert!(!tower.list_active().contains(&agent_id));
    }

    #[tokio::test]
    async fn test_status_reflects_running_count() {
        // ensure status().running matches count of active agents
        use crate::{AgentManifest, make_tower};

        let mut tower = make_tower();
        assert_eq!(tower.status().running, 0);

        let manifest1 = AgentManifest {
            agent_id: Uuid::new_v4(),
            branch_name: "test-branch-1".to_string(),
        };
        tower.spawn_agent(manifest1).await.unwrap();
        assert_eq!(tower.status().running, 1);

        let manifest2 = AgentManifest {
            agent_id: Uuid::new_v4(),
            branch_name: "test-branch-2".to_string(),
        };
        tower.spawn_agent(manifest2).await.unwrap();
        assert_eq!(tower.status().running, 2);
    }
}
