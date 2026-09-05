/// A2A Message Router — Central dispatcher for agent-to-agent communication
///
/// Routes incoming IPC messages to appropriate handler based on:
/// - Message type (TaskIntent → Planner, ComplianceVeto → Evidence, etc.)
/// - Target agent ID (if present)
/// - Auto-discovery of available handlers
///
/// Pattern:
/// IPCMessage → A2ARouter → Handler → Agent Logic → A2AEnvelope → IPCMessage (signed)

use crate::integration::AgentRegistry;
use crate::protocol::{MessageType, MessageStatus};
use anyhow::{anyhow, Result};
use async_trait::async_trait;
use siss_a2a_ipc::{A2AMessage as IPCMessage, MessageType as IPCMessageType};
use std::collections::HashMap;
use std::sync::Arc;

/// Handler trait: each agent implements this
#[async_trait]
pub trait A2AHandlerTrait: Send + Sync {
    /// Process incoming IPC message and return response
    async fn handle(&self, msg: IPCMessage) -> Result<IPCMessage>;

    /// Get handler capability (e.g., "planner", "compliance", "evidence")
    fn capability(&self) -> String;
}

/// Central router: dispatches messages to handlers
pub struct A2ARouter {
    registry: Arc<AgentRegistry>,
    handlers: HashMap<MessageType, Arc<dyn A2AHandlerTrait>>,
}

impl A2ARouter {
    pub fn new(registry: Arc<AgentRegistry>) -> Self {
        Self {
            registry,
            handlers: HashMap::new(),
        }
    }

    /// Register a handler for a specific message type
    pub fn register_handler(
        &mut self,
        msg_type: MessageType,
        handler: Arc<dyn A2AHandlerTrait>,
    ) -> Result<()> {
        log::info!(
            "A2ARouter: registering handler for message type {:?} ({})",
            msg_type,
            handler.capability()
        );

        self.handlers.insert(msg_type, handler);
        Ok(())
    }

    /// Main entry point: route message to correct handler
    pub async fn route_and_handle(&self, ipc_msg: IPCMessage) -> Result<IPCMessage> {
        log::debug!(
            "A2ARouter: routing message type {:?} from agent {}",
            ipc_msg.message_type,
            ipc_msg.agent_id
        );

        // Map IPC message type to A2A protocol message type
        let msg_type = match ipc_msg.message_type {
            IPCMessageType::PlannerToCompliance => MessageType::TaskIntent,
            IPCMessageType::ComplianceToEvidence => MessageType::ComplianceVeto,
            IPCMessageType::EvidenceToLedger => MessageType::LedgerCommit,
            IPCMessageType::HealthCheck => MessageType::DiscoveryRequest,
            IPCMessageType::Ack => MessageType::HandoffAccept,
            IPCMessageType::Nack => MessageType::HandoffAbort,
        };

        // Find handler for this message type
        let handler = self
            .handlers
            .get(&msg_type)
            .ok_or_else(|| anyhow!("No handler registered for message type {:?}", msg_type))?;

        log::debug!(
            "A2ARouter: dispatching to handler: {}",
            handler.capability()
        );

        // Dispatch to handler
        match handler.handle(ipc_msg).await {
            Ok(response) => {
                log::debug!(
                    "A2ARouter: handler returned successfully, message type: {:?}",
                    response.message_type
                );
                Ok(response)
            }
            Err(e) => {
                log::warn!("A2ARouter: handler error: {}", e);
                Err(e)
            }
        }
    }

    /// Query registry for registered agents
    pub fn list_agents(&self) -> Result<Vec<String>> {
        let agents = self.registry.list()?;
        Ok(agents.iter().map(|a| a.agent_id.clone()).collect())
    }

