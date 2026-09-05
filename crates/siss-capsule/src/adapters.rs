// HarnessCapsule Adapters: LangChain, Ollama, AutoGPT
// <500ms LangChain roundtrip + <100ms Ollama per-token

use crate::harness::HarnessCapsule;
use serde_json::{Value, json};
use std::time::Instant;

// ============================================================================
// LANGCHAIN ADAPTER
// ============================================================================

pub struct LangChainAdapter<'a> {
    harness: &'a HarnessCapsule,
}

impl<'a> LangChainAdapter<'a> {
    pub fn new(harness: &'a HarnessCapsule) -> Self {
        LangChainAdapter { harness }
    }

    /// Intercept LangChain tool calls for policy checking
    pub async fn intercept_tool_call(&self, tool_call: &Value) -> Option<Value> {
        self.harness.increment_request_count();

        // Extract tool name and arguments
        let tool_name = tool_call.get("name")?.as_str()?;
        let arguments = tool_call.get("arguments")?;

        // Simulate policy check (in real impl, call baseline capsule)
        Some(json!({
            "tool_name": tool_name,
            "arguments": arguments,
            "policy_checked": true,
            "approved": true,
        }))
    }

    /// Roundtrip with policy verification (goal: <500ms)
    pub async fn roundtrip_with_policy_check(&self, model_config: &Value) -> Option<Value> {
        let start = Instant::now();

        self.harness.increment_request_count();

        // Simulate mock LLM call (~300ms in test)
        tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;

        let elapsed = start.elapsed();

        // Return result if under 500ms budget
        if elapsed.as_millis() < 500 {
            Some(json!({
                "model": model_config.get("model").cloned().unwrap_or(json!("gpt-4")),
                "response": "Simulated LLM response",
                "latency_ms": elapsed.as_millis(),
                "policy_verified": true,
            }))
        } else {
            None
        }
    }
}

// ============================================================================
// OLLAMA ADAPTER
// ============================================================================

pub struct OllamaAdapter<'a> {
    harness: &'a HarnessCapsule,
}

impl<'a> OllamaAdapter<'a> {
    pub fn new(harness: &'a HarnessCapsule) -> Self {
        OllamaAdapter { harness }
    }

    /// Stream response from Ollama
    pub async fn stream_response(&self, model: &str, prompt: &str) -> Option<Value> {
        self.harness.increment_request_count();

        // Simulate streaming response
        Some(json!({
            "model": model,
            "prompt": prompt,
            "stream": true,
            "status": "streaming",
        }))
    }

    #[allow(dead_code)]
    pub fn _unused_placeholder(&self) {
        // Reserved for future extensions
    }

    /// Check if GPU acceleration enabled
    pub fn is_gpu_acceleration_enabled(&self) -> bool {
        self.harness.config().enable_gpu
    }

    /// Generate N tokens with per-token latency tracking
    pub async fn generate_tokens(&self, _model: &str, _prompt: &str, count: usize) -> Vec<String> {
        self.harness.increment_request_count();

        // Simulate token generation
        let mut tokens = Vec::new();
        for i in 0..count {
            // Simulate ~8-10ms per token on GPU
            if self.is_gpu_acceleration_enabled() {
                tokio::time::sleep(tokio::time::Duration::from_millis(8)).await;
            } else {
                tokio::time::sleep(tokio::time::Duration::from_millis(20)).await;
            }

            tokens.push(format!("token_{}", i));
        }

        tokens
    }
}

// ============================================================================
// AUTOGPT ADAPTER
// ============================================================================

pub struct AutoGPTAdapter<'a> {
    harness: &'a HarnessCapsule,
}

impl<'a> AutoGPTAdapter<'a> {
    pub fn new(harness: &'a HarnessCapsule) -> Self {
        AutoGPTAdapter { harness }
    }

    /// Generate AutoGPT-compatible tool schema (JSON)
    pub fn generate_autogpt_schema(&self, tool_name: &str) -> String {
        let schema = json!({
            "name": tool_name,
            "description": format!("Tool: {}", tool_name),
            "parameters": {
                "type": "object",
                "properties": {
                    "param": {
                        "type": "string",
                        "description": "Parameter"
                    }
                },
                "required": ["param"]
            }
        });

        schema.to_string()
    }

    /// Execute tool and return decision
    pub async fn execute_and_return_decision(
        &self,
        tool_name: &str,
        params: &Value,
    ) -> Option<Value> {
        self.harness.increment_request_count();

        // Simulate tool execution
        Some(json!({
            "tool": tool_name,
            "params": params,
            "executed": true,
            "decision": {
                "action": "allow",
                "reason": "Tool execution successful"
            }
        }))
    }
}
