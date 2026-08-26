//! L3: Native function calling with permit gates
//! Ensures all tool invocations check policy before execution (BEFORE, not after)

pub mod permit;
pub mod enforcement;

pub use permit::{PermitGate, GateDecision};
pub use enforcement::GateEnforcer;
