//! L6: FreeToken edge inference + hardware detection
//! Validates 39.3 tok/s on 8GB, integrates CanIRun.ai

pub mod hardware;

pub use hardware::{HardwareDetector, HardwareTier};
