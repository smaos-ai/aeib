use crate::error::{PoolError, Result};
use crate::{Agent, AgentStatus, PoolConfig, StateSnapshot};
use dashmap::DashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use uuid::Uuid;

/// Agent pool manager
pub struct AgentPool {
    config: Arc<PoolConfig>,
    pub agents: Arc<DashMap<Uuid, Agent>>,
    state_snapshots: Arc<DashMap<Uuid, StateSnapshot>>,
    shutdown_signal: Arc<RwLock<bool>>,
}

impl AgentPool {
    /// Create new agent pool
    pub fn new(config: PoolConfig) -> Self {
        Self {
            config: Arc::new(config),
            agents: Arc::new(DashMap::new()),
            state_snapshots: Arc::new(DashMap::new()),
            shutdown_signal: Arc::new(RwLock::new(false)),
        }
    }

    /// Spawn new agent
    pub async fn spawn_agent(&self) -> Result<Uuid> {
        if *self.shutdown_signal.read().await {
            return Err(PoolError::ShutdownFailed("Pool is shutting down".into()));
        }

        if self.agents.len() >= self.config.max_agents as usize {
            return Err(PoolError::PoolFull);
        }

        let agent = Agent::new();
        let agent_id = agent.id;
        self.agents.insert(agent_id, agent);

        Ok(agent_id)
    }

    /// Drain agent gracefully
    pub async fn drain_agent(&self, agent_id: Uuid) -> Result<()> {
        let mut agent = self
            .agents
            .get_mut(&agent_id)
            .ok_or(PoolError::AgentNotFound)?;

        agent.start_drain();

        // Simulate graceful shutdown with timeout
        let deadline = tokio::time::Instant::now()
            + tokio::time::Duration::from_millis(self.config.drain_timeout_ms);

        while agent.status == AgentStatus::Draining {
            if tokio::time::Instant::now() > deadline {
                return Err(PoolError::DrainTimeout);
            }
            tokio::time::sleep(tokio::time::Duration::from_millis(10)).await;
        }

        Ok(())
    }

    /// Migrate agent state
    pub async fn migrate_state(&self, from_id: Uuid, to_id: Uuid) -> Result<()> {
        let from_agent = self
            .agents
            .get(&from_id)
            .ok_or(PoolError::AgentNotFound)?;
        let snapshot = StateSnapshot::new(from_id, from_agent.state.clone());

        // Verify snapshot
        if !snapshot.verify() {
            return Err(PoolError::MigrationFailed("Snapshot verification failed".into()));
        }

        // Store snapshot
        self.state_snapshots.insert(to_id, snapshot);

        // Start drain on source
        self.drain_agent(from_id).await?;

        Ok(())
    }

    /// Get agent count
    pub fn agent_count(&self) -> u32 {
        self.agents.len() as u32
    }

    /// Get idle agent count
    pub fn idle_count(&self) -> u32 {
        self.agents
            .iter()
            .filter(|entry| entry.value().status == AgentStatus::Idle)
            .count() as u32
    }

    /// Shutdown pool
    pub async fn shutdown(&self) -> Result<()> {
        *self.shutdown_signal.write().await = true;

        // Start draining all agents
        for mut agent_ref in self.agents.iter_mut() {
            agent_ref.value_mut().start_drain();
        }

        // Wait for all to shutdown
        let deadline = tokio::time::Instant::now()
            + tokio::time::Duration::from_millis(self.config.drain_timeout_ms);

        while self.agents.iter().any(|a| a.status != AgentStatus::Shutdown) {
            if tokio::time::Instant::now() > deadline {
                // Force shutdown remaining agents
                for mut agent_ref in self.agents.iter_mut() {
                    agent_ref.value_mut().shutdown();
                }
                break;
            }
            tokio::time::sleep(tokio::time::Duration::from_millis(10)).await;
        }

        self.agents.clear();
        Ok(())
    }

    /// Get agent status
    pub fn get_agent_status(&self, agent_id: Uuid) -> Option<AgentStatus> {
        self.agents.get(&agent_id).map(|a| a.status.clone())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_pool_creation() {
        let config = PoolConfig::new(10, 5).unwrap();
        let pool = AgentPool::new(config);
        assert_eq!(pool.agent_count(), 0);
    }

    #[tokio::test]
    async fn test_pool_spawn() {
        let config = PoolConfig::new(10, 5).unwrap();
        let pool = AgentPool::new(config);

        let agent_id = pool.spawn_agent().await.unwrap();
        assert_eq!(pool.agent_count(), 1);
        assert_eq!(
            pool.get_agent_status(agent_id),
            Some(AgentStatus::Idle)
        );
    }

    #[tokio::test]
    async fn test_pool_full() {
        let config = PoolConfig::new(2, 2).unwrap();
        let pool = AgentPool::new(config);

        pool.spawn_agent().await.unwrap();
        pool.spawn_agent().await.unwrap();

        let result = pool.spawn_agent().await;
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_pool_idle_count() {
        let config = PoolConfig::new(10, 5).unwrap();
        let pool = AgentPool::new(config);

        pool.spawn_agent().await.unwrap();
        pool.spawn_agent().await.unwrap();

        assert_eq!(pool.idle_count(), 2);
    }
}
