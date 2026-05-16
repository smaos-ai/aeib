use crate::memory::EphemeralBuffer;
use std::sync::Arc;

/// Immutable snapshot of thought-tool-action trajectory from EphemeralBuffer.
#[derive(Debug, Clone)]
pub struct GhostBranchBuffer {
    trajectory: Vec<String>,
}

impl GhostBranchBuffer {
    pub fn from_trajectory(trajectory: Vec<String>) -> Self {
        Self { trajectory }
    }

    pub fn len(&self) -> usize {
        self.trajectory.len()
    }

    pub fn is_empty(&self) -> bool {
        self.trajectory.is_empty()
    }

    pub fn get(&self, index: usize) -> Option<&str> {
        self.trajectory.get(index).map(|s| s.as_str())
    }

    pub fn iter(&self) -> impl Iterator<Item = &str> {
        self.trajectory.iter().map(|s| s.as_str())
    }

    pub fn trajectory_len(&self) -> usize {
        self.trajectory.len()
    }

    pub fn thought_at(&self, index: usize) -> Option<&str> {
        self.trajectory.get(index).map(|s| s.as_str())
    }

    pub fn tool_at(&self, index: usize) -> Option<&str> {
        self.trajectory.get(index).map(|s| s.as_str())
    }

    pub fn action_at(&self, index: usize) -> Option<&str> {
        self.trajectory.get(index).map(|s| s.as_str())
    }
}

/// Extracts exact trajectory from EphemeralBuffer before flush.
pub struct TrajectoryExtractor {
    ephemeral: Arc<EphemeralBuffer>,
}

impl TrajectoryExtractor {
    pub fn new(ephemeral: Arc<EphemeralBuffer>) -> Self {
        Self { ephemeral }
    }

    pub async fn extract(&self) -> Result<GhostBranchBuffer, String> {
        let snapshot = self.ephemeral.snapshot().await;
        Ok(GhostBranchBuffer::from_trajectory(snapshot))
    }
}
