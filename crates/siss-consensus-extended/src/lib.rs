//! # SISS Consensus Extended
//! Real PBFT consensus with Merkle checkpoints and view change support.
//!
//! Integration point for Phase 1 L8 (proof layer) - marked for Jun 2027.

pub mod pbft;
pub mod merkle;
pub mod view_change;
pub mod error;

pub use error::{ConsensusError, Result};
pub use pbft::PBFTConsensus;
pub use merkle::MerkleCheckpoint;

#[cfg(test)]
mod tests;

/// Consensus configuration
#[derive(Clone, Debug)]
pub struct ConsensusConfig {
    /// Node ID (0-indexed)
    pub node_id: u32,
    /// Total replicas in cluster
    pub total_replicas: u32,
    /// View number
    pub view: u64,
    /// Timeout for commit (ms)
    pub commit_timeout_ms: u64,
}

impl ConsensusConfig {
    /// Create new config with validation
    pub fn new(node_id: u32, total_replicas: u32) -> Result<Self> {
        if node_id >= total_replicas {
            return Err(ConsensusError::InvalidNodeId);
        }
        if total_replicas < 4 {
            return Err(ConsensusError::TooFewReplicas);
        }
        Ok(Self {
            node_id,
            total_replicas,
            view: 0,
            commit_timeout_ms: 5000,
        })
    }

    /// Quorum size for this config (f+1 where f = (n-1)/3)
    pub fn quorum_size(&self) -> u32 {
        (self.total_replicas / 3) + 1
    }

    /// Primary node ID for current view
    pub fn primary(&self) -> u32 {
        (self.view as u32) % self.total_replicas
    }

    /// Is this node the primary?
    pub fn is_primary(&self) -> bool {
        self.node_id == self.primary()
    }
}

#[cfg(test)]
mod config_tests {
    use super::*;

    #[test]
    fn test_config_validation() {
        assert!(ConsensusConfig::new(0, 3).is_err());
        assert!(ConsensusConfig::new(5, 4).is_err());
        assert!(ConsensusConfig::new(0, 4).is_ok());
    }

    #[test]
    fn test_quorum_size() {
        let config = ConsensusConfig::new(0, 4).unwrap();
        assert_eq!(config.quorum_size(), 2);
        let config = ConsensusConfig::new(0, 7).unwrap();
        assert_eq!(config.quorum_size(), 3);
    }

    #[test]
    fn test_primary_rotation() {
        let mut config = ConsensusConfig::new(0, 4).unwrap();
        assert_eq!(config.primary(), 0);
        config.view = 1;
        assert_eq!(config.primary(), 1);
        config.view = 4;
        assert_eq!(config.primary(), 0);
    }
}
