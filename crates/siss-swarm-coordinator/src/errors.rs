use thiserror::Error;

#[derive(Debug, Error)]
pub enum SwarmCoordinatorError {
    #[error("Agent not found: {0}")]
    AgentNotFound(String),

    #[error("Cycle detected: {0}")]
    CycleDetected(String),

    #[error("Depth limit exceeded")]
    DepthLimitExceeded,

    #[error("Delegation limit exceeded")]
    DelegationLimitExceeded,

    #[error("Invalid signature")]
    InvalidSignature,
}
