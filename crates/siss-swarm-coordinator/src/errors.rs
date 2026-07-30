use thiserror::Error;

#[derive(Error, Debug)]
pub enum SwarmCoordinatorError {
    #[error("Agent not found: {0}")]
    AgentNotFound(String),

    #[error("MongeGap bounds exceeded: {0}")]
    BoundsExceeded(String),

    #[error("Cycle detected in delegation: {0}")]
    CycleDetected(String),

    #[error("Invalid agent ID")]
    InvalidAgentId,

    #[error("Delegation limit reached (5 agents max)")]
    DelegationLimitReached,

    #[error("Depth limit exceeded (max 3)")]
    DepthLimitExceeded,

    #[error("Internal error: {0}")]
    InternalError(String),
}
