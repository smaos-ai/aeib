// Phase 3 Stream 1: BaselineCapsule + HarnessCapsule v1
// Governance core wrapper + LangChain/Ollama/AutoGPT adapters
// Phase 26 Task 1: CAPSULE v2.2 Hardening (Ed25519 + Merkle-DAG)
// Phase 26 Task 2: Tiers 2-4 (Determinism + Protocol v2 + Swarm)

// pub mod adapters;
// pub mod baseline;
pub mod determinism;
pub mod errors;
pub mod fallback;
// pub mod harness;
pub mod protocol_bridge;
// Stub implementations to bypass external dependencies
pub mod signing;
pub mod state_log;
// pub mod swarm_link;
pub mod types;

// pub use adapters::{AutoGPTAdapter, LangChainAdapter, OllamaAdapter};
// pub use baseline::BaselineCapsule;
pub use determinism::{CacheStats, CachedPrompt, DeterministicExecutor};
pub use errors::CapsuleError;
pub use fallback::{FallbackAction, FallbackRule, RuleBasedFallback};
// pub use harness::HarnessCapsule;
pub use protocol_bridge::{ProtocolV2Bridge, ScopeError, ScopeRule};
// Temporarily commented to bypass compilation errors in dependencies
// pub use signing::{SignedMutation, SigningError, StateMutationSigner};
// pub use state_log::{SignedStateEntry, SignedStateLog, StateLogError};
// pub use swarm_link::{PeerCapsule, StateEntry, SwarmError, SwarmLink};
pub use types::{
    AuditTraceEntry, ContextIsolation, CovenantEnforcement, ExecutionContext, HarnessConfig,
    MerkleProofVerification, PolicyVerificationResult, ToolAuthProof, ToolAuthVerification,
};
