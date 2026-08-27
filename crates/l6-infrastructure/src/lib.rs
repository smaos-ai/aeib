//! L6: FreeToken edge inference + hardware detection
//! Validates 39.3 tok/s on 8GB, integrates CanIRun.ai

pub mod error;
pub mod hardware;

pub use error::{L6AuditEntry, L6Error};
pub use hardware::{HardwareDetector, HardwareTier};
