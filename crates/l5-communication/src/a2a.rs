use serde::{Deserialize, Serialize};
use uuid::Uuid;
use chrono::{DateTime, Utc};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct A2aMessage {
    pub message_id: String,
    pub sender_id: String,
    pub recipient_id: String,
    pub message_type: String,
    pub payload: serde_json::Value,
    pub timestamp: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Agent {
    pub id: String,
    pub name: String,
    pub role: String,
}

pub struct A2aRouter {
    agents: HashMap<String, Agent>,
    message_queue: Vec<A2aMessage>,
}

impl A2aRouter {
    pub fn new() -> Self {
        Self {
            agents: HashMap::new(),
            message_queue: Vec::new(),
        }
    }

    pub fn register_agent(&mut self, name: String, role: String) -> Agent {
        let agent = Agent {
            id: Uuid::new_v4().to_string(),
            name,
            role,
        };
        self.agents.insert(agent.id.clone(), agent.clone());
        agent
    }

    pub fn send_message(
        &mut self,
        sender_id: String,
        recipient_id: String,
        message_type: String,
        payload: serde_json::Value,
    ) -> Result<A2aMessage, String> {
        if !self.agents.contains_key(&sender_id) {
            return Err(format!("Sender not found: {}", sender_id));
        }
        if !self.agents.contains_key(&recipient_id) {
            return Err(format!("Recipient not found: {}", recipient_id));
        }

        let message = A2aMessage {
            message_id: Uuid::new_v4().to_string(),
            sender_id,
            recipient_id,
            message_type,
            payload,
            timestamp: Utc::now(),
        };

        self.message_queue.push(message.clone());
        Ok(message)
    }

    pub fn get_messages_for_agent(&self, agent_id: &str) -> Vec<&A2aMessage> {
        self.message_queue
            .iter()
            .filter(|m| m.recipient_id == agent_id)
            .collect()
    }

    pub fn get_agent(&self, agent_id: &str) -> Option<&Agent> {
        self.agents.get(agent_id)
    }

    pub fn list_agents(&self) -> Vec<&Agent> {
        self.agents.values().collect()
    }

    pub fn message_count(&self) -> usize {
        self.message_queue.len()
    }
}

impl Default for A2aRouter {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_register_agent() {
        let mut router = A2aRouter::new();
        let agent = router.register_agent("policy_agent".to_string(), "policy_enforcer".to_string());

        assert_eq!(agent.name, "policy_agent");
        assert_eq!(agent.role, "policy_enforcer");
    }

    #[test]
    fn test_send_message() {
        let mut router = A2aRouter::new();
        let agent1 = router.register_agent("agent1".to_string(), "orchestrator".to_string());
        let agent2 = router.register_agent("agent2".to_string(), "evaluator".to_string());

        let result = router.send_message(
            agent1.id.clone(),
            agent2.id.clone(),
            "evaluate_request".to_string(),
            serde_json::json!({"request_id": "req123"}),
        );

        assert!(result.is_ok());
    }

    #[test]
    fn test_get_messages_for_agent() {
        let mut router = A2aRouter::new();
        let agent1 = router.register_agent("agent1".to_string(), "orchestrator".to_string());
        let agent2 = router.register_agent("agent2".to_string(), "evaluator".to_string());

        router.send_message(
            agent1.id.clone(),
            agent2.id.clone(),
            "message1".to_string(),
            serde_json::json!({}),
        ).ok();

        let messages = router.get_messages_for_agent(&agent2.id);
        assert_eq!(messages.len(), 1);
    }

    #[test]
    fn test_invalid_recipient() {
        let mut router = A2aRouter::new();
        let agent = router.register_agent("agent1".to_string(), "role1".to_string());

        let result = router.send_message(
            agent.id.clone(),
            "nonexistent".to_string(),
            "type".to_string(),
            serde_json::json!({}),
        );

        assert!(result.is_err());
    }

    #[test]
    fn test_list_agents() {
        let mut router = A2aRouter::new();
        router.register_agent("agent1".to_string(), "role1".to_string());
        router.register_agent("agent2".to_string(), "role2".to_string());

        assert_eq!(router.list_agents().len(), 2);
    }
}
