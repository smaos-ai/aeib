//! Checkpoint manager: failure recovery and state persistence

use crate::error::{Error, Result};
use crate::types::{Checkpoint, CheckpointId, ExecutionId, TaskExecution};
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;

/// Checkpoint configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CheckpointConfig {
    pub auto_checkpoint: bool,
    pub checkpoint_interval_ms: u64,
    pub max_checkpoints: usize,
}

impl Default for CheckpointConfig {
    fn default() -> Self {
        Self {
            auto_checkpoint: true,
            checkpoint_interval_ms: 5000,
            max_checkpoints: 10,
        }
    }
}

/// Checkpoint manager: persists state for recovery
pub struct CheckpointManager {
    config: CheckpointConfig,
    checkpoints: Arc<RwLock<HashMap<CheckpointId, Checkpoint>>>,
    latest_by_execution: Arc<RwLock<HashMap<ExecutionId, CheckpointId>>>,
}

impl CheckpointManager {
    /// Create new checkpoint manager
    pub fn new(config: CheckpointConfig) -> Self {
        Self {
            config,
            checkpoints: Arc::new(RwLock::new(HashMap::new())),
            latest_by_execution: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Create checkpoint from current state
    pub fn create_checkpoint(
        &self,
        execution_id: ExecutionId,
        task_states: HashMap<String, TaskExecution>,
    ) -> Result<Checkpoint> {
        let checkpoint = Checkpoint {
            id: CheckpointId::new(),
            execution_id,
            task_states,
            created_at: chrono::Utc::now(),
            recoverable: true,
        };

        let mut checkpoints = self.checkpoints.write();
        let mut latest = self.latest_by_execution.write();

        // Enforce max checkpoints per execution
        let exec_checkpoints: Vec<_> = checkpoints
            .iter()
            .filter(|(_, cp)| cp.execution_id == execution_id)
            .map(|(id, _)| *id)
            .collect();

        if exec_checkpoints.len() >= self.config.max_checkpoints {
            if let Some(oldest_id) = exec_checkpoints.first() {
                checkpoints.remove(oldest_id);
            }
        }

        checkpoints.insert(checkpoint.id, checkpoint.clone());
        latest.insert(execution_id, checkpoint.id);

        Ok(checkpoint)
    }

    /// Recover from latest checkpoint
    pub fn recover(&self, execution_id: ExecutionId) -> Result<Checkpoint> {
        let latest = self.latest_by_execution.read();

        if let Some(checkpoint_id) = latest.get(&execution_id) {
            let checkpoints = self.checkpoints.read();
            checkpoints
                .get(checkpoint_id)
                .cloned()
                .ok_or(Error::CheckpointError("Checkpoint not found".to_string()))
        } else {
            Err(Error::CheckpointError("No checkpoint for execution".to_string()))
        }
    }

    /// Get checkpoint by ID
    pub fn get_checkpoint(&self, checkpoint_id: CheckpointId) -> Option<Checkpoint> {
        self.checkpoints.read().get(&checkpoint_id).cloned()
    }

    /// Mark checkpoint as unrecoverable
    pub fn mark_unrecoverable(&self, checkpoint_id: CheckpointId) -> Result<()> {
        let mut checkpoints = self.checkpoints.write();

        if let Some(cp) = checkpoints.get_mut(&checkpoint_id) {
            cp.recoverable = false;
            Ok(())
        } else {
            Err(Error::CheckpointError("Checkpoint not found".to_string()))
        }
    }

    /// Get checkpoint count for execution
    pub fn checkpoint_count(&self, execution_id: ExecutionId) -> usize {
        self.checkpoints
            .read()
            .values()
            .filter(|cp| cp.execution_id == execution_id)
            .count()
    }

    /// Get total checkpoint count
    pub fn total_checkpoints(&self) -> usize {
        self.checkpoints.read().len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_manager_creation() {
        let manager = CheckpointManager::new(CheckpointConfig::default());
        assert_eq!(manager.total_checkpoints(), 0);
    }

    #[test]
    fn test_create_checkpoint() {
        let manager = CheckpointManager::new(CheckpointConfig::default());
        let exec_id = ExecutionId::new();

        let result = manager.create_checkpoint(exec_id, HashMap::new());
        assert!(result.is_ok());
        assert_eq!(manager.checkpoint_count(exec_id), 1);
    }

    #[test]
    fn test_recover_from_checkpoint() {
        let manager = CheckpointManager::new(CheckpointConfig::default());
        let exec_id = ExecutionId::new();

        let checkpoint = manager.create_checkpoint(exec_id, HashMap::new()).unwrap();
        let recovered = manager.recover(exec_id).unwrap();

        assert_eq!(checkpoint.id, recovered.id);
    }

    #[test]
    fn test_recover_nonexistent() {
        let manager = CheckpointManager::new(CheckpointConfig::default());
        let result = manager.recover(ExecutionId::new());
        assert!(result.is_err());
    }

    #[test]
    fn test_max_checkpoints_enforcement() {
        let mut config = CheckpointConfig::default();
        config.max_checkpoints = 2;
        let manager = CheckpointManager::new(config);
        let exec_id = ExecutionId::new();

        manager.create_checkpoint(exec_id, HashMap::new()).unwrap();
        manager.create_checkpoint(exec_id, HashMap::new()).unwrap();
        manager.create_checkpoint(exec_id, HashMap::new()).unwrap();

        assert!(manager.checkpoint_count(exec_id) <= 2);
    }

    #[test]
    fn test_mark_unrecoverable() {
        let manager = CheckpointManager::new(CheckpointConfig::default());
        let exec_id = ExecutionId::new();

        let checkpoint = manager.create_checkpoint(exec_id, HashMap::new()).unwrap();
        let result = manager.mark_unrecoverable(checkpoint.id);
        assert!(result.is_ok());

        let marked = manager.get_checkpoint(checkpoint.id).unwrap();
        assert!(!marked.recoverable);
    }
}
