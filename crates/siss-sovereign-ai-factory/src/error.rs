//! Error types for Sovereign AI Factory

use thiserror::Error;

pub type Result<T> = std::result::Result<T, Error>;

#[derive(Error, Debug)]
pub enum Error {
    #[error("Node discovery failed: {0}")]
    DiscoveryError(String),

    #[error("Node not found: {0}")]
    NodeNotFound(String),

    #[error("Cluster quorum not met: {0}/{1}")]
    QuorumNotMet(usize, usize),

    #[error("Load balance failed: no healthy nodes available")]
    NoHealthyNodes,

    #[error("Gossip consensus failed: {0}")]
    ConsensusError(String),

    #[error("Merkle verification failed: {0}")]
    MerkleVerificationFailed(String),

    #[error("Invalid cluster configuration: {0}")]
    InvalidConfig(String),

    #[error("Model version mismatch: local={local}, cluster={cluster}")]
    ModelVersionMismatch { local: String, cluster: String },

    #[error("Air-gap violation detected: {0}")]
    AirGapViolation(String),

    #[error("Node unhealthy: {0}")]
    NodeUnhealthy(String),

    #[error("Timeout: {0}")]
    Timeout(String),

    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),

    #[error("Serialization error: {0}")]
    SerializationError(#[from] serde_json::Error),
}
