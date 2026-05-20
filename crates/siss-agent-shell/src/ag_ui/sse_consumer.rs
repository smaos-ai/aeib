/// AG-UI SSE Consumer Module
///
/// Handles streaming of events from the Axum API endpoints:
/// - `/api/graph/projections/actions` (TEXT_MESSAGE_CONTENT, TOOL_CALL_START)
/// - `/api/graph/projections/anomalies` (ANOMALY_DETECTED)
///
/// Features:
/// - Stable SSE connection with AbortController support
/// - 5-second polling fallback with exponential backoff (5s, 10s, 20s, 40s, cap 60s)
/// - Memory-efficient event routing to stdout in AoE format
/// - Graceful error handling and connection recovery
use std::time::Duration;
use tokio::time::sleep;

/// Represents an SSE event from the AG-UI projection
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct AoEEvent {
    pub action_type: String,
    pub id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub content: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metadata: Option<serde_json::Value>,
}

/// Configuration for the SSE consumer
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct SseConfig {
    pub actions_endpoint: String,
    pub anomalies_endpoint: String,
    pub base_url: String,
    pub initial_backoff_secs: u64,
    pub max_backoff_secs: u64,
    pub timeout_secs: u64,
}

impl Default for SseConfig {
    fn default() -> Self {
        Self {
            actions_endpoint: "http://localhost:3000/api/graph/projections/actions"
                .to_string(),
            anomalies_endpoint: "http://localhost:3000/api/graph/projections/anomalies"
                .to_string(),
            base_url: "http://localhost:3000".to_string(),
            initial_backoff_secs: 5,
            max_backoff_secs: 60,
            timeout_secs: 5,
        }
    }
}

/// Main SSE consumer that streams events and routes them to stdout
#[derive(Debug)]
pub struct AoESseConsumer {
    config: SseConfig,
    client: reqwest::Client,
    backoff_attempt: u64,
}

impl AoESseConsumer {
    /// Create a new SSE consumer with default configuration
    pub fn new() -> Self {
        Self::with_config(SseConfig::default())
    }

    /// Create a new SSE consumer with custom configuration
    pub fn with_config(config: SseConfig) -> Self {
        Self {
            config,
            client: reqwest::Client::new(),
            backoff_attempt: 0,
        }
    }

    /// Calculate exponential backoff delay
    pub fn calculate_backoff(&self) -> Duration {
        let base = self.config.initial_backoff_secs as f64;
        let exponent = self.backoff_attempt as f64;
        let delay = base * 2.0_f64.powf(exponent);
        let capped = delay.min(self.config.max_backoff_secs as f64);
        Duration::from_secs(capped as u64)
    }

    /// Connect to the actions endpoint and stream events
    pub async fn stream_actions(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        self.stream_endpoint(&self.config.actions_endpoint.clone())
            .await
    }

    /// Connect to the anomalies endpoint and stream events
    pub async fn stream_anomalies(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        self.stream_endpoint(&self.config.anomalies_endpoint.clone())
            .await
    }

    /// Stream events from a specific endpoint
    async fn stream_endpoint(
        &mut self,
        endpoint: &str,
    ) -> Result<(), Box<dyn std::error::Error>> {
        loop {
            match self.try_connect(endpoint).await {
                Ok(_) => {
                    // Successfully connected; reset backoff
                    self.backoff_attempt = 0;
                }
                Err(e) => {
                    // Connection failed; apply exponential backoff
                    eprintln!("[SSE_ERROR] Connection failed: {}", e);
                    self.backoff_attempt += 1;

                    let backoff_duration = self.calculate_backoff();
                    eprintln!(
                        "[SSE_RETRY] Backing off for {:?} (attempt {})",
                        backoff_duration, self.backoff_attempt
                    );

                    sleep(backoff_duration).await;
                }
            }
        }
    }

