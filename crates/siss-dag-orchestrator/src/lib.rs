//! siss-dag-orchestrator: Heterogeneous DAG orchestration and execution
//!
//! Provides:
//! - DAG compilation from intent
//! - Topological ordering with safety constraints
//! - Parallel execution scheduling
//! - Failure recovery + checkpointing

pub mod error;
pub mod types;
pub mod compiler;
pub mod executor;
pub mod checkpoint;

pub use error::{Error, Result};
pub use types::*;
pub use compiler::{DagCompiler, CompilerConfig};
pub use executor::{DagExecutor, ExecutorConfig};
pub use checkpoint::{CheckpointManager, CheckpointConfig};

pub const VERSION: &str = env!("CARGO_PKG_VERSION");
