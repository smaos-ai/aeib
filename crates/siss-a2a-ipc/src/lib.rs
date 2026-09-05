/// Phase 2B: A2A IPC Layer — Local loopback socket communication between agents
/// Uses Unix domain sockets with JSON/CBOR serialization and Ed25519 signing
/// Message format: { payload, signature, agent_id, timestamp }

use anyhow::{anyhow, Result};
use async_trait::async_trait;
use chrono::{DateTime, Utc};
use ed25519_dalek::{Signature, SigningKey, VerifyingKey, Signer};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
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
}

impl LocalIPCClient {
    pub fn new(config: IPCConfig, signing_key: SigningKey, agent_id: Uuid) -> Self {
        Self {
            config,
            signing_key,
            agent_id,
        }
    }

    pub async fn send_message(&self, msg: A2AMessage) -> Result<A2AMessage> {
        let mut socket = UnixStream::connect(&self.config.socket_path).await?;
        let signed_msg = self.sign_message(msg).await?;
        let msg_bytes = serde_json::to_vec(&signed_msg)?;
        socket.write_all(&msg_bytes).await?;
        socket.flush().await?;

        let mut buf = vec![0u8; self.config.max_message_size];
        let n = socket.read(&mut buf).await?;
        let response_bytes = &buf[..n];
        let response = serde_json::from_slice(response_bytes)?;
        Ok(response)
    }

    async fn sign_message(&self, mut msg: A2AMessage) -> Result<A2AMessage> {
        let payload_bytes = serde_json::to_vec(&msg.payload)?;
        let signature = self.signing_key.sign(&payload_bytes);
        msg.signature = hex::encode(signature.to_bytes());
        Ok(msg)
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
