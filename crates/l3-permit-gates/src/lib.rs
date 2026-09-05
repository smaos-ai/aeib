//! L3: Native function calling with permit gates
//! Ensures all tool invocations check policy before execution (BEFORE, not after)
//! Phase 2A: Intent verification protocol (L3B gate with cryptographic commitment validation)

pub mod enforcement;
pub mod error;
pub mod intent_verification;
pub mod l3_gate_integration;
pub mod l3b_middleware;
pub mod permit;

pub use enforcement::GateEnforcer;
pub use error::{L3AuditEntry, L3Error};
pub use intent_verification::{CryptoIntentCommitment, DelegationLink, IntentVerificationGate, VerificationResult};
pub use l3_gate_integration::{L3BGateHandler, L3BGateResult};
pub use l3b_middleware::{L3BGate, L4ExecutionPermit};
pub use permit::{GateDecision, PermitGate};
