use thiserror::Error;

#[derive(Error, Debug)]
pub enum SettlementError {
    #[error("Settlement not found: {0}")]
    NotFound(String),

    #[error("Invalid settlement status: {0}")]
    InvalidStatus(String),

    #[error("Signature verification failed: {0}")]
    SignatureVerificationFailed(String),

    #[error("Insufficient funds: {0}")]
    InsufficientFunds(String),

    #[error("Settlement already committed")]
    AlreadyCommitted,

    #[error("Settlement aborted")]
    Aborted,

    #[error("Ledger error: {0}")]
    LedgerError(String),

    #[error("Cryptographic error: {0}")]
    CryptoError(String),

    #[error("Invalid commitment: {0}")]
    InvalidCommitment(String),

    #[error("Serialization error: {0}")]
    SerializationError(#[from] serde_json::Error),
}
