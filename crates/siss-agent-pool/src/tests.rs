#[cfg(test)]
mod integration_tests {
    use crate::{AgentPool, PoolConfig, AgentStatus};

    #[tokio::test]
    async fn test_pool_concurrent_spawn() {
        let config = PoolConfig::new(50, 10).unwrap();
        let pool = std::sync::Arc::new(AgentPool::new(config));

        let mut handles = vec![];
        for _ in 0..10 {
            let pool = pool.clone();
            let handle = tokio::spawn(async move {
                pool.spawn_agent().await.unwrap()
            });
            handles.push(handle);
        }

        for handle in handles {
            handle.await.unwrap();
        }

        assert_eq!(pool.agent_count(), 10);
    }

    #[tokio::test]
    async fn test_pool_state_migration() {
        let config = PoolConfig::new(10, 5).unwrap();
        let pool = AgentPool::new(config);

        let agent1 = pool.spawn_agent().await.unwrap();
        let agent2 = pool.spawn_agent().await.unwrap();

        let result = pool.migrate_state(agent1, agent2).await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_pool_graceful_shutdown() {
        let config = PoolConfig::new(10, 5).unwrap();
        let pool = AgentPool::new(config);

        pool.spawn_agent().await.unwrap();
        pool.spawn_agent().await.unwrap();
        pool.spawn_agent().await.unwrap();

        let result = pool.shutdown().await;
        assert!(result.is_ok());
        assert_eq!(pool.agent_count(), 0);
    }

    #[tokio::test]
    async fn test_pool_drain_agent() {
        let config = PoolConfig::new(10, 5).unwrap();
        let pool = AgentPool::new(config);

        let agent_id = pool.spawn_agent().await.unwrap();
        assert_eq!(pool.get_agent_status(agent_id), Some(AgentStatus::Idle));

        // Mark as draining (real drain would complete async)
        if let Some(mut agent) = pool.agents.get_mut(&agent_id) {
            agent.start_drain();
            agent.shutdown();
        }

        assert_eq!(pool.get_agent_status(agent_id), Some(AgentStatus::Shutdown));
    }
}
