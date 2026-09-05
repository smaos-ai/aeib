use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Message type discriminator for routing
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum MessageType {
    /// Task intent submission (planner -> compliance)
    TaskIntent,
    /// Compliance veto signal (compliance -> planner)
    ComplianceVeto,
    /// Task execution acknowledgment
    TaskAck,
    /// Task completion with proof
    TaskCompletion,
    /// Peer discovery request
    DiscoveryRequest,
    /// Peer manifest response
    DiscoveryResponse,
    /// Handoff request (source agent -> target agent)
    HandoffRequest,
    /// Handoff acceptance (target agent -> source agent)
    HandoffAccept,
    /// Handoff abort (target agent -> source agent)
    HandoffAbort,
    /// Ledger commit notification
    LedgerCommit,
    /// Error response
    Error,
}

/// Message status codes (compatible with REST semantics)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum MessageStatus {
    /// 200: Message processed successfully
    Success = 200,
    /// 202: Message accepted, processing async
    Accepted = 202,
    /// 400: Malformed message
    BadRequest = 400,
    /// 401: Signature verification failed
    Unauthorized = 401,
    /// 403: Task delegation denied (compliance gate)
    Forbidden = 403,
    /// 409: Handoff conflict (target already processing)
    Conflict = 409,
    /// 500: Peer internal error
    InternalError = 500,
    /// 503: Peer unavailable (retry later)
    ServiceUnavailable = 503,
}

/// Core A2A message payload (CBOR-serializable)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct A2AMessage {
    /// Message ID (UUID v4)
    pub id: String,
    /// Message type discriminator
    pub msg_type: MessageType,
    /// Status code (Success, Forbidden, etc.)
    pub status: MessageStatus,
    /// Source agent ID
    pub from_agent: String,
    /// Target agent ID (or broadcast if None)
    pub to_agent: Option<String>,
    /// Message timestamp (UTC)
    pub timestamp: DateTime<Utc>,
    /// Task intent or state payload (JSON)
    pub payload: serde_json::Value,
    /// Trace ID for distributed tracing
    pub trace_id: Option<String>,
    /// Request correlation (for RPC semantics)
    pub request_id: Option<String>,
}

impl A2AMessage {
    /// Create new message
    pub fn new(
        msg_type: MessageType,
        from_agent: String,
        to_agent: Option<String>,
        payload: serde_json::Value,
    ) -> Self {
        A2AMessage {
            id: Uuid::new_v4().to_string(),
            msg_type,
            status: MessageStatus::Success,
            from_agent,
            to_agent,
            timestamp: Utc::now(),
            payload,
            trace_id: None,
            request_id: None,
        }
    }

    /// Set trace ID for debugging
    pub fn with_trace(mut self, trace_id: String) -> Self {
        self.trace_id = Some(trace_id);
        self
    }

    /// Set request ID for RPC correlation
    pub fn with_request(mut self, request_id: String) -> Self {
        self.request_id = Some(request_id);
        self
    }

    /// Serialize to CBOR bytes (for cryptographic signing)
    pub fn to_cbor(&self) -> anyhow::Result<Vec<u8>> {
        // CBOR encoding: message without signature
        let json = serde_json::to_string(self)?;
        // For now, use JSON as CBOR transport (can be optimized to binary)
        Ok(json.into_bytes())
    }

    /// Deserialize from CBOR bytes
    pub fn from_cbor(bytes: &[u8]) -> anyhow::Result<Self> {
        let json_str = String::from_utf8(bytes.to_vec())?;
        Ok(serde_json::from_str(&json_str)?)
    }
}

/// Signed A2A message envelope
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct A2AEnvelope {
    /// Core message
    pub message: A2AMessage,
    /// Ed25519 signature (hex-encoded)
    pub signature: String,
    /// Signer's Ed25519 public key (hex-encoded)
    pub signer_pubkey: String,
    /// Previous message digest (for ledger chaining)
    pub prev_digest: Option<String>,
}

impl A2AEnvelope {
    /// Create unsigned envelope
    pub fn new(message: A2AMessage) -> Self {
        A2AEnvelope {
            message,
            signature: String::new(),
            signer_pubkey: String::new(),
            prev_digest: None,
        }
    }

    /// Verify signature against signer's public key
    pub fn verify_signature(&self) -> anyhow::Result<bool> {
        use ed25519_dalek::VerifyingKey;

        let pubkey_bytes = hex::decode(&self.signer_pubkey)?;
        let pubkey = VerifyingKey::from_bytes(&pubkey_bytes.as_slice().try_into()?)?;

        let message_bytes = self.message.to_cbor()?;

        // Strip "ed25519:" prefix if present (8 characters)
        let sig_hex = if self.signature.starts_with("ed25519:") {
            &self.signature[8..]
        } else {
            &self.signature
        };

        let signature_bytes = hex::decode(sig_hex)?;
        let signature_array: [u8; 64] = signature_bytes.as_slice().try_into()?;
        let signature = ed25519_dalek::Signature::from_bytes(&signature_array);

        match pubkey.verify_strict(&message_bytes, &signature) {
            Ok(_) => Ok(true),
            Err(_) => Ok(false),
        }
    }

    /// Serialize envelope to bytes
    pub fn to_bytes(&self) -> anyhow::Result<Vec<u8>> {
        Ok(serde_json::to_vec(self)?)
    }

    /// Deserialize envelope from bytes
    pub fn from_bytes(bytes: &[u8]) -> anyhow::Result<Self> {
        Ok(serde_json::from_slice(bytes)?)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_message_creation() {
        let payload = serde_json::json!({"intent": "classify"});
        let msg = A2AMessage::new(
            MessageType::TaskIntent,
            "planner-1".to_string(),
            Some("compliance-1".to_string()),
            payload,
        );
        assert_eq!(msg.msg_type, MessageType::TaskIntent);
        assert_eq!(msg.from_agent, "planner-1");
    }

    #[test]
    fn test_envelope_serialization() {
        let payload = serde_json::json!({"task": "test"});
        let msg = A2AMessage::new(
            MessageType::TaskIntent,
            "agent-1".to_string(),
            None,
            payload,
        );
        let envelope = A2AEnvelope::new(msg);
        let bytes = envelope.to_bytes().expect("serialize");
        let restored = A2AEnvelope::from_bytes(&bytes).expect("deserialize");
        assert_eq!(restored.message.from_agent, "agent-1");
    }

    #[test]
    fn test_message_status_codes() {
        assert_eq!(MessageStatus::Success as i32, 200);
        assert_eq!(MessageStatus::Forbidden as i32, 403);
        assert_eq!(MessageStatus::InternalError as i32, 500);
    }
}
