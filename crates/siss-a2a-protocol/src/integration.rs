/// Integration bridge: Phase 2B Part 1 IPC ↔ A2A Protocol
///
/// Adapts siss-a2a-ipc messages to A2AEnvelope format and vice versa.
/// Handles agent registration, message routing, and signature validation.

use crate::protocol::{A2AMessage, A2AEnvelope, MessageType, MessageStatus};
use crate::discovery::PeerManifest;
use crate::error::{A2AError, Result};
use anyhow::anyhow;
use ed25519_dalek::VerifyingKey;
use serde::{Deserialize, Serialize};
use siss_a2a_ipc::{A2AMessage as IPCMessage, IPCConfig, LocalIPCClient};
use std::collections::HashMap;
use std::sync::Arc;
use uuid::Uuid;

/// Convert Phase 2B Part 1 IPC message to A2A protocol envelope
pub fn ipc_to_a2a(ipc_msg: &IPCMessage, signer_pubkey: String) -> Result<A2AEnvelope> {
    let a2a_msg = A2AMessage {
        id: Uuid::new_v4().to_string(),
        msg_type: map_ipc_type_to_a2a(&ipc_msg.message_type),
        status: MessageStatus::Success,
        from_agent: ipc_msg.agent_id.to_string(),
        to_agent: None,
        timestamp: ipc_msg.timestamp,
        payload: ipc_msg.payload.clone(),
        trace_id: None,
        request_id: Some(ipc_msg.agent_id.to_string()),
    };

    let mut envelope = A2AEnvelope::new(a2a_msg);
    envelope.signature = format!("ed25519:{}", ipc_msg.signature.clone());
    envelope.signer_pubkey = signer_pubkey;

    Ok(envelope)
}

/// Convert A2A protocol envelope to Phase 2B Part 1 IPC message
pub fn a2a_to_ipc(envelope: &A2AEnvelope, agent_id: Uuid) -> Result<IPCMessage> {
    // Extract signature bytes (remove "ed25519:" prefix)
    let sig_hex = if envelope.signature.starts_with("ed25519:") {
        &envelope.signature[9..]
    } else {
        &envelope.signature
    };

    let ipc_msg = IPCMessage {
        agent_id,
        message_type: map_a2a_type_to_ipc(&envelope.message.msg_type),
        payload: envelope.message.payload.clone(),
        timestamp: envelope.message.timestamp,
        signature: sig_hex.to_string(),
    };

    Ok(ipc_msg)
}

/// Map IPC message types to A2A protocol types
fn map_ipc_type_to_a2a(ipc_type: &siss_a2a_ipc::MessageType) -> MessageType {
    match ipc_type {
        siss_a2a_ipc::MessageType::PlannerToCompliance => MessageType::TaskIntent,
        siss_a2a_ipc::MessageType::ComplianceToEvidence => MessageType::ComplianceVeto,
        siss_a2a_ipc::MessageType::EvidenceToLedger => MessageType::LedgerCommit,
        siss_a2a_ipc::MessageType::HealthCheck => MessageType::DiscoveryRequest,
        siss_a2a_ipc::MessageType::Ack => MessageType::HandoffAccept,
        siss_a2a_ipc::MessageType::Nack => MessageType::HandoffAbort,
    }
}

/// Map A2A protocol types back to IPC types
fn map_a2a_type_to_ipc(a2a_type: &MessageType) -> siss_a2a_ipc::MessageType {
    match a2a_type {
        MessageType::TaskIntent => siss_a2a_ipc::MessageType::PlannerToCompliance,
        MessageType::ComplianceVeto => siss_a2a_ipc::MessageType::ComplianceToEvidence,
        MessageType::TaskAck => siss_a2a_ipc::MessageType::Ack,
        MessageType::TaskCompletion => siss_a2a_ipc::MessageType::Ack,
        MessageType::DiscoveryRequest => siss_a2a_ipc::MessageType::HealthCheck,
        MessageType::DiscoveryResponse => siss_a2a_ipc::MessageType::Ack,
        MessageType::HandoffRequest => siss_a2a_ipc::MessageType::HealthCheck,
        MessageType::HandoffAccept => siss_a2a_ipc::MessageType::Ack,
        MessageType::HandoffAbort => siss_a2a_ipc::MessageType::Nack,
        MessageType::LedgerCommit => siss_a2a_ipc::MessageType::EvidenceToLedger,
        MessageType::Error => siss_a2a_ipc::MessageType::Nack,
    }
}

