/// MCP client: agent-side wrapper with degraded mode local buffering.
/// Blocks flat-file writes (STATE.md, MEMORY.md) for hot coordination.

use crate::swarm_mcp_server::{SwarmStatePayload, GlobalStateFilter};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tokio::time::{sleep, Duration};

pub struct SwarmMcpClient {
    pub socket_path: String,
    /// Degraded mode local buffer when MCP socket is unavailable.
    pub degraded_buffer: Arc<RwLock<HashMap<String, SwarmStatePayload>>>,
}

impl SwarmMcpClient {
    pub fn new(socket_path: &str) -> Self {
        Self {
            socket_path: socket_path.to_string(),
            degraded_buffer: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Block direct writes to STATE.md or MEMORY.md for hot coordination.
    /// Fail-closed: all hot state must go through MCP.
    pub fn block_flat_file_writes(&self, file_path: &str) -> Result<(), String> {
        if file_path.ends_with("STATE.md") || file_path.ends_with("MEMORY.md") {
            return Err("Flat-file sync prohibited for hot runtime coordination.".into());
        }
        Ok(())
    }

    /// Update swarm state with exponential backoff retry + degraded mode fallback.
    pub async fn update_swarm_state(&self, req: SwarmStatePayload) -> Result<(), String> {
        let mut backoff = Duration::from_millis(5);
        let max_retries = 4;

        for attempt in 0..max_retries {
            match self.send_via_unix_socket(&req).await {
                Ok(_) => return Ok(()),
                Err(_) if attempt < max_retries - 1 => {
                    sleep(backoff).await;
                    backoff = Duration::from_millis((backoff.as_millis() * 2).min(1000) as u64);
                }
                _ => {}
            }
        }

        // Fallback to degraded mode local buffer
        let mut buf = self.degraded_buffer.write().await;
        buf.insert(req.idempotency_key.clone(), req);
        eprintln!("[DEGRADED] MCP socket unavailable, buffered locally");
        Ok(())
    }

    /// Retrieve state from MCP, fallback to degraded mode buffer.
    pub async fn get_global_state(&self, filter: GlobalStateFilter) -> Result<Vec<SwarmStatePayload>, String> {
        match self.fetch_via_unix_socket(&filter).await {
            Ok(state) => Ok(state),
            Err(_) => {
                // Degrade to local buffer
                let buf = self.degraded_buffer.read().await;
                let mut res = Vec::new();
                for val in buf.values() {
                    if let Some(ref phase) = filter.phase_filter {
                        if val.phase == *phase {
                            res.push(val.clone());
                        }
                    } else {
                        res.push(val.clone());
                    }
                }
                Ok(res)
            }
        }
    }

    async fn send_via_unix_socket(&self, _req: &SwarmStatePayload) -> Result<(), String> {
        // Stubbed Unix domain socket implementation.
        // Production: serialize via bincode/json to AF_UNIX socket at self.socket_path
        Err("Socket unavailable (stub)".into())
    }

    async fn fetch_via_unix_socket(&self, _filter: &GlobalStateFilter) -> Result<Vec<SwarmStatePayload>, String> {
        // Stubbed Unix domain socket implementation.
        Err("Socket unavailable (stub)".into())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use uuid::Uuid;

    #[test]
    fn test_flat_file_ban_state_md() {
        let client = SwarmMcpClient::new("/tmp/smaos.sock");
        assert!(client.block_flat_file_writes("project/STATE.md").is_err());
    }

    #[test]
    fn test_flat_file_ban_memory_md() {
        let client = SwarmMcpClient::new("/tmp/smaos.sock");
        assert!(client.block_flat_file_writes("project/MEMORY.md").is_err());
    }

    #[test]
    fn test_flat_file_allow_code() {
        let client = SwarmMcpClient::new("/tmp/smaos.sock");
        assert!(client.block_flat_file_writes("project/src/main.rs").is_ok());
    }

    #[tokio::test]
    async fn test_degraded_mode_fallback() {
        let client = SwarmMcpClient::new("/tmp/dead.sock");
        let req = SwarmStatePayload {
            idempotency_key: Uuid::new_v4().to_string(),
            agent_id: "agent-1".into(),
            phase: "PHASE_42".into(),
            status: "RUNNING".into(),
            payload_json: None,
        };

        let result = client.update_swarm_state(req.clone()).await;
        assert!(result.is_ok(), "should fall back to degraded mode");

        let state = client.get_global_state(GlobalStateFilter { phase_filter: None }).await.unwrap();
        assert_eq!(state.len(), 1);
        assert_eq!(state[0].idempotency_key, req.idempotency_key);
    }
}
