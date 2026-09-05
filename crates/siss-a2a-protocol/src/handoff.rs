use chrono::{DateTime, Utc};
use ed25519_dalek::{SigningKey, VerifyingKey, Signer};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::HashSet;
use uuid::Uuid;

use crate::protocol::{A2AEnvelope, A2AMessage};
use crate::integration::AgentRegistry;

/// Task state snapshot for handoff
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskState {
    /// Task ID
    pub task_id: String,
    /// Intent payload (JSON)
    pub intent: serde_json::Value,
    /// Partial execution trace
    pub trace: Vec<TraceEntry>,
    /// Current execution checkpoint (for resumption)
    pub checkpoint: Option<String>,
    /// Serialized context from pgvector (L2 knowledge)
    pub context_vector: Option<Vec<f32>>,
    /// pgvector embedding for semantic retrieval
    pub pgvector_embedding: Option<Vec<f32>>,
    /// Source agent public key (Ed25519, hex-encoded)
    pub source_agent_pubkey: String,
    /// SHA256 checkpoint hash for recovery validation
    pub checkpoint_hash: String,
    /// Timestamp of state capture
    pub captured_at: DateTime<Utc>,
}

impl TaskState {
    /// Create new task state
    pub fn new(task_id: String, intent: serde_json::Value) -> Self {
        TaskState {
            task_id,
            intent,
            trace: vec![],
            checkpoint: None,
            context_vector: None,
            pgvector_embedding: None,
            source_agent_pubkey: String::new(),
            checkpoint_hash: String::new(),
            captured_at: Utc::now(),
        }
    }

    /// Create task state with full parameters (for handoff)
    pub fn with_source(
        task_id: String,
        intent: serde_json::Value,
        source_agent_pubkey: String,
        checkpoint_hash: String,
    ) -> Self {
        TaskState {
            task_id,
            intent,
            trace: vec![],
            checkpoint: None,
            context_vector: None,
            pgvector_embedding: None,
            source_agent_pubkey,
            checkpoint_hash,
            captured_at: Utc::now(),
        }
    }

    /// Serialize state to bytes (for storage/transmission)
    pub fn to_bytes(&self) -> anyhow::Result<Vec<u8>> {
        Ok(serde_json::to_vec(self)?)
    }

    /// Deserialize state from bytes
    pub fn from_bytes(bytes: &[u8]) -> anyhow::Result<Self> {
        Ok(serde_json::from_slice(bytes)?)
    }

    /// Compute SHA256 digest for ledger anchoring
    pub fn digest(&self) -> anyhow::Result<String> {
        let bytes = self.to_bytes()?;
        let mut hasher = Sha256::new();
        hasher.update(&bytes);
        Ok(format!("{:x}", hasher.finalize()))
    }

    /// Add trace entry
    pub fn add_trace(&mut self, entry: TraceEntry) {
        self.trace.push(entry);
    }
}

/// Execution trace entry
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TraceEntry {
    /// Trace step ID
    pub id: String,
    /// Agent that performed step
    pub agent: String,
    /// Action description
    pub action: String,
    /// Timestamp
    pub timestamp: DateTime<Utc>,
    /// Result (success/error)
    pub result: String,
}

impl TraceEntry {
    /// Create new trace entry
    pub fn new(agent: String, action: String, result: String) -> Self {
        TraceEntry {
            id: Uuid::new_v4().to_string(),
            agent,
            action,
            timestamp: Utc::now(),
            result,
        }
    }
}

/// Handoff result with acceptance/rejection
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HandoffResult {
    /// Handoff ID
    pub id: String,
    /// Source agent ID
    pub source_agent: String,
    /// Target agent ID
    pub target_agent: String,
    /// Handoff accepted?
    pub accepted: bool,
    /// Rejection reason (if any)
    pub rejection_reason: Option<String>,
    /// Timestamp
    pub timestamp: DateTime<Utc>,
}

/// Handoff validation result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HandoffValidation {
    /// Is handoff valid?
    pub is_valid: bool,
    /// Validation reason/error message
    pub reason: String,
}

/// Cryptographic handoff manager
pub struct CryptographicHandoff {
    /// Ed25519 signing key for this agent
    signing_key: SigningKey,
    /// Agent's public key (derived)
    verifying_key: VerifyingKey,
    /// Agent ID
    agent_id: String,
}

impl CryptographicHandoff {
    /// Create handoff manager with new key pair
    pub fn new(agent_id: String) -> anyhow::Result<Self> {
        let mut seed = [0u8; 32];
        use rand::RngCore;
        rand::thread_rng().fill_bytes(&mut seed);
        let signing_key = SigningKey::from_bytes(&seed);
        let verifying_key = signing_key.verifying_key();

        Ok(CryptographicHandoff {
            signing_key,
            verifying_key,
            agent_id,
        })
    }

