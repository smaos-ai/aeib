/// A2A Handler for @Compliance Agent — Receives plans, evaluates policies, delegates to evidence
///
/// Processes incoming A2A messages from the message router:
/// - Convert IPCMessage → A2AEnvelope
/// - Validate signature via agent registry
/// - Route payload to compliance evaluation logic
/// - Respond with signed evaluation or veto

use crate::{ComplianceAgent, IncomingPlan};
use anyhow::Result;
use chrono::Utc;
use ed25519_dalek::Signer;
use siss_a2a_ipc::{A2AMessage as IPCMessage, MessageType as IPCMessageType};
use siss_a2a_protocol::{
    integration::{ipc_to_a2a, a2a_to_ipc, AgentRegistry},
    protocol::{A2AEnvelope, A2AMessage, MessageStatus, MessageType},
};
use std::sync::Arc;
use uuid::Uuid;

pub struct ComplianceA2AHandler {
    agent: Arc<ComplianceAgent>,
    registry: Arc<AgentRegistry>,
}

impl ComplianceA2AHandler {
    pub fn new(agent: Arc<ComplianceAgent>, registry: Arc<AgentRegistry>) -> Self {
        Self { agent, registry }
    }

    /// Main entry point: handle incoming A2A message
    pub async fn handle_incoming_message(&self, ipc_msg: IPCMessage) -> Result<IPCMessage> {
        log::debug!(
            "@Compliance A2A Handler: received message type {:?}",
            ipc_msg.message_type
        );

        // Step 1: Convert IPC message to A2AEnvelope
        let sender_id = ipc_msg.agent_id.to_string();
        let sender_agent = match self.registry.get(&sender_id) {
            Ok(agent) => agent,
            Err(_) => {
                log::warn!("Sender agent {} not in registry", sender_id);
                return self.create_error_response(
                    &ipc_msg,
                    MessageStatus::Unauthorized,
                    "Agent not registered",
                );
            }
        };

        let envelope = ipc_to_a2a(&ipc_msg, sender_agent.pubkey_hex.clone())?;

        // Step 2: Validate signature via registry
        if !self.registry.verify_signature(&envelope)? {
            log::warn!(
                "@Compliance A2A Handler: signature verification failed for message {}",
                envelope.message.id
            );
            return self.create_error_response(
                &ipc_msg,
                MessageStatus::Unauthorized,
                "Signature verification failed",
            );
        }

        // Step 3: Route to compliance logic based on message type
        let response_envelope = match envelope.message.msg_type {
            MessageType::TaskIntent => {
                self.handle_plan_evaluation(&envelope).await?
            }
            MessageType::DiscoveryRequest => {
                self.handle_discovery(&envelope).await?
            }
            _ => {
                log::warn!(
                    "@Compliance A2A Handler: unexpected message type {:?}",
                    envelope.message.msg_type
                );
                return self.create_error_response(
                    &ipc_msg,
                    MessageStatus::BadRequest,
                    "Unexpected message type for compliance",
                );
            }
        };

        // Step 4: Sign response and convert back to IPC format
        let signed_response = self.sign_envelope(response_envelope)?;
        let response_ipc = a2a_to_ipc(&signed_response, self.agent.agent_id)?;

        log::debug!(
            "@Compliance A2A Handler: sending response message type {:?}",
            response_ipc.message_type
        );

        Ok(response_ipc)
    }

    async fn handle_plan_evaluation(&self, envelope: &A2AEnvelope) -> Result<A2AEnvelope> {
        log::info!(
            "@Compliance A2A Handler: evaluating plan from {}",
            envelope.message.from_agent
        );

        // Parse incoming plan from payload
        let plan: IncomingPlan = serde_json::from_value(envelope.message.payload.clone())?;

        // Evaluate plan against compliance policies
        let evaluation = self.agent.evaluate_plan(&plan).await?;

        // Respond with evaluation result
        let response_msg = A2AMessage {
            id: Uuid::new_v4().to_string(),
            msg_type: MessageType::ComplianceVeto,
            status: MessageStatus::Success,
            from_agent: self.agent.agent_id.to_string(),
            to_agent: Some(envelope.message.from_agent.clone()),
            timestamp: Utc::now(),
            payload: serde_json::to_value(&evaluation)?,
            trace_id: envelope.message.trace_id.clone(),
            request_id: Some(envelope.message.id.clone()),
        };

        Ok(A2AEnvelope::new(response_msg))
    }

