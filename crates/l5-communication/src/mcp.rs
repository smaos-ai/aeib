use serde::{Deserialize, Serialize};
use uuid::Uuid;
use chrono::{DateTime, Utc};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ServerType {
    Request,
    Policy,
    Audit,
    Feedback,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct McpServer {
    pub id: String,
    pub server_type: ServerType,
    pub endpoint: String,
    pub status: String,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct McpRequest {
    pub request_id: String,
    pub method: String,
    pub params: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct McpResponse {
    pub request_id: String,
    pub result: serde_json::Value,
    pub timestamp: DateTime<Utc>,
}

pub struct McpRegistry {
    servers: Vec<McpServer>,
}

impl McpRegistry {
    pub fn new() -> Self {
        Self {
            servers: Vec::new(),
        }
    }

    pub fn register_server(&mut self, server_type: ServerType, endpoint: String) -> McpServer {
        let server = McpServer {
            id: Uuid::new_v4().to_string(),
            server_type,
            endpoint,
            status: "ready".to_string(),
            created_at: Utc::now(),
        };
        self.servers.push(server.clone());
        server
    }

    pub fn get_server(&self, server_type: ServerType) -> Option<&McpServer> {
        self.servers.iter().find(|s| s.server_type == server_type)
    }

    pub fn list_servers(&self) -> &[McpServer] {
        &self.servers
    }

    pub fn handle_request(&self, request: &McpRequest) -> Result<McpResponse, String> {
        let response = McpResponse {
            request_id: request.request_id.clone(),
            result: serde_json::json!({"status": "processed"}),
            timestamp: Utc::now(),
        };
        Ok(response)
    }
}

impl Default for McpRegistry {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_register_server() {
        let mut registry = McpRegistry::new();
        let server = registry.register_server(
            ServerType::Policy,
            "http://localhost:8001/policy".to_string(),
        );

        assert_eq!(server.server_type, ServerType::Policy);
        assert_eq!(server.status, "ready");
    }

    #[test]
    fn test_get_server() {
        let mut registry = McpRegistry::new();
        registry.register_server(
            ServerType::Audit,
            "http://localhost:8003/audit".to_string(),
        );

        let server = registry.get_server(ServerType::Audit);
        assert!(server.is_some());
        assert_eq!(server.unwrap().server_type, ServerType::Audit);
    }

    #[test]
    fn test_list_servers() {
        let mut registry = McpRegistry::new();
        registry.register_server(ServerType::Request, "http://localhost:8000".to_string());
        registry.register_server(ServerType::Policy, "http://localhost:8001".to_string());

        assert_eq!(registry.list_servers().len(), 2);
    }

    #[test]
    fn test_handle_request() {
        let registry = McpRegistry::new();
        let request = McpRequest {
            request_id: Uuid::new_v4().to_string(),
            method: "get_policy".to_string(),
            params: serde_json::json!({"article": "50"}),
        };

        let response = registry.handle_request(&request);
        assert!(response.is_ok());
    }
}