    /// Create handoff manager from stored key (from siss-vault-integration)
    pub fn from_key(agent_id: String, key_bytes: &[u8]) -> anyhow::Result<Self> {
        let signing_key = SigningKey::from_bytes(&key_bytes.try_into()?);
        let verifying_key = signing_key.verifying_key();

        Ok(CryptographicHandoff {
            signing_key,
            verifying_key,
            agent_id,
        })
    }

    /// Get agent's public key (hex-encoded)
    pub fn public_key(&self) -> String {
        hex::encode(self.verifying_key.to_bytes())
    }

    /// Sign A2A message envelope
    pub fn sign_envelope(&self, mut envelope: A2AEnvelope) -> anyhow::Result<A2AEnvelope> {
        let message_bytes = envelope.message.to_cbor()?;
        let signature = self.signing_key.sign(&message_bytes);

        envelope.signature = format!("ed25519:{}", hex::encode(signature.to_bytes()));
        envelope.signer_pubkey = self.public_key();

        Ok(envelope)
    }

    /// Prepare handoff: sign task state for transmission
    pub fn prepare_handoff(
        &self,
        target_agent: String,
        task_state: TaskState,
    ) -> anyhow::Result<A2AEnvelope> {
        let state_bytes = task_state.to_bytes()?;
        let state_digest = task_state.digest()?;

        let payload = serde_json::json!({
            "task_id": task_state.task_id,
            "state_digest": state_digest,
            "state_size": state_bytes.len(),
        });

        let msg = A2AMessage::new(
            crate::protocol::MessageType::HandoffRequest,
            self.agent_id.clone(),
            Some(target_agent),
            payload,
        );

        let envelope = A2AEnvelope::new(msg);
        self.sign_envelope(envelope)
    }

    /// Verify received envelope
    pub fn verify_envelope(&self, envelope: &A2AEnvelope) -> anyhow::Result<bool> {
        envelope.verify_signature()
    }

    /// Accept handoff: sign acceptance acknowledgment
    pub fn accept_handoff(
        &self,
        source_agent: String,
        task_id: String,
    ) -> anyhow::Result<A2AEnvelope> {
        let payload = serde_json::json!({
            "task_id": task_id,
            "status": "accepted",
        });

        let msg = A2AMessage::new(
            crate::protocol::MessageType::HandoffAccept,
            self.agent_id.clone(),
            Some(source_agent),
            payload,
        );

        let envelope = A2AEnvelope::new(msg);
        self.sign_envelope(envelope)
    }

    /// Reject handoff with reason
    pub fn reject_handoff(
        &self,
        source_agent: String,
        task_id: String,
        reason: String,
    ) -> anyhow::Result<A2AEnvelope> {
        let payload = serde_json::json!({
            "task_id": task_id,
            "status": "rejected",
            "reason": reason,
        });

        let msg = A2AMessage::new(
            crate::protocol::MessageType::HandoffAbort,
            self.agent_id.clone(),
            Some(source_agent),
            payload,
        );

        let envelope = A2AEnvelope::new(msg);
        self.sign_envelope(envelope)
    }

    /// Validate handoff: check source agent pubkey, target agent capability, cycle detection
    pub fn validate_handoff(
        &self,
        registry: &AgentRegistry,
        state: &TaskState,
        target_agent: &str,
        required_capability: &str,
    ) -> anyhow::Result<HandoffValidation> {
        // Check 1: Source agent pubkey matches registry
        let source_agent = registry.get(&self.agent_id).ok();
        if let Some(agent) = source_agent {
            if agent.pubkey_hex != state.source_agent_pubkey {
                return Ok(HandoffValidation {
                    is_valid: false,
                    reason: "Source agent pubkey mismatch with registry".to_string(),
                });
            }
        }

        // Check 2: Target agent exists in registry
        let target = match registry.get(target_agent) {
            Ok(agent) => agent,
            Err(_) => {
                return Ok(HandoffValidation {
                    is_valid: false,
                    reason: format!("Target agent '{}' not found in registry", target_agent),
                });
            }
        };

        // Check 3: Target agent has required capability
        if !target.manifest.has_capability(required_capability) {
            return Ok(HandoffValidation {
                is_valid: false,
                reason: format!(
                    "Target agent lacks required capability: {}",
                    required_capability
                ),
            });
        }

        // Check 4: Cycle detection via trace analysis (DAG validation)
        let mut agents_in_trace = HashSet::new();
        for entry in &state.trace {
            agents_in_trace.insert(entry.agent.clone());
        }

        if agents_in_trace.contains(target_agent) {
            // Task already processed by target agent - potential cycle
            return Ok(HandoffValidation {
                is_valid: false,
                reason: format!(
                    "Cycle detected: target agent '{}' already in trace",
                    target_agent
                ),
            });
        }

        Ok(HandoffValidation {
            is_valid: true,
            reason: "Handoff validation passed".to_string(),
        })
    }