    async fn handle_discovery(&self, envelope: &A2AEnvelope) -> Result<A2AEnvelope> {
        log::debug!("@Compliance A2A Handler: responding to discovery request");

        let response_msg = A2AMessage {
            id: Uuid::new_v4().to_string(),
            msg_type: MessageType::DiscoveryResponse,
            status: MessageStatus::Success,
            from_agent: self.agent.agent_id.to_string(),
            to_agent: Some(envelope.message.from_agent.clone()),
            timestamp: Utc::now(),
            payload: serde_json::json!({
                "agent_id": self.agent.agent_id.to_string(),
                "agent_type": "compliance",
                "capabilities": ["policy_evaluation", "dry_run_execution", "veto_gating"]
            }),
            trace_id: envelope.message.trace_id.clone(),
            request_id: Some(envelope.message.id.clone()),
        };

        Ok(A2AEnvelope::new(response_msg))
    }

    fn sign_envelope(&self, mut envelope: A2AEnvelope) -> Result<A2AEnvelope> {
        let message_bytes = envelope.message.to_cbor()?;
        let signature = self.agent.signing_key.sign(&message_bytes);
        envelope.signature = hex::encode(signature.to_bytes());

        let verifying_key = self.agent.signing_key.verifying_key();
        envelope.signer_pubkey = hex::encode(verifying_key.to_bytes());

        Ok(envelope)
    }

    fn create_error_response(
        &self,
        incoming: &IPCMessage,
        status: MessageStatus,
        error_msg: &str,
    ) -> Result<IPCMessage> {
        let error_a2a = A2AMessage {
            id: Uuid::new_v4().to_string(),
            msg_type: MessageType::Error,
            status,
            from_agent: self.agent.agent_id.to_string(),
            to_agent: None,
            timestamp: Utc::now(),
            payload: serde_json::json!({ "error": error_msg }),
            trace_id: None,
            request_id: None,
        };

        let envelope = A2AEnvelope::new(error_a2a);
        let signed = self.sign_envelope(envelope)?;
        let response_ipc = a2a_to_ipc(&signed, self.agent.agent_id)?;

        Ok(response_ipc)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ed25519_dalek::SigningKey;

    fn create_test_signing_key() -> SigningKey {
        let secret_key_bytes = [42u8; 32];
        SigningKey::from_bytes(&secret_key_bytes)
    }

    #[tokio::test]
    async fn test_incoming_plan_evaluation() {
        let signing_key = create_test_signing_key();
        let agent = Arc::new(ComplianceAgent::new(signing_key));
        let registry = Arc::new(AgentRegistry::new());

        let handler = ComplianceA2AHandler::new(agent.clone(), registry.clone());

        // Create a test plan message
        let plan = IncomingPlan {
            plan_id: Uuid::new_v4(),
            intent_id: Uuid::new_v4(),
            mandated_steps: vec![],
            risk_assessment: serde_json::json!({}),
        };

        let ipc_msg = IPCMessage {
            agent_id: Uuid::new_v4(),
            message_type: IPCMessageType::PlannerToCompliance,
            payload: serde_json::to_value(&plan).unwrap(),
            timestamp: Utc::now(),
            signature: "test_sig".to_string(),
        };

        // Handler should return success with error response when sender not in registry
        let result = handler.handle_incoming_message(ipc_msg).await;
        assert!(result.is_ok());
        let response = result.unwrap();
        assert_eq!(response.message_type, IPCMessageType::Nack);
    }

    #[test]
    fn test_handler_creation() {
        let signing_key = create_test_signing_key();
        let agent = Arc::new(ComplianceAgent::new(signing_key));
        let registry = Arc::new(AgentRegistry::new());

        let handler = ComplianceA2AHandler::new(agent, registry);
        assert!(handler.agent.agent_id != Uuid::nil());
    }

    #[tokio::test]
    async fn test_discovery_response() {
        let signing_key = create_test_signing_key();
        let agent = Arc::new(ComplianceAgent::new(signing_key));
        let registry = Arc::new(AgentRegistry::new());

        let handler = ComplianceA2AHandler::new(agent, registry);

        // Create discovery request envelope
        let discovery_msg = A2AMessage::new(
            MessageType::DiscoveryRequest,
            "test_agent".to_string(),
            None,
            serde_json::json!({}),
        );
        let envelope = A2AEnvelope::new(discovery_msg);

        let response = handler.handle_discovery(&envelope).await;
        assert!(response.is_ok());

        let resp_env = response.unwrap();
        assert_eq!(resp_env.message.msg_type, MessageType::DiscoveryResponse);
    }
}
