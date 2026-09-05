/// Phase 40: MCP-A2A Bridge — Protocol Adaptation Layer
/// Marshals A2A messages into MCP protocol for cross-network routing.

use base64::engine::{general_purpose, Engine as _};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use siss_swarm_coordinator::A2AMessage;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RoutingMetadata {
    pub hop_count: u8,
    pub max_hops: u8,
    pub slice_id: Option<Uuid>,
    pub priority: u8,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct A2AMessageMarshalled {
    pub message_id: Uuid,
    pub from_agent_id: Uuid,
    pub to_agent_id: Uuid,
    pub payload_base64: String,
    pub timestamp: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct McpEnvelope {
    pub envelope_id: Uuid,
    pub protocol_version: String,
    pub a2a_message_inner: A2AMessageMarshalled,
    pub routing_metadata: RoutingMetadata,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BridgeError {
    MarshallingFailed,
    UnmarshallingFailed,
    RoutingFailed,
    HopLimitExceeded,
}

pub struct McpA2ABridge {
    max_hops: u8,
    protocol_version: String,
}

impl McpA2ABridge {
    pub fn new(max_hops: u8) -> Self {
        Self {
            max_hops,
            protocol_version: "mcp/1.0".to_string(),
        }
    }

    /// Marshal A2A message to MCP envelope
    pub fn marshal_to_mcp(
        &self,
        msg: &A2AMessage,
        slice_id: Option<Uuid>,
        priority: u8,
    ) -> Result<McpEnvelope, BridgeError> {
        // Encode payload as base64
        let payload_base64 = general_purpose::STANDARD.encode(msg.payload.as_bytes());

        let marshalled = A2AMessageMarshalled {
            message_id: msg.message_id,
            from_agent_id: msg.from_agent_id,
            to_agent_id: msg.to_agent_id,
            payload_base64,
            timestamp: msg.timestamp,
        };

        let envelope = McpEnvelope {
            envelope_id: Uuid::new_v4(),
            protocol_version: self.protocol_version.clone(),
            a2a_message_inner: marshalled,
            routing_metadata: RoutingMetadata {
                hop_count: 0,
                max_hops: self.max_hops,
                slice_id,
                priority,
            },
        };

        Ok(envelope)
    }

    /// Unmarshal MCP envelope back to A2A message
    pub fn unmarshal_from_mcp(&self, envelope: &McpEnvelope) -> Result<A2AMessage, BridgeError> {
        let payload = general_purpose::STANDARD.decode(&envelope.a2a_message_inner.payload_base64)
            .map_err(|_| BridgeError::UnmarshallingFailed)?;

        let payload_str = String::from_utf8(payload)
            .map_err(|_| BridgeError::UnmarshallingFailed)?;

        Ok(A2AMessage::new(
            envelope.a2a_message_inner.from_agent_id,
            envelope.a2a_message_inner.to_agent_id,
            payload_str,
        ))
    }

    /// Route envelope with hop limit check
    pub fn route_with_hop_check(&self, envelope: &mut McpEnvelope) -> Result<(), BridgeError> {
        envelope.routing_metadata.hop_count += 1;

        if envelope.routing_metadata.hop_count > envelope.routing_metadata.max_hops {
            return Err(BridgeError::HopLimitExceeded);
        }

        Ok(())
    }
}

impl Default for McpA2ABridge {
    fn default() -> Self {
        Self::new(10)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_bridge() {
        let _bridge = McpA2ABridge::new(5);
    }
}
