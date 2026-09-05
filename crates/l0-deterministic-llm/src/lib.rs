//! L0: Deterministic LLM Abstraction Layer
//! - Temperature=0.0 deterministic inference
//! - Prompt caching with SHA256 fingerprinting (80%+ hit target)
//! - 70% token cost reduction
//! - Offline fallback (rule-based templates)
//! - L8 proof layer integration (Merkle chain)
//! - Ed25519 signatures on all inferences

pub mod cache;
pub mod engine;
pub mod error;
pub mod ledger;
pub mod offline;
pub mod types;

pub use engine::DeterministicLLMEngine;
pub use error::{L0AuditEntry, L0Error};
pub use types::{
    CachedInferenceResponse, DeterministicInferenceRequest, MerkleChainEntry,
    OfflineFallbackTemplate, TokenCostMetrics,
};
