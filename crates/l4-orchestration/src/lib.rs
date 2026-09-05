//! L4: Deterministic orchestration with LangGraph checkpoints
//! 3 pilots: hotel (credit scoring), glass (safety), school (access control)

pub mod error;
pub mod orchestration;
pub mod l4_hook;
pub mod egress_controls;

pub use error::{L4AuditEntry, L4Error, RetryConfig};
pub use orchestration::{GlassPilot, HotelPilot, Pilot, SchoolPilot};
pub use l4_hook::{L4ExecutionResult, L4Hook, L8MetadataEntry};
pub use egress_controls::{EgressControlsEngine, EgressPolicy, EgressRequest, EgressCheckResult, EgressDecision};
