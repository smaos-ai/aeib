use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum RouteDecision {
    Allow,
    Deny,
    Defer,
}

#[derive(Debug, Clone)]
pub struct McpRouter {
    pub id: Uuid,
    pub name: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RoutingRequest {
    pub tool_name: String,
    pub schema: serde_json::Value,
    pub confidence: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RoutingResponse {
    pub decision: RouteDecision,
    pub reason: Option<String>,
}

impl McpRouter {
    pub fn new(name: String) -> Self {
        Self {
            id: Uuid::new_v4(),
            name,
        }
    }

    pub fn route(&self, request: &RoutingRequest) -> RoutingResponse {
        // For now, use a default confidence threshold of 0.5
        let confidence_threshold = 0.5;

        if request.confidence < confidence_threshold {
            RoutingResponse {
                decision: RouteDecision::Defer,
                reason: Some("Confidence score below threshold".to_string()),
            }
        } else {
            RoutingResponse {
                decision: RouteDecision::Allow,
                reason: None,
            }
        }
    }

    pub fn evaluate_tool(&self, _tool_name: &str) -> Result<bool, String> {
        unimplemented!()
    }

    pub fn select_skill(&self, _tool_name: &str, _confidence: f64) -> RouteDecision {
        unimplemented!()
    }
}

impl Default for McpRouter {
    fn default() -> Self {
        Self::new("default-router".to_string())
    }
}
