//! Phase 42: Autonomous Systems — ISO 26262 ASIL-D Safety Framework
//!
//! Provides safety-critical governance for autonomous vehicles with:
//! - ISO 26262 ASIL-D functional safety requirements
//! - Byzantine consensus for safety decisions (fault tolerance f < n/3)
//! - Formal verification integration (Lean 4)
//! - Deterministic replay for accident reconstruction

pub mod asil;
pub mod errors;
pub mod fmea;
pub mod hazard;
pub mod replay;
pub mod safety_consensus;
pub mod sotif;

pub use asil::{AssilLevel, AssilValidator};
pub use errors::{SafetyError, SafetyResult};
pub use fmea::FmeaRecord;
pub use hazard::HazardLevel;
pub use replay::{ReplayEvent, ReplayEventType, ReplayRecorder, ReplaySession};
pub use safety_consensus::{
    SafetyConsensusValidator, SafetyDecision, SafetyDecisionType,
};
pub use sotif::SotifValidator;
