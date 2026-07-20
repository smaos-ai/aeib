// Phase 3 Stream 1: BaselineCapsule + HarnessCapsule v1
// Governance core wrapper + LangChain/Ollama/AutoGPT adapters

pub mod baseline;
pub mod harness;
pub mod adapters;
pub mod types;
pub mod errors;

pub use baseline::BaselineCapsule;
pub use harness::HarnessCapsule;
pub use adapters::{LangChainAdapter, OllamaAdapter, AutoGPTAdapter};
pub use types::{
    PolicyVerificationResult, ToolAuthProof, ExecutionContext, ContextIsolation,
    AuditTraceEntry, MerkleProofVerification, CovenantEnforcement, HarnessConfig,
    ToolAuthVerification,
};
pub use errors::CapsuleError;
