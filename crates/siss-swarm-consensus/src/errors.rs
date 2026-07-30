use thiserror::Error;

#[derive(Debug, Error, Clone)]
pub enum BftConsensusError {
    #[error("Insufficient quorum reached: got {got}/{required}")]
    InsufficientQuorum { got: usize, required: usize },

    #[error("Agent not found: {0}")]
    AgentNotFound(String),

    #[error("Byzantine fault detected: {0}")]
    ByzantineFault(String),

    #[error("Consensus timeout")]
    ConsensusTimeout,

    #[error("Invalid proposal: {0}")]
    InvalidProposal(String),

    #[error("Merkle commitment mismatch")]
    MerkleCommitmentMismatch,

    #[error("Vote validation failed: {0}")]
    VoteValidationFailed(String),

    #[error("Max failures exceeded: {0}")]
    MaxFailuresExceeded(String),

    #[error("Engine state error: {0}")]
    EngineStateError(String),
}
