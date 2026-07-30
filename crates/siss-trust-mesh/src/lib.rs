//! SISS Trust Mesh: DID-anchored cryptographic authority for Proof-of-Sapience
//! Layer 13 of SGP v1.0 — replaces heuristic contradiction resolution with trust scoring

pub mod attestation;
pub mod did_registry;
pub mod proof_of_sapience;
pub mod trust_resolver;

pub use attestation::TrustAttestation;
pub use did_registry::{DidDocument, DidRegistry};
pub use proof_of_sapience::ProofOfSapience;
pub use trust_resolver::{ContradictionCandidate, Resolution, TrustResolver};
