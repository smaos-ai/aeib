use async_trait::async_trait;
use reqwest::Client;
use std::sync::Arc;
use std::time::Duration;

use crate::routing::canary_router::{Payload, ShadowAdapter, ShadowInferenceResult};

pub struct RapidMLXAdapter {
    client: Client,
    endpoint: String,
    roma_endpoint: String,
    mint_endpoint: String,
    corebench_endpoint: String,
    eval_timeout: Duration,
}

impl RapidMLXAdapter {
    pub fn new(endpoint: &str) -> Self {
        Self {
            client: Client::new(),
            endpoint: endpoint.to_string(),
            roma_endpoint: String::new(),
            mint_endpoint: String::new(),
            corebench_endpoint: String::new(),
            eval_timeout: Duration::from_millis(200),
        }
    }

    pub fn with_eval_endpoints(
        endpoint: &str,
        roma_endpoint: &str,
        mint_endpoint: &str,
        corebench_endpoint: &str,
    ) -> Self {
        Self {
            client: Client::new(),
            endpoint: endpoint.to_string(),
            roma_endpoint: roma_endpoint.to_string(),
            mint_endpoint: mint_endpoint.to_string(),
            corebench_endpoint: corebench_endpoint.to_string(),
            eval_timeout: Duration::from_millis(200),
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

    async fn call_roma(&self, _payload: &Payload) -> f64 {
        if self.roma_endpoint.is_empty() {
            return 0.0;
        }
        let body = serde_json::json!({ "payload": "robustness" });
        match tokio::time::timeout(
            self.eval_timeout,
            self.client.post(&self.roma_endpoint).json(&body).send(),
        )
        .await
        {
            Ok(Ok(resp)) if resp.status().is_success() => resp
                .json::<serde_json::Value>()
                .await
                .ok()
                .and_then(|v| v.get("score").and_then(|s| s.as_f64()))
                .unwrap_or(0.0)
                .clamp(0.0, 1.0),
            _ => 0.0,
        }
    }

    async fn call_mint(&self, _payload: &Payload) -> f64 {
        if self.mint_endpoint.is_empty() {
            return 0.0;
        }
        let body = serde_json::json!({ "payload": "alignment" });
        match tokio::time::timeout(
            self.eval_timeout,
            self.client.post(&self.mint_endpoint).json(&body).send(),
        )
        .await
        {
            Ok(Ok(resp)) if resp.status().is_success() => resp
                .json::<serde_json::Value>()
                .await
                .ok()
                .and_then(|v| v.get("score").and_then(|s| s.as_f64()))
                .unwrap_or(0.0)
                .clamp(0.0, 1.0),
            _ => 0.0,
        }
    }

    async fn call_corebench(&self, _payload: &Payload) -> f64 {
        if self.corebench_endpoint.is_empty() {
            return 0.0;
        }
        let body = serde_json::json!({ "payload": "corebench" });
        match tokio::time::timeout(
            self.eval_timeout,
            self.client
                .post(&self.corebench_endpoint)
                .json(&body)
                .send(),
        )
        .await
        {
            Ok(Ok(resp)) if resp.status().is_success() => resp
                .json::<serde_json::Value>()
                .await
                .ok()
                .and_then(|v| v.get("score").and_then(|s| s.as_f64()))
                .unwrap_or(0.0)
                .clamp(0.0, 1.0),
            _ => 0.0,
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

        let (robustness_score, alignment_score, corebench_score) = tokio::join!(
            self.call_roma(&payload),
            self.call_mint(&payload),
            self.call_corebench(&payload),
        );

        Ok(ShadowInferenceResult {
            divergence,
            f1_score,
            robustness_score,
            alignment_score,
            corebench_score,
            per_modality: vec![],
        })
    }
}
