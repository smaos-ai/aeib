use async_trait::async_trait;
use reqwest::Client;
use std::sync::Arc;

use crate::routing::canary_router::{Payload, ShadowAdapter, ShadowInferenceResult};

pub struct RapidMLXAdapter {
    client: Client,
    endpoint: String,
}

impl RapidMLXAdapter {
    pub fn new(endpoint: &str) -> Self {
        Self {
            client: Client::new(),
            endpoint: endpoint.to_string(),
        }
    }

    pub fn compute_divergence_for_test(
        &self,
        shadow_logprobs: &[f64],
        baseline_logprobs: &[f64],
    ) -> f64 {
        self.compute_divergence(shadow_logprobs, baseline_logprobs)
    }

    fn compute_divergence(&self, shadow_logprobs: &[f64], baseline_logprobs: &[f64]) -> f64 {
        if shadow_logprobs.is_empty() || baseline_logprobs.is_empty() {
            return 0.0;
        }

        let min_len = shadow_logprobs.len().min(baseline_logprobs.len());
        let mut kl_divergence = 0.0;

        for i in 0..min_len {
            let p = baseline_logprobs[i].exp();
            let q = shadow_logprobs[i].exp();

            if p > 0.0 && q > 0.0 {
                kl_divergence += p * (baseline_logprobs[i] - shadow_logprobs[i]);
            }
        }

        kl_divergence.abs().min(1.0)
    }

    pub fn compute_tool_f1_for_test(
        &self,
        shadow_tools: &serde_json::Value,
        baseline_tools: &serde_json::Value,
    ) -> f64 {
        self.compute_tool_f1(shadow_tools, baseline_tools)
    }

    fn compute_tool_f1(
        &self,
        shadow_tools: &serde_json::Value,
        baseline_tools: &serde_json::Value,
    ) -> f64 {
        let shadow_str = shadow_tools.to_string();
        let baseline_str = baseline_tools.to_string();

        if shadow_str == baseline_str {
            1.0
        } else {
            let shadow_tokens: Vec<&str> = shadow_str.split_whitespace().collect();
            let baseline_tokens: Vec<&str> = baseline_str.split_whitespace().collect();

            if shadow_tokens.is_empty() && baseline_tokens.is_empty() {
                return 1.0;
            }

            if shadow_tokens.is_empty() || baseline_tokens.is_empty() {
                return 0.0;
            }

            let mut matches = 0;
            for token in &shadow_tokens {
                if baseline_tokens.contains(token) {
                    matches += 1;
                }
            }

            let precision = matches as f64 / shadow_tokens.len() as f64;
            let recall = matches as f64 / baseline_tokens.len() as f64;

            if precision + recall > 0.0 {
                2.0 * (precision * recall) / (precision + recall)
            } else {
                0.0
            }
        }
    }
}

#[async_trait]
impl ShadowAdapter for RapidMLXAdapter {
    async fn evaluate(&self, payload: Arc<Payload>) -> Result<ShadowInferenceResult, String> {
        let request_body = serde_json::json!({
            "model": "mlx-community/Mistral-7B-Instruct-v0.1",
            "messages": [{"role": "user", "content": "test"}],
            "logprobs": true,
            "top_logprobs": 5,
        });

        let response = self
            .client
            .post(&self.endpoint)
            .json(&request_body)
            .send()
            .await
            .map_err(|e| format!("HTTP request failed: {}", e))?;

        if !response.status().is_success() {
            return Err(format!("HTTP error: {}", response.status()));
        }

        let body: serde_json::Value = response
            .json()
            .await
            .map_err(|e| format!("Failed to parse response: {}", e))?;

        let shadow_logprobs = body
            .get("choices")
            .and_then(|c| c.get(0))
            .and_then(|c| c.get("logprobs"))
            .map(|l| {
                l.as_array()
                    .unwrap_or(&vec![])
                    .iter()
                    .filter_map(|v| v.as_f64())
                    .collect::<Vec<f64>>()
            })
            .unwrap_or_default();

        let shadow_tools = body
            .get("choices")
            .and_then(|c| c.get(0))
            .and_then(|c| c.get("message"))
            .and_then(|m| m.get("tool_calls"))
            .cloned()
            .unwrap_or(serde_json::json!([]));

        let divergence = self.compute_divergence(&shadow_logprobs, &payload.baseline_logprobs);
        let f1_score = self.compute_tool_f1(&shadow_tools, &payload.baseline_tools);

        Ok(ShadowInferenceResult {
            divergence,
            f1_score,
        })
    }
}
