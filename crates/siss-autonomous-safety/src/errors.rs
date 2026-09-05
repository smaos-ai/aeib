use thiserror::Error;

pub type SafetyResult<T> = Result<T, SafetyError>;

#[derive(Error, Debug, Clone)]
pub enum SafetyError {
    #[error("ASIL level violation: {0}")]
    AssilViolation(String),

    #[error("Hazard severity exceeds threshold: {0}")]
    HazardExceedsThreshold(String),

    #[error("SOTIF validation failed: {0}")]
    SotifValidationFailed(String),

    #[error("Consensus quorum not met: required {required}, got {got}")]
    InsufficientQuorum { required: usize, got: usize },

    #[error("Consensus proof invalid: {0}")]
    InvalidConsensusProof(String),

    #[error("Replay integrity violation: {0}")]
    ReplayIntegrityError(String),

    #[error("Sensor degradation detected: {0}")]
    SensorDegradation(String),

    #[error("Byzantine fault detected: {0}")]
    ByzantineFault(String),

    #[error("Invalid FMEA record: {0}")]
    InvalidFmeaRecord(String),

    #[error("Formal verification error: {0}")]
    FormalVerificationError(String),

    #[error("Internal error: {0}")]
    InternalError(String),
}