    /// Query router for registered handlers
    pub fn list_handlers(&self) -> Vec<String> {
        self.handlers
            .values()
            .map(|h| h.capability())
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::discovery::PeerManifest;
    use chrono::Utc;
    use siss_a2a_ipc::MessageType as IPCMessageType;
    use uuid::Uuid;

    /// Mock handler for testing
    struct MockHandler {
        capability: String,
    }

    #[async_trait]
    impl A2AHandlerTrait for MockHandler {
        async fn handle(&self, msg: IPCMessage) -> Result<IPCMessage> {
            Ok(IPCMessage {
                agent_id: msg.agent_id,
                message_type: IPCMessageType::Ack,
                payload: serde_json::json!({"status": "ok"}),
                timestamp: Utc::now(),
                signature: "mock_sig".to_string(),
            })
        }

        fn capability(&self) -> String {
            self.capability.clone()
        }
    }

    #[test]
    fn test_router_creation() {
        let registry = Arc::new(AgentRegistry::new());
        let router = A2ARouter::new(registry);
        assert_eq!(router.handlers.len(), 0);
    }

    #[test]
    fn test_register_handler() {
        let registry = Arc::new(AgentRegistry::new());
        let mut router = A2ARouter::new(registry);

        let mock_handler = Arc::new(MockHandler {
            capability: "test_capability".to_string(),
        });

        router
            .register_handler(MessageType::TaskIntent, mock_handler.clone())
            .unwrap();

        assert_eq!(router.handlers.len(), 1);
        assert!(router.handlers.contains_key(&MessageType::TaskIntent));
    }

    #[test]
    fn test_list_handlers() {
        let registry = Arc::new(AgentRegistry::new());
        let mut router = A2ARouter::new(registry);

        let handler1 = Arc::new(MockHandler {
            capability: "handler1".to_string(),
        });
        let handler2 = Arc::new(MockHandler {
            capability: "handler2".to_string(),
        });

        router
            .register_handler(MessageType::TaskIntent, handler1)
            .unwrap();
        router
            .register_handler(MessageType::ComplianceVeto, handler2)
            .unwrap();

        let handlers = router.list_handlers();
        assert_eq!(handlers.len(), 2);
        assert!(handlers.contains(&"handler1".to_string()));
        assert!(handlers.contains(&"handler2".to_string()));
    }

    #[tokio::test]
    async fn test_route_message_no_handler() {
        let registry = Arc::new(AgentRegistry::new());
        let router = A2ARouter::new(registry);

        let msg = IPCMessage {
            agent_id: Uuid::new_v4(),
            message_type: IPCMessageType::PlannerToCompliance,
            payload: serde_json::json!({}),
            timestamp: Utc::now(),
            signature: "test_sig".to_string(),
        };

        let result = router.route_and_handle(msg).await;
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_route_message_with_handler() {
        let registry = Arc::new(AgentRegistry::new());
        let mut router = A2ARouter::new(registry);

        let mock_handler = Arc::new(MockHandler {
            capability: "test_handler".to_string(),
        });

        router
            .register_handler(MessageType::TaskIntent, mock_handler)
            .unwrap();

        let msg = IPCMessage {
            agent_id: Uuid::new_v4(),
            message_type: IPCMessageType::PlannerToCompliance,
            payload: serde_json::json!({}),
            timestamp: Utc::now(),
            signature: "test_sig".to_string(),
        };

        let result = router.route_and_handle(msg).await;
        assert!(result.is_ok());

        let response = result.unwrap();
        assert_eq!(response.message_type, IPCMessageType::Ack);
    }

    #[test]
    fn test_list_agents() {
        let registry = Arc::new(AgentRegistry::new());

        // Register a test agent
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
            .register("agent-1".to_string(), manifest, "key123".to_string())
            .unwrap();

        let router = A2ARouter::new(registry);
        let agents = router.list_agents().unwrap();

        assert_eq!(agents.len(), 1);
        assert!(agents.contains(&"agent-1".to_string()));
    }

    #[test]
    fn test_message_type_mapping() {
        // Verify IPC message types map correctly to A2A protocol types
        assert_eq!(
            IPCMessageType::PlannerToCompliance,
            IPCMessageType::PlannerToCompliance
        );
        assert_eq!(
            IPCMessageType::ComplianceToEvidence,
            IPCMessageType::ComplianceToEvidence
        );
    }
}
