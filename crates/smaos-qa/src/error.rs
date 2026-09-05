use thiserror::Error;

pub type Result<T> = std::result::Result<T, QaError>;

#[derive(Error, Debug)]
pub enum QaError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),

    #[error("Chrono error: {0}")]
    Chrono(#[from] chrono::ParseError),

    #[error("Pre-flight validation failed: {0}")]
    PreFlightFailed(String),

    #[error("Git validation failed: {0}")]
    GitValidationFailed(String),

    #[error("Nonce generation failed: {0}")]
    NonceGenerationFailed(String),

    #[error("Unit test execution failed: {0}")]
    TestExecutionFailed(String),

    #[error("Behavioral metrics out of bounds: {0}")]
    MetricsValidationFailed(String),

    #[error("Proof signing failed: {0}")]
    ProofSigningFailed(String),

    #[error("Proof verification failed: {0}")]
    ProofVerificationFailed(String),

    #[error("Agent execution failed: agent_id={agent_id}, reason={reason}")]
    AgentExecutionFailed { agent_id: u32, reason: String },

    #[error("Triangulation failed: {0}")]
    TriangulationFailed(String),

    #[error("Merkle root mismatch: {0}")]
    MerkleRootMismatch(String),

    #[error("Determinism check failed: {0}")]
    DeterminismCheckFailed(String),

    #[error("Adversarial test failed: {0}")]
    AdversarialTestFailed(String),

    #[error("Attestation failed: {0}")]
    AttestationFailed(String),

    #[error("AP2 ledger operation failed: {0}")]
    Ap2OperationFailed(String),

    #[error("Timeout: {0}")]
    Timeout(String),

    #[error("Agent proof invalid: agent_id={agent_id}, {reason}")]
    InvalidAgentProof { agent_id: u32, reason: String },

    #[error("Configuration error: {0}")]
    ConfigurationError(String),

    #[error("Unknown error: {0}")]
    Unknown(String),
}
