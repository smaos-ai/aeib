//! SISS Trust Mesh: DID-anchored cryptographic authority for Proof-of-Sapience
//! Layer 13 of SGP v1.0 — replaces heuristic contradiction resolution with trust scoring

pub mod did_registry;
pub mod proof_of_sapience;
pub mod trust_resolver;
pub mod attestation;

pub use did_registry::{DidRegistry, DidDocument};
pub use proof_of_sapience::ProofOfSapience;
pub use trust_resolver::{TrustResolver, ContradictionCandidate, Resolution};
pub use attestation::TrustAttestation;