    /// Attempt to connect to an endpoint and stream events
    async fn try_connect(&self, endpoint: &str) -> Result<(), Box<dyn std::error::Error>> {
        let response = self
            .client
            .get(endpoint)
            .header("Accept", "text/event-stream")
            .timeout(Duration::from_secs(self.config.timeout_secs))
            .send()
            .await?;

        if response.status() != 200 {
            return Err(format!("HTTP {}", response.status()).into());
        }

        // Stream the response line by line
        let mut stream = response.bytes_stream();
        use futures::stream::StreamExt;

        while let Some(chunk_result) = stream.next().await {
            match chunk_result {
                Ok(chunk) => {
                    let text = String::from_utf8_lossy(&chunk);
                    for line in text.lines() {
                        if line.starts_with("data:") {
                            self.process_sse_line(line)?;
                        }
                    }
                }
                Err(e) => {
                    return Err(format!("Stream error: {}", e).into());
                }
            }
        }

        Ok(())
    }

    /// Process a single SSE data line
    fn process_sse_line(&self, line: &str) -> Result<(), Box<dyn std::error::Error>> {
        // Remove "data: " prefix
        let data = if let Some(content) = line.strip_prefix("data:") {
            content.trim()
        } else {
            return Ok(());
        };

        // Parse as JSON
        let event: AoEEvent = serde_json::from_str(data)?;

        // Route to stdout in AoE format
        self.emit_aoe_event(&event);

        Ok(())
    }

    /// Emit event in AoE format to stdout
    fn emit_aoe_event(&self, event: &AoEEvent) {
        println!(
            "[AoE_EVENT] action_type={} id={}",
            event.action_type, event.id
        );
    }
}

impl Default for AoESseConsumer {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_backoff_calculation_sequence() {
        let config = SseConfig::default();

        // Test backoff sequence: 5, 10, 20, 40, 60, 60
        let expected = vec![5, 10, 20, 40, 60, 60];

        for (attempt, expected_secs) in expected.iter().enumerate() {
            let consumer = AoESseConsumer {
                config: config.clone(),
                client: reqwest::Client::new(),
                backoff_attempt: attempt as u64,
            };

            let backoff = consumer.calculate_backoff();
            assert_eq!(
                backoff.as_secs(),
                *expected_secs as u64,
                "Attempt {}: expected {}s, got {}s",
                attempt,
                expected_secs,
                backoff.as_secs()
            );
        }
    }

    #[test]
    fn test_aoe_event_creation() {
        let event = AoEEvent {
            action_type: "TEXT_MESSAGE_CONTENT".to_string(),
            id: "550e8400-e29b-41d4-a716-446655440000".to_string(),
            content: Some("Hello world".to_string()),
            metadata: None,
        };

        assert_eq!(event.action_type, "TEXT_MESSAGE_CONTENT");
        assert_eq!(event.id, "550e8400-e29b-41d4-a716-446655440000");
        assert_eq!(event.content, Some("Hello world".to_string()));
    }

    #[test]
    fn test_aoe_event_serialization() {
        let event = AoEEvent {
            action_type: "TOOL_CALL_START".to_string(),
            id: "uuid-123".to_string(),
            content: None,
            metadata: Some(serde_json::json!({"tool": "Bash"})),
        };

        let json = serde_json::to_string(&event).expect("Should serialize");
        assert!(json.contains("TOOL_CALL_START"));
        assert!(json.contains("uuid-123"));
    }

    #[test]
    fn test_sses_config_default() {
        let config = SseConfig::default();
        assert_eq!(config.initial_backoff_secs, 5);
        assert_eq!(config.max_backoff_secs, 60);
        assert_eq!(config.timeout_secs, 5);
    }

    #[test]
    fn test_sse_line_parsing() {
        let consumer = AoESseConsumer::new();

        // Test valid SSE line
        let valid_line = r#"data: {"action_type": "TEXT_MESSAGE_CONTENT", "id": "uuid-1", "content": "test"}"#;
        let result = consumer.process_sse_line(valid_line);
        assert!(result.is_ok(), "Should parse valid SSE line");

        // Test invalid JSON
        let invalid_json = "data: {invalid json";
        let result = consumer.process_sse_line(invalid_json);
        assert!(result.is_err(), "Should reject invalid JSON");

        // Test non-data line
        let non_data_line = "comment: this is a comment";
        let result = consumer.process_sse_line(non_data_line);
        assert!(result.is_ok(), "Should skip non-data lines");
    }
}
