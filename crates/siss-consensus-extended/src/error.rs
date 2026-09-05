use thiserror::Error;

#[derive(Error, Debug)]
pub enum ConsensusError {
    #[error("Invalid node ID")]
    InvalidNodeId,
    #[error("Too few replicas (minimum 4)")]
    TooFewReplicas,
    #[error("Invalid message")]
    InvalidMessage,
    #[error("Duplicate message")]
    DuplicateMessage,
    #[error("Merkle tree error: {0}")]
    MerkleError(String),
    #[error("Invalid signature")]
    InvalidSignature,
    #[error("Commit failed: {0}")]
    CommitFailed(String),
    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),
}

pub type Result<T> = std::result::Result<T, ConsensusError>;
