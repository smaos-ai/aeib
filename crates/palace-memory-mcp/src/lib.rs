use chrono::{DateTime, Utc};
use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use uuid::Uuid;

pub mod ap2_ledger;
pub mod mcp_server;
pub mod memory_graph;

pub use ap2_ledger::{AP2Entry, AP2Ledger};
pub use mcp_server::{PalaceServer, ToolRequest, ToolResponse};
pub use memory_graph::{MemoryEntry, MemoryGraph, MemoryZone};

#[derive(Debug, Clone)]
pub struct PalaceState {
    pub id: Uuid,
    pub memory_graph: Arc<MemoryGraph>,
    pub ap2_ledger: Arc<AP2Ledger>,
    pub created_at: DateTime<Utc>,
    pub last_updated: DateTime<Utc>,
}

impl PalaceState {
    pub fn new() -> Self {
        Self {
            id: Uuid::new_v4(),
            memory_graph: Arc::new(MemoryGraph::new()),
            ap2_ledger: Arc::new(AP2Ledger::new()),
            created_at: Utc::now(),
            last_updated: Utc::now(),
        }
    }

    pub async fn invoke_tool(&self, request: &ToolRequest) -> Result<ToolResponse, String> {
        self.ap2_ledger.charge_budget(0.01).await?;
        self.memory_graph
            .log_invocation(request.tool_name.clone())
            .await;
        Ok(ToolResponse {
            id: Uuid::new_v4(),
            result: format!("Executed {}", request.tool_name),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_palace_state_creation() {
        let state = PalaceState::new();
        assert_eq!(state.id.is_nil(), false);
    }

    #[tokio::test]
    async fn test_tool_invocation() {
        let state = PalaceState::new();
        let request = ToolRequest {
            tool_name: "test_tool".to_string(),
            params: Default::default(),
        };
        let result = state.invoke_tool(&request).await;
        assert!(result.is_ok());
    }
}
