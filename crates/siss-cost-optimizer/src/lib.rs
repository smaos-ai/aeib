//! siss-cost-optimizer: Real-time cost tracking and financial optimization
//!
//! Provides:
//! - Real-time cost tracking per agent/transaction
//! - Dynamic resource allocation
//! - Cost prediction + budgeting
//! - Financial optimization

pub mod error;
pub mod types;
pub mod cost_tracker;
pub mod resource_allocator;
pub mod budgeter;

pub use error::{Error, Result};
pub use types::*;
pub use cost_tracker::{CostTracker, CostTrackerConfig};
pub use resource_allocator::{ResourceAllocator, AllocationConfig};
pub use budgeter::{Budgeter, BudgetConfig};

pub const VERSION: &str = env!("CARGO_PKG_VERSION");
