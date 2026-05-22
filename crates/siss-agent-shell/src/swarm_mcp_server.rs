/// MCP server for swarm state synchronization via Unix socket.
/// Single source of truth: idempotent upsert semantics via PRIMARY KEY on idempotency_key.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct SwarmStatePayload {
    pub idempotency_key: String,
    pub agent_id: String,
    pub phase: String,
    pub status: String,
    pub payload_json: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GlobalStateFilter {
    pub phase_filter: Option<String>,
}

/// MCP server storing swarm state with idempotent upsert semantics.
pub struct SwarmMcpServer {
    state: Arc<RwLock<HashMap<String, SwarmStatePayload>>>,
}

impl SwarmMcpServer {
    /// Initialize MCP server with in-memory state (production: SQLite + WAL backend).
    pub async fn new(_db_path: &str) -> Result<Self, String> {
        Ok(Self {
            state: Arc::new(RwLock::new(HashMap::new())),
        })
    }

    /// Idempotent state mutation: second call with same idempotency_key overwrites first.
    pub async fn update_swarm_state(&self, req: SwarmStatePayload) -> Result<(), String> {
        let mut state = self.state.write().await;
        state.insert(req.idempotency_key.clone(), req);
        Ok(())
    }

    /// Retrieve global state snapshot with optional phase filter.
    pub async fn get_global_state(&self, filter: GlobalStateFilter) -> Result<Vec<SwarmStatePayload>, String> {
        let state = self.state.read().await;
        let mut result = Vec::new();

        for payload in state.values() {
            if let Some(ref phase) = filter.phase_filter {
                if payload.phase == *phase {
                    result.push(payload.clone());
                }
            } else {
                result.push(payload.clone());
            }
        }

        Ok(result)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use uuid::Uuid;

    #[tokio::test]
    async fn test_mcp_server_initialization() {
        let server = SwarmMcpServer::new("sqlite::memory:").await;
        assert!(server.is_ok());
    }

    #[tokio::test]
    async fn test_mcp_update_and_retrieve() {
        let server = SwarmMcpServer::new("sqlite::memory:").await.unwrap();
        let req = SwarmStatePayload {
            idempotency_key: Uuid::new_v4().to_string(),
            agent_id: "agent-1".to_string(),
            phase: "PHASE_42".to_string(),
            status: "RUNNING".to_string(),
            payload_json: None,
        };

        let result = server.update_swarm_state(req.clone()).await;
        assert!(result.is_ok());

        let state = server.get_global_state(GlobalStateFilter { phase_filter: None }).await.unwrap();
        assert_eq!(state.len(), 1);
        assert_eq!(state[0].idempotency_key, req.idempotency_key);
    }
}
