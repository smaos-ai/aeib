//! L3: Native function calling with permit gates
//! Ensures all tool invocations check policy before execution (BEFORE, not after)

pub mod enforcement;
pub mod error;
pub mod permit;

pub use enforcement::GateEnforcer;
pub use error::{L3AuditEntry, L3Error};
pub use permit::{GateDecision, PermitGate};