/// Agent registry: maps agent IDs to their manifests and public keys
#[derive(Debug, Clone)]
pub struct AgentRegistry {
    agents: Arc<std::sync::Mutex<HashMap<String, RegisteredAgent>>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RegisteredAgent {
    pub agent_id: String,
    pub manifest: PeerManifest,
    pub pubkey_hex: String,
}

impl AgentRegistry {
    /// Create new registry
    pub fn new() -> Self {
        AgentRegistry {
            agents: Arc::new(std::sync::Mutex::new(HashMap::new())),
        }
    }

    /// Register agent (called during agent startup)
    pub fn register(&self, agent_id: String, manifest: PeerManifest, pubkey_hex: String) -> Result<()> {
        let mut agents = self
            .agents
            .lock()
            .map_err(|e| A2AError::InternalError(format!("Mutex poisoned: {}", e)))?;

        agents.insert(
            agent_id.clone(),
            RegisteredAgent {
                agent_id,
                manifest,
                pubkey_hex,
            },
        );

        Ok(())
    }

    /// Get agent by ID
    pub fn get(&self, agent_id: &str) -> Result<RegisteredAgent> {
        let agents = self
            .agents
            .lock()
            .map_err(|e| A2AError::InternalError(format!("Mutex poisoned: {}", e)))?;

        agents
            .get(agent_id)
            .cloned()
            .ok_or_else(|| A2AError::PeerNotFound(agent_id.to_string()))
    }

    /// List all registered agents
    pub fn list(&self) -> Result<Vec<RegisteredAgent>> {
        let agents = self
            .agents
            .lock()
            .map_err(|e| A2AError::InternalError(format!("Mutex poisoned: {}", e)))?;

        Ok(agents.values().cloned().collect())
    }

    /// Verify envelope signature using registered agent's pubkey
    pub fn verify_signature(&self, envelope: &A2AEnvelope) -> Result<bool> {
        let agent = self.get(&envelope.message.from_agent)?;

        // Compare registered pubkey with envelope signer pubkey
        if agent.pubkey_hex != envelope.signer_pubkey {
            return Err(A2AError::SignatureVerificationFailed);
        }

        // Verify signature using protocol method
        envelope.verify_signature()
            .map_err(|e| A2AError::CryptoError(e.to_string()))
    }
}

impl Default for AgentRegistry {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;

    #[test]
    fn test_ipc_to_a2a_conversion() {
        let ipc_msg = IPCMessage {
            agent_id: Uuid::new_v4(),
            message_type: siss_a2a_ipc::MessageType::PlannerToCompliance,
            payload: serde_json::json!({"test": "data"}),
            timestamp: Utc::now(),
            signature: "abc123def456".to_string(),
        };

        let envelope = ipc_to_a2a(&ipc_msg, "pubkey123".to_string()).expect("convert");
        assert_eq!(envelope.message.msg_type, MessageType::TaskIntent);
        assert!(envelope.signature.starts_with("ed25519:"));
    }

    #[test]
    fn test_agent_registry() {
        let registry = AgentRegistry::new();
        let manifest = PeerManifest {
            agent_id: "agent-1".to_string(),
            uri: "http://localhost:9000".to_string(),
            pubkey: "key123".to_string(),
            capabilities: vec![],
            updated_at: Utc::now(),
            ttl_secs: 3600,
            cert_chain: None,
        };

        registry
            .register("agent-1".to_string(), manifest.clone(), "key123".to_string())
            .expect("register");

        let agent = registry.get("agent-1").expect("get");
        assert_eq!(agent.agent_id, "agent-1");
    }

    #[test]
    fn test_message_type_roundtrip() {
        let ipc_type = siss_a2a_ipc::MessageType::ComplianceToEvidence;
        let a2a_type = map_ipc_type_to_a2a(&ipc_type);
        let ipc_type_back = map_a2a_type_to_ipc(&a2a_type);

        assert_eq!(ipc_type, ipc_type_back);
    }
}
