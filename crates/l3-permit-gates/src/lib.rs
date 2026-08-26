//! L3: Native function calling with permit gates
//! Ensures all tool invocations check policy before execution (BEFORE, not after)

pub mod enforcement;
pub mod permit;

pub use enforcement::GateEnforcer;
pub use permit::{GateDecision, PermitGate};