    /// Prepare task state for pgvector storage (serialize + digest, no embedding yet)
    pub fn prepare_for_pgvector(&self, state: &TaskState) -> anyhow::Result<(Vec<u8>, String)> {
        let state_bytes = state.to_bytes()?;
        let digest = state.digest()?;

        Ok((state_bytes, digest))
    }

    /// Sign state transfer: create cryptographic proof of handoff authorization
    pub fn sign_state_transfer(&self, state: &TaskState) -> anyhow::Result<String> {
        let digest = state.digest()?;
        let digest_bytes = digest.as_bytes();

        let signature = self.signing_key.sign(digest_bytes);
        Ok(format!("ed25519:{}", hex::encode(signature.to_bytes())))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::discovery::{PeerManifest, PeerCapability};

    #[test]
    fn test_task_state_creation() {
        let intent = serde_json::json!({"action": "classify"});
        let state = TaskState::new("task-123".to_string(), intent);
        assert_eq!(state.task_id, "task-123");
        assert_eq!(state.trace.len(), 0);
    }

    #[test]
    fn test_task_state_serialization() {
        let intent = serde_json::json!({"test": "data"});
        let state = TaskState::new("task-456".to_string(), intent);
        let bytes = state.to_bytes().expect("serialize");
        let restored = TaskState::from_bytes(&bytes).expect("deserialize");
        assert_eq!(restored.task_id, "task-456");
    }

    #[test]
    fn test_state_serialization_with_source() {
        let intent = serde_json::json!({"amount": 100});
        let state = TaskState::with_source(
            "task-789".to_string(),
            intent,
            "agent1pubkey123".to_string(),
            "checkpoint_hash_123".to_string(),
        );
        let bytes = state.to_bytes().expect("serialize");
        let restored = TaskState::from_bytes(&bytes).expect("deserialize");
        assert_eq!(restored.task_id, "task-789");
        assert_eq!(restored.source_agent_pubkey, "agent1pubkey123");
        assert_eq!(restored.checkpoint_hash, "checkpoint_hash_123");
    }

    #[test]
    fn test_handoff_manager_creation() {
        let handoff = CryptographicHandoff::new("agent-1".to_string()).expect("create");
        let pubkey = handoff.public_key();
        assert!(!pubkey.is_empty());
        assert_eq!(pubkey.len(), 128); // 64 bytes = 128 hex chars
    }

    #[test]
    fn test_envelope_signing() {
        let handoff = CryptographicHandoff::new("agent-1".to_string()).expect("create");
        let payload = serde_json::json!({"test": "payload"});
        let msg = A2AMessage::new(
            crate::protocol::MessageType::TaskIntent,
            "agent-1".to_string(),
            Some("agent-2".to_string()),
            payload,
        );

        let envelope = A2AEnvelope::new(msg);
        let signed = handoff.sign_envelope(envelope).expect("sign");
        assert!(!signed.signature.is_empty());
        assert!(signed.signature.starts_with("ed25519:"));
    }

    #[test]
    fn test_trace_entry() {
        let entry = TraceEntry::new(
            "agent-1".to_string(),
            "classify".to_string(),
            "success".to_string(),
        );
        assert_eq!(entry.agent, "agent-1");
        assert_eq!(entry.action, "classify");
    }

    #[test]
    fn test_valid_handoff() {
        let registry = AgentRegistry::new();
        let pubkey1 = "11111111111111111111111111111111";
        let pubkey2 = "22222222222222222222222222222222";

        let manifest1 = PeerManifest {
            agent_id: "agent-1".to_string(),
            uri: "http://localhost:9001".to_string(),
            pubkey: pubkey1.to_string(),
            capabilities: vec![PeerCapability {
                name: "task-execution".to_string(),
                version: "1.0".to_string(),
                available: true,
            }],
            updated_at: Utc::now(),
            ttl_secs: 3600,
            cert_chain: None,
        };

        let manifest2 = PeerManifest {
            agent_id: "agent-2".to_string(),
            uri: "http://localhost:9002".to_string(),
            pubkey: pubkey2.to_string(),
            capabilities: vec![PeerCapability {
                name: "task-execution".to_string(),
                version: "1.0".to_string(),
                available: true,
            }],
            updated_at: Utc::now(),
            ttl_secs: 3600,
            cert_chain: None,
        };

        registry
            .register("agent-1".to_string(), manifest1, pubkey1.to_string())
            .expect("register agent-1");
        registry
            .register("agent-2".to_string(), manifest2, pubkey2.to_string())
            .expect("register agent-2");

        let handoff = CryptographicHandoff::new("agent-1".to_string()).expect("create handoff");
        let state = TaskState::with_source(
            "task-001".to_string(),
            serde_json::json!({"action": "classify"}),
            pubkey1.to_string(),
            "checkpoint_hash_abc".to_string(),
        );

        let validation = handoff
            .validate_handoff(&registry, &state, "agent-2", "task-execution")
            .expect("validate");
        assert!(validation.is_valid);
        assert_eq!(validation.reason, "Handoff validation passed");
    }

    #[test]
    fn test_unknown_target() {
        let registry = AgentRegistry::new();
        let pubkey1 = "11111111111111111111111111111111";

        let manifest1 = PeerManifest {
            agent_id: "agent-1".to_string(),
            uri: "http://localhost:9001".to_string(),
            pubkey: pubkey1.to_string(),
            capabilities: vec![],
            updated_at: Utc::now(),
            ttl_secs: 3600,
            cert_chain: None,
        };

        registry
            .register("agent-1".to_string(), manifest1, pubkey1.to_string())
            .expect("register");

        let handoff = CryptographicHandoff::new("agent-1".to_string()).expect("create");
        let state = TaskState::with_source(
            "task-002".to_string(),
            serde_json::json!({"action": "classify"}),
            pubkey1.to_string(),
            "checkpoint_hash_def".to_string(),
        );

        let validation = handoff
            .validate_handoff(&registry, &state, "agent-unknown", "task-execution")
            .expect("validate");
        assert!(!validation.is_valid);
        assert!(validation.reason.contains("not found in registry"));
    }

    #[test]
    fn test_cycle_detection() {
        let registry = AgentRegistry::new();
        let pubkey1 = "11111111111111111111111111111111";
        let pubkey2 = "22222222222222222222222222222222";

        let manifest1 = PeerManifest {
            agent_id: "agent-1".to_string(),
            uri: "http://localhost:9001".to_string(),
            pubkey: pubkey1.to_string(),
            capabilities: vec![PeerCapability {
                name: "task-execution".to_string(),
                version: "1.0".to_string(),
                available: true,
            }],
            updated_at: Utc::now(),
            ttl_secs: 3600,
            cert_chain: None,
        };

        let manifest2 = PeerManifest {
            agent_id: "agent-2".to_string(),
            uri: "http://localhost:9002".to_string(),
            pubkey: pubkey2.to_string(),
            capabilities: vec![PeerCapability {
                name: "task-execution".to_string(),
                version: "1.0".to_string(),
                available: true,
            }],
            updated_at: Utc::now(),
            ttl_secs: 3600,
            cert_chain: None,
        };

        registry
            .register("agent-1".to_string(), manifest1, pubkey1.to_string())
            .expect("register");
        registry
            .register("agent-2".to_string(), manifest2, pubkey2.to_string())
            .expect("register");

        let handoff = CryptographicHandoff::new("agent-1".to_string()).expect("create");
        let mut state = TaskState::with_source(
            "task-003".to_string(),
            serde_json::json!({"action": "classify"}),
            pubkey1.to_string(),
            "checkpoint_hash_ghi".to_string(),
        );

        // Add trace entry with agent-2 (cycle)
        state.add_trace(TraceEntry::new(
            "agent-2".to_string(),
            "classify".to_string(),
            "success".to_string(),
        ));

        let validation = handoff
            .validate_handoff(&registry, &state, "agent-2", "task-execution")
            .expect("validate");
        assert!(!validation.is_valid);
        assert!(validation.reason.contains("Cycle detected"));
    }

    #[test]
    fn test_sign_state_transfer() {
        let handoff = CryptographicHandoff::new("agent-1".to_string()).expect("create");
        let state = TaskState::with_source(
            "task-004".to_string(),
            serde_json::json!({"action": "verify"}),
            "pubkey_hex".to_string(),
            "checkpoint_hash_jkl".to_string(),
        );

        let signature = handoff
            .sign_state_transfer(&state)
            .expect("sign state transfer");
        assert!(!signature.is_empty());
        assert!(signature.starts_with("ed25519:"));
        assert!(signature.len() > 20); // Reasonable signature length
    }

    #[test]
    fn test_prepare_for_pgvector() {
        let handoff = CryptographicHandoff::new("agent-1".to_string()).expect("create");
        let state = TaskState::with_source(
            "task-005".to_string(),
            serde_json::json!({"amount": 500, "currency": "USD"}),
            "pubkey_hex".to_string(),
            "checkpoint_hash_mno".to_string(),
        );

        let (bytes, digest) = handoff
            .prepare_for_pgvector(&state)
            .expect("prepare for pgvector");
        assert!(!bytes.is_empty());
        assert!(!digest.is_empty());
        assert_eq!(digest.len(), 64); // SHA256 hex is 64 chars
    }
}
