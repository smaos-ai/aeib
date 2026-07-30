use thiserror::Error;

#[derive(Error, Debug)]
pub enum ContractError {
    #[error("Invalid state transition: {from} -> {to}")]
    InvalidStateTransition { from: String, to: String },

    #[error("Contract not found: {0}")]
    NotFound(uuid::Uuid),

    #[error("Contract already activated")]
    AlreadyActivated,

    #[error("Commitment is immutable after activation")]
    CommitmentImmutable,

    #[error("Invalid region for vertical: {vertical} requires {required}")]
    InvalidRegion { vertical: String, required: String },

    #[error("Policy error: {0}")]
    PolicyError(String),

    #[error("Internal error: {0}")]
    Internal(String),
}

#[derive(Error, Debug)]
pub enum PolicyError {
    #[error("Request validation failed: {0}")]
    ValidationFailed(String),

    #[error("Regional isolation violation")]
    RegionalIsolationViolated,

    #[error("HIPAA compliance violation")]
    HipaaViolation,

    #[error("Air-gap validation failed")]
    AirGapViolationFailed,

    #[error("MiFID II compliance violation")]
    MiFidViolation,

    #[error("Settlement atomicity violation")]
    SettlementAtomicity,

    #[error("2FA required for this transaction")]
    TwoFaRequired,
}

#[derive(Error, Debug)]
pub enum RevenueError {
    #[error("Contract already registered")]
    DuplicateContract,

    #[error("Settlement failed: {0}")]
    SettlementFailed(String),

    #[error("Invalid billing period")]
    InvalidBillingPeriod,
}

#[derive(Error, Debug)]
pub enum SlaError {
    #[error("SLA metric recording failed")]
    MetricRecordingFailed,

    #[error("Compliance check failed")]
    ComplianceCheckFailed,

    #[error("Breach remediation failed: {0}")]
    RemediationFailed(String),
}
