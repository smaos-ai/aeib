use thiserror::Error;

#[derive(Debug, Clone, Error)]
pub enum Stream6Error {
    #[error("KYC verification failed: {0}")]
    KYCVerificationFailed(String),

    #[error("KYC record not found for creator: {0}")]
    KYCNotFound(String),

    #[error("KYC status expired for creator: {0}")]
    KYCExpired(String),

    #[error("Creator identity mismatch: {0}")]
    IdentityMismatch(String),

    #[error("AML sanctions check failed: {0}")]
    AMLSanctionsViolation(String),

    #[error("Creator on sanctions list: {0}")]
    CreatorOnSanctionsList(String),

    #[error("Layer 0 integration error: {0}")]
    Layer0Error(String),

    #[error("Gate invocation denied: {0}")]
    GateInvocationDenied(String),

    #[error("Database error: {0}")]
    DatabaseError(String),

    #[error("Compliance check failed: {0}")]
    ComplianceCheckFailed(String),

    #[error("Invalid stream6 configuration: {0}")]
    ConfigurationError(String),
}

pub type Stream6Result<T> = Result<T, Stream6Error>;
