use crate::types::{AgentStatus, AgentState, ConsoleError};
use std::sync::Arc;
use tokio::sync::RwLock;
use std::collections::HashMap;
use uuid::Uuid;

pub type AgentStreamId = Uuid;

#[derive(Debug, Clone)]
pub struct AgentStream {
    pub stream_id: AgentStreamId,
    pub agent_id: String,
    pub last_status: Option<AgentStatus>,
}

pub struct WsBridge {
    agent_streams: Arc<RwLock<HashMap<AgentStreamId, AgentStream>>>,
    agent_id_map: Arc<RwLock<HashMap<String, AgentStreamId>>>,
    heartbeat_interval_ms: u64,
}

impl WsBridge {
    pub fn new(heartbeat_interval_ms: u64) -> Self {
        Self {
            agent_streams: Arc::new(RwLock::new(HashMap::new())),
            agent_id_map: Arc::new(RwLock::new(HashMap::new())),
            heartbeat_interval_ms,
        }
    }

    pub async fn connect_agent(&self, agent_id: &str) -> Result<AgentStream, ConsoleError> {
        let stream_id = Uuid::new_v4();
        let stream = AgentStream {
            stream_id,
            agent_id: agent_id.to_string(),
            last_status: None,
        };

        let mut streams = self.agent_streams.write().await;
        let mut id_map = self.agent_id_map.write().await;

        streams.insert(stream_id, stream.clone());
        id_map.insert(agent_id.to_string(), stream_id);

        Ok(stream)
    }

    pub async fn broadcast_status(&self, status: AgentStatus) -> Result<(), ConsoleError> {
        let mut streams = self.agent_streams.write().await;

        if let Some(stream) = streams.get_mut(&self.lookup_agent(&status.agent_id).await?) {
            let mut updated = stream.clone();
            updated.last_status = Some(status);
            *stream = updated;
            Ok(())
        } else {
            Err(ConsoleError::WsError(format!(
                "Agent {} not connected",
                status.agent_id
            )))
        }
    }

    pub async fn disconnect_agent(&self, agent_id: &str) -> Result<(), ConsoleError> {
        let mut id_map = self.agent_id_map.write().await;
        if let Some(stream_id) = id_map.remove(agent_id) {
            let mut streams = self.agent_streams.write().await;
            streams.remove(&stream_id);
            Ok(())
        } else {
            Err(ConsoleError::WsError(format!("Agent {} not found", agent_id)))
        }
    }

    pub async fn get_agent_status(&self, agent_id: &str) -> Result<Option<AgentStatus>, ConsoleError> {
        match self.lookup_agent(agent_id).await {
            Ok(stream_id) => {
                let streams = self.agent_streams.read().await;
                Ok(streams
                    .get(&stream_id)
                    .and_then(|s| s.last_status.clone()))
            }
            Err(_) => Ok(None), // Agent not found returns None, not an error
        }
    }

    pub async fn list_connected_agents(&self) -> Result<Vec<String>, ConsoleError> {
        let id_map = self.agent_id_map.read().await;
        Ok(id_map.keys().cloned().collect())
    }

    pub fn heartbeat_interval_ms(&self) -> u64 {
        self.heartbeat_interval_ms
    }

    async fn lookup_agent(&self, agent_id: &str) -> Result<AgentStreamId, ConsoleError> {
        let id_map = self.agent_id_map.read().await;
        id_map
            .get(agent_id)
            .copied()
            .ok_or_else(|| ConsoleError::WsError(format!("Agent {} not connected", agent_id)))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_ws_bridge_create() {
        let bridge = WsBridge::new(5000);
        assert_eq!(bridge.heartbeat_interval_ms(), 5000);
    }

    #[tokio::test]
    async fn test_ws_bridge_connect_agent() {
        let bridge = WsBridge::new(5000);
        let stream = bridge.connect_agent("alpha_001").await.unwrap();
        assert_eq!(stream.agent_id, "alpha_001");
    }

    #[tokio::test]
    async fn test_ws_bridge_broadcast_status() {
        let bridge = WsBridge::new(5000);
        bridge.connect_agent("alpha_001").await.unwrap();

        let status = AgentStatus {
            agent_id: "alpha_001".to_string(),
            state: AgentState::Running,
            memory_mb: 256,
            tasks_active: 3,
            timestamp_ms: 1719072747000,
            error: None,
            metadata: None,
        };

        bridge.broadcast_status(status.clone()).await.unwrap();

        let retrieved = bridge.get_agent_status("alpha_001").await.unwrap();
        assert!(retrieved.is_some());
        assert_eq!(retrieved.unwrap().agent_id, "alpha_001");
    }

    #[tokio::test]
    async fn test_ws_bridge_disconnect() {
        let bridge = WsBridge::new(5000);
        bridge.connect_agent("beta_002").await.unwrap();
        bridge.disconnect_agent("beta_002").await.unwrap();

        let result = bridge.get_agent_status("beta_002").await.unwrap();
        assert!(result.is_none());
    }

    #[tokio::test]
    async fn test_ws_bridge_list_connected() {
        let bridge = WsBridge::new(5000);
        bridge.connect_agent("alpha_001").await.unwrap();
        bridge.connect_agent("beta_002").await.unwrap();

        let agents = bridge.list_connected_agents().await.unwrap();
        assert_eq!(agents.len(), 2);
        assert!(agents.contains(&"alpha_001".to_string()));
        assert!(agents.contains(&"beta_002".to_string()));
    }

    #[tokio::test]
    async fn test_ws_bridge_get_nonexistent_agent() {
        let bridge = WsBridge::new(5000);
        let result = bridge.get_agent_status("nonexistent").await;
        assert!(result.is_ok());
        assert!(result.unwrap().is_none());
    }

    #[tokio::test]
    async fn test_ws_bridge_broadcast_to_disconnected() {
        let bridge = WsBridge::new(5000);
        let status = AgentStatus {
            agent_id: "alpha_001".to_string(),
            state: AgentState::Running,
            memory_mb: 256,
            tasks_active: 3,
            timestamp_ms: 1719072747000,
            error: None,
            metadata: None,
        };

        let result = bridge.broadcast_status(status).await;
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_ws_bridge_multiple_agents() {
        let bridge = WsBridge::new(5000);
        bridge.connect_agent("agent_1").await.unwrap();
        bridge.connect_agent("agent_2").await.unwrap();
        bridge.connect_agent("agent_3").await.unwrap();

        let agents = bridge.list_connected_agents().await.unwrap();
        assert_eq!(agents.len(), 3);
    }

    #[tokio::test]
    async fn test_ws_bridge_status_updates() {
        let bridge = WsBridge::new(5000);
        bridge.connect_agent("gamma_003").await.unwrap();

        let status1 = AgentStatus {
            agent_id: "gamma_003".to_string(),
            state: AgentState::Idle,
            memory_mb: 128,
            tasks_active: 0,
            timestamp_ms: 1719072747000,
            error: None,
            metadata: None,
        };
        bridge.broadcast_status(status1).await.unwrap();

        let status2 = AgentStatus {
            agent_id: "gamma_003".to_string(),
            state: AgentState::Running,
            memory_mb: 512,
            tasks_active: 5,
            timestamp_ms: 1719072748000,
            error: None,
            metadata: None,
        };
        bridge.broadcast_status(status2).await.unwrap();

        let current = bridge.get_agent_status("gamma_003").await.unwrap().unwrap();
        assert_eq!(current.state, AgentState::Running);
        assert_eq!(current.memory_mb, 512);
    }
}
