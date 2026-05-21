//! Multi-worktree execution framework for parallel agent dispatch.
//!
//! This crate provides:
//! - Task queue management with dependency tracking
//! - Agent lifecycle management (spawn, execute, cleanup)
//! - Git worktree orchestration
//! - Merge coordination with conflict detection
//! - File-based locking for queue coordination

pub mod agent;
pub mod config;
pub mod errors;
pub mod executor;
pub mod git;
pub mod lock;
pub mod queue;
pub mod swarm;
pub mod tmux;
pub mod types;

pub use errors::{DispatchError, Result};
pub use executor::Executor;
pub use queue::TaskQueue;
pub use swarm::SwarmDispatcher;
pub use tmux::TmuxSession;
pub use types::{Agent, AgentStatus, Task, TaskDependency, TaskStatus};
