use thiserror::Error;

#[derive(Error, Debug)]
pub enum AiFactoryError {
    #[error("Snapshot error: {0}")]
    SnapshotError(String),

    #[error("Replay error: {0}")]
    ReplayError(String),

    #[error("Chaos injection error: {0}")]
    ChaosInjectionError(String),

    #[error("Recovery validation error: {0}")]
    RecoveryValidationError(String),

    #[error("Machine registry error: {0}")]
    MachineRegistryError(String),

    #[error("State consistency error: {0}")]
    StateConsistencyError(String),

    #[error("RTO violation: expected <5s, got {0:?}")]
    RtoViolation(std::time::Duration),

    #[error("RPO violation: expected 0 loss, got {0} messages")]
    RpoViolation(usize),

    #[error("Determinism verification failed: {0}")]
    DeterminismViolation(String),

    #[error("No agents in snapshot")]
    NoAgentsInSnapshot,

    #[error("Agent not found: {0}")]
    AgentNotFound(uuid::Uuid),

    #[error("Machine not found: {0}")]
    MachineNotFound(uuid::Uuid),

    #[error("No primary region available")]
    NoPrimaryRegion,
}

pub type Result<T> = std::result::Result<T, AiFactoryError>;
