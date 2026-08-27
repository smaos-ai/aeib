//! L4: Deterministic orchestration with LangGraph checkpoints
//! 3 pilots: hotel (credit scoring), glass (safety), school (access control)

pub mod error;
pub mod orchestration;

pub use error::{L4AuditEntry, L4Error, RetryConfig};
pub use orchestration::{GlassPilot, HotelPilot, Pilot, SchoolPilot};
