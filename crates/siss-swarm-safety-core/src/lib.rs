//! siss-swarm-safety-core: Multi-agent swarm safety gates
//!
//! Provides:
//! - RCE (Remote Code Execution) prevention gates
//! - MongeGap security boundary enforcement
//! - DAG scheduling with safety constraints
//! - <20 microsecond inter-agent communication latency

pub mod error;
pub mod types;
pub mod rce_gate;
pub mod monge_gap;
pub mod dag_scheduler;

pub use error::{Error, Result};
pub use types::*;
pub use rce_gate::{RceGate, RceGateConfig};
pub use monge_gap::{MongeGap, SecurityBoundary};
pub use dag_scheduler::{DagScheduler, ScheduleConfig};

/// Library version
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
