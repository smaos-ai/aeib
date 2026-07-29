use serde::{Deserialize, Serialize};
use uuid::Uuid;
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolRequest {
    pub tool_name: String,
    pub params: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolResponse {
    pub id: Uuid,
    pub result: String,
}

pub struct PalaceServer {
    version: String,
}

impl PalaceServer {
    pub fn new() -> Self {
        Self {
            version: "1.0.0".to_string(),
        }
    }

    pub async fn handle_request(&self, request: &ToolRequest) -> Result<ToolResponse, String> {
        match request.tool_name.as_str() {
            "memory.read" => self.handle_memory_read(request).await,
            "memory.write" => self.handle_memory_write(request).await,
            "memory.query" => self.handle_memory_query(request).await,
            _ => Err(format!("Unknown tool: {}", request.tool_name)),
        }
    }

    async fn handle_memory_read(&self, request: &ToolRequest) -> Result<ToolResponse, String> {
        Ok(ToolResponse {
            id: Uuid::new_v4(),
            result: format!("Read from memory: {:?}", request.params),
        })
    }

    async fn handle_memory_write(&self, request: &ToolRequest) -> Result<ToolResponse, String> {
        Ok(ToolResponse {
            id: Uuid::new_v4(),
            result: format!("Wrote to memory: {:?}", request.params),
        })
    }

    async fn handle_memory_query(&self, request: &ToolRequest) -> Result<ToolResponse, String> {
        Ok(ToolResponse {
            id: Uuid::new_v4(),
            result: format!("Queried memory: {:?}", request.params),
        })
    }

    pub fn protocol_version(&self) -> &str {
        &self.version
    }
}

impl Default for PalaceServer {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_server_creation() {
        let server = PalaceServer::new();
        assert_eq!(server.protocol_version(), "1.0.0");
    }

    #[tokio::test]
    async fn test_memory_read_request() {
        let server = PalaceServer::new();
        let request = ToolRequest {
            tool_name: "memory.read".to_string(),
            params: Default::default(),
        };
        let response = server.handle_request(&request).await;
        assert!(response.is_ok());
    }

    #[tokio::test]
    async fn test_memory_write_request() {
        let server = PalaceServer::new();
        let request = ToolRequest {
            tool_name: "memory.write".to_string(),
            params: Default::default(),
        };
        let response = server.handle_request(&request).await;
        assert!(response.is_ok());
    }

    #[tokio::test]
    async fn test_unknown_tool_error() {
        let server = PalaceServer::new();
        let request = ToolRequest {
            tool_name: "unknown.tool".to_string(),
            params: Default::default(),
        };
        let response = server.handle_request(&request).await;
        assert!(response.is_err());
    }
}
