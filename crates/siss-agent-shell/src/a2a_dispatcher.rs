/// Phase 58: A2A Dispatcher — JSON-RPC + SSE stream parsing

use serde::{Deserialize, Serialize};
use siss_gatekeeper::tokens::IntentMandate;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct JsonRpcRequest {
    pub jsonrpc: String,
    pub id: Uuid,
    pub method: String,
    pub params: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JsonRpcError {
    pub code: i32,
    pub message: String,
    pub data: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JsonRpcResponse {
    pub jsonrpc: String,
    pub id: Uuid,
    pub result: Option<serde_json::Value>,
    pub error: Option<JsonRpcError>,
}

#[derive(Debug, Clone, PartialEq)]
pub enum A2AStreamEvent {
    Step { step_id: Uuid, content: String },
    Done,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DispatchError {
    MandateRequired,
    InsufficientBudget { required: i64, available: i64 },
    SerializationFailed(String),
}

pub struct A2ADispatcher;

impl A2ADispatcher {
    /// Validate dispatch permission.
    /// RULE 1: mandate required
    /// RULE 2: budget check
    pub fn validate_dispatch(
        mandate: Option<&IntentMandate>,
        budget_required: i64,
    ) -> Result<(), DispatchError> {
        let m = mandate.ok_or(DispatchError::MandateRequired)?;

        let remaining = m.budget_limit - m.budget_spent;
        if remaining < budget_required {
            return Err(DispatchError::InsufficientBudget {
                required: budget_required,
                available: remaining,
            });
        }

        Ok(())
    }

    /// Build JSON-RPC 2.0 request.
    pub fn build_request(method: &str, params: serde_json::Value) -> JsonRpcRequest {
        JsonRpcRequest {
            jsonrpc: "2.0".to_string(),
            id: Uuid::new_v4(),
            method: method.to_string(),
            params,
        }
    }

    /// Parse a single SSE line.
    /// RULE 6: non-data lines → None
    /// RULE 7: "done" event → Some(Done)
    /// RULE 8: JSON step → Some(Step)
    /// RULE 9: malformed → None
    pub fn parse_sse_line(line: &str) -> Option<A2AStreamEvent> {
        if !line.starts_with("data:") {
            return None;
        }

        let data = line[5..].trim();

        if data.to_lowercase() == "done" {
            return Some(A2AStreamEvent::Done);
        }

        if let Ok(val) = serde_json::from_str::<serde_json::Value>(data) {
            if let (Some(step_id_str), Some(content_str)) =
                (val.get("step_id").and_then(|v| v.as_str()),
                 val.get("content").and_then(|v| v.as_str()))
            {
                if let Ok(step_id) = Uuid::parse_str(step_id_str) {
                    return Some(A2AStreamEvent::Step {
                        step_id,
                        content: content_str.to_string(),
                    });
                }
            }
        }

        None
    }

    /// Parse full SSE stream.
    pub fn parse_sse_stream(raw: &str) -> Vec<A2AStreamEvent> {
        raw.lines()
            .filter_map(|line| Self::parse_sse_line(line))
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_build_request() {
        let req = A2ADispatcher::build_request("test", serde_json::json!({}));
        assert_eq!(req.jsonrpc, "2.0");
        assert_eq!(req.method, "test");
    }
}
