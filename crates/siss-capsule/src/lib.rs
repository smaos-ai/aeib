// Phase 3 Stream 1: BaselineCapsule + HarnessCapsule v1
// Governance core wrapper + LangChain/Ollama/AutoGPT adapters
// Phase 26 Task 1: CAPSULE v2.2 Hardening (Ed25519 + Merkle-DAG)

pub mod baseline;
pub mod harness;
pub mod adapters;
pub mod types;
pub mod errors;
pub mod signing;
pub mod state_log;

pub use baseline::BaselineCapsule;
pub use harness::HarnessCapsule;
pub use adapters::{LangChainAdapter, OllamaAdapter, AutoGPTAdapter};
pub use types::{
    PolicyVerificationResult, ToolAuthProof, ExecutionContext, ContextIsolation,
    AuditTraceEntry, MerkleProofVerification, CovenantEnforcement, HarnessConfig,
    ToolAuthVerification,
};
pub use errors::CapsuleError;
pub use signing::{StateMutationSigner, SignedMutation, SigningError};
pub use state_log::{SignedStateLog, SignedStateEntry, StateLogError};
