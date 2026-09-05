//! # SISS Agent Pool
//! Dynamic spawn/drain with state migration and graceful shutdown.
//!
//! Integration point for Phase 2 agent swarm - marked for Jun 2027.

pub mod pool;
pub mod agent;
pub mod state;
pub mod error;

pub use pool::AgentPool;
pub use agent::{Agent, AgentState, AgentStatus};
pub use state::StateSnapshot;
pub use error::{PoolError, Result};

#[cfg(test)]
mod tests;

/// Pool configuration
#[derive(Clone, Debug)]
pub struct PoolConfig {
    /// Maximum agents in pool
    pub max_agents: u32,
    /// Target number of agents
    pub target_agents: u32,
    /// Spawn timeout (ms)
    pub spawn_timeout_ms: u64,
    /// Drain timeout (ms)
    pub drain_timeout_ms: u64,
}

impl PoolConfig {
    /// Create new pool config
    pub fn new(max_agents: u32, target_agents: u32) -> Result<Self> {
        if target_agents > max_agents {
            return Err(PoolError::InvalidConfig("target > max".into()));
        }
        if max_agents == 0 {
            return Err(PoolError::InvalidConfig("max_agents must be > 0".into()));
        }
        Ok(Self {
            max_agents,
            target_agents,
            spawn_timeout_ms: 5000,
            drain_timeout_ms: 10000,
        })
    }
}

#[cfg(test)]
mod config_tests {
    use super::*;

    #[test]
    fn test_pool_config_validation() {
        assert!(PoolConfig::new(0, 5).is_err());
        assert!(PoolConfig::new(5, 10).is_err());
        assert!(PoolConfig::new(10, 5).is_ok());
    }
}
