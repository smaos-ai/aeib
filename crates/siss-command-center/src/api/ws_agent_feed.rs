use chrono::Utc;
use serde::{Deserialize, Serialize};
use siss_console::{AgentState, AgentStatus, WsMessage};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentFeedMessage {
    pub message_id: String,
    pub timestamp_ms: u64,
    pub payload: WsMessage,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FeedStats {
    pub total_agents: usize,
    pub running_agents: usize,
    pub idle_agents: usize,
    pub failed_agents: usize,
    pub total_memory_mb: u32,
    pub total_tasks_active: usize,
}

pub struct AgentFeed {
    agent_statuses: Arc<RwLock<HashMap<String, AgentStatus>>>,
    message_count: Arc<RwLock<u64>>,
}

impl AgentFeed {
    pub fn new() -> Self {
        Self {
            agent_statuses: Arc::new(RwLock::new(HashMap::new())),
            message_count: Arc::new(RwLock::new(0)),
        }
    }

    pub async fn publish_status(&self, status: AgentStatus) -> Result<AgentFeedMessage, String> {
        let mut statuses = self.agent_statuses.write().await;
        statuses.insert(status.agent_id.clone(), status.clone());

        let mut count = self.message_count.write().await;
        *count += 1;

        Ok(AgentFeedMessage {
            message_id: format!("msg_{}", count),
            timestamp_ms: Utc::now().timestamp_millis() as u64,
            payload: WsMessage::AgentStatus(status),
        })
    }

    pub async fn get_agent_status(&self, agent_id: &str) -> Result<Option<AgentStatus>, String> {
        let statuses = self.agent_statuses.read().await;
        Ok(statuses.get(agent_id).cloned())
    }

    pub async fn list_all_statuses(&self) -> Result<Vec<AgentStatus>, String> {
        let statuses = self.agent_statuses.read().await;
        Ok(statuses.values().cloned().collect())
    }

    pub async fn get_stats(&self) -> Result<FeedStats, String> {
        let statuses = self.agent_statuses.read().await;
        let total_agents = statuses.len();
        let mut running_agents = 0;
        let mut idle_agents = 0;
        let mut failed_agents = 0;
        let mut total_memory_mb = 0u32;
        let mut total_tasks_active = 0;

        for status in statuses.values() {
            total_memory_mb = total_memory_mb.saturating_add(status.memory_mb);
            total_tasks_active += status.tasks_active;

            match status.state {
                AgentState::Running => running_agents += 1,
                AgentState::Idle => idle_agents += 1,
                AgentState::Failed => failed_agents += 1,
                _ => {}
            }
        }

        Ok(FeedStats {
            total_agents,
            running_agents,
            idle_agents,
            failed_agents,
            total_memory_mb,
            total_tasks_active,
        })
    }

    pub async fn remove_agent(&self, agent_id: &str) -> Result<(), String> {
        let mut statuses = self.agent_statuses.write().await;
        statuses.remove(agent_id);
        Ok(())
    }

    pub async fn clear_all(&self) -> Result<(), String> {
        let mut statuses = self.agent_statuses.write().await;
        statuses.clear();
        Ok(())
    }

    pub async fn get_message_count(&self) -> Result<u64, String> {
        let count = self.message_count.read().await;
        Ok(*count)
    }
}

impl Default for AgentFeed {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_agent_feed_create() {
        let feed = AgentFeed::new();
        let stats = feed.get_stats().await.unwrap();
        assert_eq!(stats.total_agents, 0);
    }

    #[tokio::test]
    async fn test_agent_feed_publish_status() {
        let feed = AgentFeed::new();
        let status = AgentStatus {
            agent_id: "alpha_001".to_string(),
            state: AgentState::Running,
            memory_mb: 256,
            tasks_active: 3,
            timestamp_ms: 1719072747000,
            error: None,
            metadata: None,
        };

        let msg = feed.publish_status(status.clone()).await.unwrap();
        assert!(msg.message_id.contains("msg_"));
    }

    #[tokio::test]
    async fn test_agent_feed_get_status() {
        let feed = AgentFeed::new();
        let status = AgentStatus {
            agent_id: "beta_002".to_string(),
            state: AgentState::Idle,
            memory_mb: 128,
            tasks_active: 0,
            timestamp_ms: 1719072747000,
            error: None,
            metadata: None,
        };

        feed.publish_status(status.clone()).await.unwrap();
        let retrieved = feed.get_agent_status("beta_002").await.unwrap();
        assert!(retrieved.is_some());
        assert_eq!(retrieved.unwrap().agent_id, "beta_002");
    }

    #[tokio::test]
    async fn test_agent_feed_list_all() {
        let feed = AgentFeed::new();
        feed.publish_status(AgentStatus {
            agent_id: "agent_1".to_string(),
            state: AgentState::Running,
            memory_mb: 256,
            tasks_active: 1,
            timestamp_ms: 1719072747000,
            error: None,
            metadata: None,
        })
        .await
        .unwrap();

        feed.publish_status(AgentStatus {
            agent_id: "agent_2".to_string(),
            state: AgentState::Idle,
            memory_mb: 128,
            tasks_active: 0,
            timestamp_ms: 1719072747000,
            error: None,
            metadata: None,
        })
        .await
        .unwrap();

        let statuses = feed.list_all_statuses().await.unwrap();
        assert_eq!(statuses.len(), 2);
    }

    #[tokio::test]
    async fn test_agent_feed_stats() {
        let feed = AgentFeed::new();
        feed.publish_status(AgentStatus {
            agent_id: "agent_1".to_string(),
            state: AgentState::Running,
            memory_mb: 256,
            tasks_active: 3,
            timestamp_ms: 1719072747000,
            error: None,
            metadata: None,
        })
        .await
        .unwrap();

        feed.publish_status(AgentStatus {
            agent_id: "agent_2".to_string(),
            state: AgentState::Idle,
            memory_mb: 128,
            tasks_active: 0,
            timestamp_ms: 1719072747000,
            error: None,
            metadata: None,
        })
        .await
        .unwrap();

        let stats = feed.get_stats().await.unwrap();
        assert_eq!(stats.total_agents, 2);
        assert_eq!(stats.running_agents, 1);
        assert_eq!(stats.idle_agents, 1);
        assert_eq!(stats.total_memory_mb, 384);
        assert_eq!(stats.total_tasks_active, 3);
    }

    #[tokio::test]
    async fn test_agent_feed_remove_agent() {
        let feed = AgentFeed::new();
        feed.publish_status(AgentStatus {
            agent_id: "agent_1".to_string(),
            state: AgentState::Running,
            memory_mb: 256,
            tasks_active: 1,
            timestamp_ms: 1719072747000,
            error: None,
            metadata: None,
        })
        .await
        .unwrap();

        feed.remove_agent("agent_1").await.unwrap();
        let status = feed.get_agent_status("agent_1").await.unwrap();
        assert!(status.is_none());
    }

    #[tokio::test]
    async fn test_agent_feed_clear_all() {
        let feed = AgentFeed::new();
        feed.publish_status(AgentStatus {
            agent_id: "agent_1".to_string(),
            state: AgentState::Running,
            memory_mb: 256,
            tasks_active: 1,
            timestamp_ms: 1719072747000,
            error: None,
            metadata: None,
        })
        .await
        .unwrap();

        feed.clear_all().await.unwrap();
        let stats = feed.get_stats().await.unwrap();
        assert_eq!(stats.total_agents, 0);
    }

    #[tokio::test]
    async fn test_agent_feed_message_count() {
        let feed = AgentFeed::new();
        let status = AgentStatus {
            agent_id: "agent_1".to_string(),
            state: AgentState::Running,
            memory_mb: 256,
            tasks_active: 1,
            timestamp_ms: 1719072747000,
            error: None,
            metadata: None,
        };

        feed.publish_status(status.clone()).await.unwrap();
        feed.publish_status(status).await.unwrap();

        let count = feed.get_message_count().await.unwrap();
        assert_eq!(count, 2);
    }

    #[tokio::test]
    async fn test_agent_feed_default() {
        let feed = AgentFeed::default();
        let stats = feed.get_stats().await.unwrap();
        assert_eq!(stats.total_agents, 0);
    }
}
