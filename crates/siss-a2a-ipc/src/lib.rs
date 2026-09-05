/// Phase 2B: A2A IPC Layer — Local loopback socket communication between agents
/// Uses Unix domain sockets with JSON/CBOR serialization and Ed25519 signing
/// Message format: { payload, signature, agent_id, timestamp }

use anyhow::{anyhow, Result};
use async_trait::async_trait;
use chrono::{DateTime, Utc};
use ed25519_dalek::{SigningKey, Signer};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::sync::{atomic::{AtomicU32, AtomicU64, Ordering}, Arc, Mutex};
use std::time::Duration;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::{UnixListener, UnixStream};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct A2AMessage {
    pub agent_id: Uuid,
    pub message_type: MessageType,
    pub payload: serde_json::Value,
    pub timestamp: DateTime<Utc>,
    pub signature: String, // hex-encoded Ed25519 signature
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum MessageType {
    PlannerToCompliance,
    ComplianceToEvidence,
    EvidenceToLedger,
    HealthCheck,
    Ack,
    Nack,
}

#[derive(Debug, Clone)]
pub struct IPCConfig {
    pub socket_path: PathBuf,
    pub max_message_size: usize,
    pub timeout_secs: u64,
}

impl Default for IPCConfig {
    fn default() -> Self {
        Self {
            socket_path: PathBuf::from("/tmp/siss-a2a.sock"),
            max_message_size: 16 * 1024 * 1024, // 16 MB
            timeout_secs: 30,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CircuitBreakerStatus {
    pub state: String, // "open" | "closed" | "half-open"
    pub failure_count: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MessageMetrics {
    pub sent: u64,
    pub received: u64,
    pub failures: u64,
}

struct CircuitBreaker {
    state: Mutex<String>,
    failure_count: AtomicU32,
    last_failure_time: Mutex<Option<DateTime<Utc>>>,
    threshold: u32,
    timeout_secs: u64,
}

impl CircuitBreaker {
    fn new() -> Self {
        Self {
            state: Mutex::new("closed".to_string()),
            failure_count: AtomicU32::new(0),
            last_failure_time: Mutex::new(None),
            threshold: 5,
            timeout_secs: 60,
        }
    }

    fn record_failure(&self) {
        self.failure_count.fetch_add(1, Ordering::SeqCst);
        *self.last_failure_time.lock().unwrap() = Some(Utc::now());
        if self.failure_count.load(Ordering::SeqCst) >= self.threshold {
            *self.state.lock().unwrap() = "open".to_string();
        }
    }

    fn record_success(&self) {
        self.failure_count.store(0, Ordering::SeqCst);
        *self.state.lock().unwrap() = "closed".to_string();
    }

    fn is_open(&self) -> bool {
        let state = self.state.lock().unwrap();
        if state.as_str() == "open" {
            if let Some(last_fail) = *self.last_failure_time.lock().unwrap() {
                let elapsed = Utc::now().signed_duration_since(last_fail).num_seconds();
                return elapsed < self.timeout_secs as i64;
            }
            return true;
        }
        false
    }

    fn get_status(&self) -> CircuitBreakerStatus {
        CircuitBreakerStatus {
            state: self.state.lock().unwrap().clone(),
            failure_count: self.failure_count.load(Ordering::SeqCst),
        }
    }
}

#[async_trait]
pub trait IPCServer: Send + Sync {
    async fn start(&self) -> Result<()>;
    async fn handle_message(&self, msg: A2AMessage) -> Result<A2AMessage>;
}

#[async_trait]
pub trait IPCClient: Send + Sync {
    async fn send(&self, msg: A2AMessage) -> Result<A2AMessage>;
}

pub struct LocalIPCServer {
    config: IPCConfig,
    signing_key: SigningKey,
    agent_id: Uuid,
}

impl LocalIPCServer {
    pub fn new(config: IPCConfig, signing_key: SigningKey, agent_id: Uuid) -> Self {
        Self {
            config,
            signing_key,
            agent_id,
        }
    }

    pub async fn listen(&self) -> Result<()> {
        // Remove existing socket if present
        let _ = std::fs::remove_file(&self.config.socket_path);

        let listener = UnixListener::bind(&self.config.socket_path)?;
        log::info!(
            "A2A IPC server listening on {:?}",
            self.config.socket_path
        );

        loop {
            match listener.accept().await {
                Ok((mut socket, _)) => {
                    let mut buf = vec![0u8; self.config.max_message_size];
                    match socket.read(&mut buf).await {
                        Ok(n) => {
                            let msg_bytes = &buf[..n];
                            match self.deserialize_message(msg_bytes).await {
                                Ok(msg) => {
                                    if self.verify_signature(&msg).await.is_ok() {
                                        let response = A2AMessage {
                                            agent_id: self.agent_id,
                                            message_type: MessageType::Ack,
                                            payload: serde_json::json!({"status": "received"}),
                                            timestamp: Utc::now(),
                                            signature: String::new(), // Will be signed
                                        };
                                        let signed_response = self.sign_message(response).await?;
                                        let response_bytes = serde_json::to_vec(&signed_response)?;
                                        let _ = socket.write_all(&response_bytes).await;
                                    } else {
                                        let nack = A2AMessage {
                                            agent_id: self.agent_id,
                                            message_type: MessageType::Nack,
                                            payload: serde_json::json!({"error": "signature_invalid"}),
                                            timestamp: Utc::now(),
                                            signature: String::new(),
                                        };
                                        let signed_nack = self.sign_message(nack).await?;
                                        let nack_bytes = serde_json::to_vec(&signed_nack)?;
                                        let _ = socket.write_all(&nack_bytes).await;
                                    }
                                }
                                Err(e) => {
                                    log::warn!("Failed to deserialize message: {}", e);
                                }
                            }
                        }
                        Err(e) => {
                            log::warn!("Read error: {}", e);
                        }
                    }
                }
                Err(e) => {
                    log::warn!("Accept error: {}", e);
                }
            }
        }
    }

    async fn deserialize_message(&self, bytes: &[u8]) -> Result<A2AMessage> {
        Ok(serde_json::from_slice(bytes)?)
    }

    async fn sign_message(&self, mut msg: A2AMessage) -> Result<A2AMessage> {
        // Sign the JSON payload (without signature field)
        let payload_bytes = serde_json::to_vec(&msg.payload)?;
        let signature = self.signing_key.sign(&payload_bytes);
        msg.signature = hex::encode(signature.to_bytes());
        Ok(msg)
    }

    async fn verify_signature(&self, _msg: &A2AMessage) -> Result<()> {
        // For now, skip verification in server (would need public key registry)
        // In production, look up verifying key from agent registry
        Ok(())
    }
}

pub struct LocalIPCClient {
    config: IPCConfig,
    signing_key: SigningKey,
    agent_id: Uuid,
    circuit_breaker: Arc<CircuitBreaker>,
    metrics: Arc<(AtomicU64, AtomicU64, AtomicU64)>, // sent, received, failures
    message_sequence: AtomicU64,
}

impl LocalIPCClient {
    pub fn new(config: IPCConfig, signing_key: SigningKey, agent_id: Uuid) -> Self {
        Self {
            config,
            signing_key,
            agent_id,
            circuit_breaker: Arc::new(CircuitBreaker::new()),
            metrics: Arc::new((AtomicU64::new(0), AtomicU64::new(0), AtomicU64::new(0))),
            message_sequence: AtomicU64::new(0),
        }
    }

    pub async fn send_message(&self, msg: A2AMessage) -> Result<A2AMessage> {
        let _seq = self.message_sequence.fetch_add(1, Ordering::SeqCst);
        let mut socket = UnixStream::connect(&self.config.socket_path).await?;
        let signed_msg = self.sign_message(msg).await?;
        let msg_bytes = serde_json::to_vec(&signed_msg)?;
        socket.write_all(&msg_bytes).await?;
        socket.flush().await?;
        self.metrics.0.fetch_add(1, Ordering::SeqCst);

        let mut buf = vec![0u8; self.config.max_message_size];
        let n = socket.read(&mut buf).await?;
        let response_bytes = &buf[..n];
        let response = serde_json::from_slice(response_bytes)?;
        self.metrics.1.fetch_add(1, Ordering::SeqCst);
        Ok(response)
    }

    async fn sign_message(&self, mut msg: A2AMessage) -> Result<A2AMessage> {
        let payload_bytes = serde_json::to_vec(&msg.payload)?;
        let signature = self.signing_key.sign(&payload_bytes);
        msg.signature = hex::encode(signature.to_bytes());
        Ok(msg)
    }

    pub async fn send_with_retry(&self, msg: A2AMessage) -> Result<A2AMessage> {
        if self.circuit_breaker.is_open() {
            self.metrics.2.fetch_add(1, Ordering::SeqCst);
            return Err(anyhow!("Circuit breaker is open"));
        }

        let max_retries = 3;
        let mut backoff_ms = 100u64;

        for attempt in 0..max_retries {
            match self.send_message(msg.clone()).await {
                Ok(response) => {
                    self.circuit_breaker.record_success();
                    self.metrics.1.fetch_add(1, Ordering::SeqCst);
                    return Ok(response);
                }
                Err(e) => {
                    self.circuit_breaker.record_failure();
                    self.metrics.2.fetch_add(1, Ordering::SeqCst);
                    if attempt < max_retries - 1 {
                        tokio::time::sleep(Duration::from_millis(backoff_ms)).await;
                        backoff_ms = (backoff_ms * 2).min(5000);
                    } else {
                        return Err(e);
                    }
                }
            }
        }

        Err(anyhow!("Max retries exceeded"))
    }

    pub fn get_circuit_breaker_status(&self) -> CircuitBreakerStatus {
        self.circuit_breaker.get_status()
    }

    pub fn get_metrics(&self) -> MessageMetrics {
        MessageMetrics {
            sent: self.metrics.0.load(Ordering::SeqCst),
            received: self.metrics.1.load(Ordering::SeqCst),
            failures: self.metrics.2.load(Ordering::SeqCst),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_message_serialization() {
        let msg = A2AMessage {
            agent_id: Uuid::nil(),
            message_type: MessageType::HealthCheck,
            payload: serde_json::json!({"status": "ok"}),
            timestamp: Utc::now(),
            signature: "test_sig".to_string(),
        };
        let json = serde_json::to_string(&msg).unwrap();
        let deserialized: A2AMessage = serde_json::from_str(&json).unwrap();
        assert_eq!(msg.agent_id, deserialized.agent_id);
        assert_eq!(msg.message_type, deserialized.message_type);
    }

    #[test]
    fn test_message_type_variants() {
        assert_eq!(MessageType::PlannerToCompliance, MessageType::PlannerToCompliance);
        assert_ne!(MessageType::HealthCheck, MessageType::Ack);
    }

    #[test]
    fn test_default_ipc_config() {
        let config = IPCConfig::default();
        assert_eq!(config.max_message_size, 16 * 1024 * 1024);
        assert_eq!(config.timeout_secs, 30);
    }
}
