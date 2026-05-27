use uuid::Uuid;
use serde::{Deserialize, Serialize};
use std::time::{SystemTime, UNIX_EPOCH, Duration};
use sha2::{Sha256, Digest};

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum CapabilityLevel {
    None,
    Basic,
    Advanced,
    Expert,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CapabilityToken {
    pub token_id: Uuid,
    pub agent_id: Uuid,
    pub level: CapabilityLevel,
    pub issued_at: u64,
    pub expires_at: u64,
    pub signature: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ExpertTask {
    pub task_id: Uuid,
    pub description: String,
    pub complexity: u8,
    pub required_level: CapabilityLevel,
    pub timeout_ms: u32,
    pub created_at: u64,
}

#[derive(Clone, Debug)]
pub enum EscalationResult {
    Approved { task_id: Uuid, execution_time_ms: u32 },
    Denied { reason: String },
    Timeout { task_id: Uuid, elapsed_ms: u32 },
}

#[derive(Clone, Debug)]
pub enum EscalationError {
    InvalidToken,
    ExpiredToken,
    InsufficientCapability,
    TimeoutExceeded { elapsed_ms: u32, limit_ms: u32 },
    BadSignature,
}

impl CapabilityToken {
    pub fn new(agent_id: Uuid, level: CapabilityLevel, duration_secs: u32) -> Self {
        let token_id = Uuid::new_v4();
        let issued_at = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        let expires_at = issued_at + duration_secs as u64;

        let payload = format!(
            "{}:{}:{:?}:{}:{}",
            token_id, agent_id, level, issued_at, expires_at
        );
        let mut hasher = Sha256::new();
        hasher.update(payload.as_bytes());
        let signature = format!("{:x}", hasher.finalize());

        Self {
            token_id,
            agent_id,
            level,
            issued_at,
            expires_at,
            signature,
        }
    }

    pub fn is_valid(&self) -> bool {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        now < self.expires_at
    }

    pub fn verify_signature(&self) -> bool {
        let payload = format!(
            "{}:{}:{:?}:{}:{}",
            self.token_id, self.agent_id, self.level, self.issued_at, self.expires_at
        );
        let mut hasher = Sha256::new();
        hasher.update(payload.as_bytes());
        let computed = format!("{:x}", hasher.finalize());
        computed == self.signature
    }

    pub fn has_capability(&self, required: CapabilityLevel) -> bool {
        match (self.level, required) {
            (CapabilityLevel::Expert, _) => true,
            (CapabilityLevel::Advanced, CapabilityLevel::Advanced) => true,
            (CapabilityLevel::Advanced, CapabilityLevel::Basic) => true,
            (CapabilityLevel::Basic, CapabilityLevel::Basic) => true,
            _ => false,
        }
    }
}

pub struct ExpertGateway {
    active_tokens: Vec<CapabilityToken>,
    max_concurrent: usize,
}

impl ExpertGateway {
    pub fn new(max_concurrent: usize) -> Self {
        Self {
            active_tokens: Vec::new(),
            max_concurrent,
        }
    }

    pub fn register_token(&mut self, token: CapabilityToken) -> Result<(), EscalationError> {
        if !token.verify_signature() {
            return Err(EscalationError::BadSignature);
        }
        if !token.is_valid() {
            return Err(EscalationError::ExpiredToken);
        }

        self.active_tokens.push(token);
        Ok(())
    }

    pub fn escalate(
        &self,
        task: &ExpertTask,
        agent_id: Uuid,
    ) -> Result<EscalationResult, EscalationError> {
        let start_ms = Self::current_time_ms();

        let token = self
            .active_tokens
            .iter()
            .find(|t| t.agent_id == agent_id)
            .ok_or(EscalationError::InvalidToken)?;

        if !token.is_valid() {
            return Err(EscalationError::ExpiredToken);
        }

        let elapsed_ms = Self::current_time_ms() - start_ms;
        if elapsed_ms > task.timeout_ms {
            return Err(EscalationError::TimeoutExceeded {
                elapsed_ms,
                limit_ms: task.timeout_ms,
            });
        }

        if !token.has_capability(task.required_level) {
            return Err(EscalationError::InsufficientCapability);
        }

        let execution_time_ms = (task.timeout_ms / 4).min(50);

        Ok(EscalationResult::Approved {
            task_id: task.task_id,
            execution_time_ms,
        })
    }

    pub fn revoke_token(&mut self, token_id: Uuid) {
        self.active_tokens.retain(|t| t.token_id != token_id);
    }

    pub fn cleanup_expired(&mut self) {
        self.active_tokens.retain(|t| t.is_valid());
    }

    fn current_time_ms() -> u32 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis() as u32
    }

    pub fn active_token_count(&self) -> usize {
        self.active_tokens.len()
    }
}

impl Default for ExpertGateway {
    fn default() -> Self {
        Self::new(10)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_capability_token_creation() {
        let token = CapabilityToken::new(Uuid::new_v4(), CapabilityLevel::Expert, 3600);
        assert_eq!(token.level, CapabilityLevel::Expert);
        assert!(token.is_valid());
    }

    #[test]
    fn test_capability_token_expired() {
        let mut token = CapabilityToken::new(Uuid::new_v4(), CapabilityLevel::Expert, 0);
        token.expires_at = 0;
        assert!(!token.is_valid());
    }

    #[test]
    fn test_token_signature_verification() {
        let token = CapabilityToken::new(Uuid::new_v4(), CapabilityLevel::Expert, 3600);
        assert!(token.verify_signature());
    }

    #[test]
    fn test_token_signature_tampering() {
        let mut token = CapabilityToken::new(Uuid::new_v4(), CapabilityLevel::Expert, 3600);
        token.signature = "tampered".to_string();
        assert!(!token.verify_signature());
    }

    #[test]
    fn test_capability_level_hierarchy() {
        let expert = CapabilityToken::new(Uuid::new_v4(), CapabilityLevel::Expert, 3600);
        assert!(expert.has_capability(CapabilityLevel::Basic));
        assert!(expert.has_capability(CapabilityLevel::Advanced));
        assert!(expert.has_capability(CapabilityLevel::Expert));
    }

    #[test]
    fn test_insufficient_capability() {
        let basic = CapabilityToken::new(Uuid::new_v4(), CapabilityLevel::Basic, 3600);
        assert!(!basic.has_capability(CapabilityLevel::Advanced));
        assert!(!basic.has_capability(CapabilityLevel::Expert));
    }

    #[test]
    fn test_expert_gateway_register_token() {
        let mut gateway = ExpertGateway::new(10);
        let token = CapabilityToken::new(Uuid::new_v4(), CapabilityLevel::Expert, 3600);
        assert!(gateway.register_token(token).is_ok());
    }

    #[test]
    fn test_expert_gateway_register_bad_signature() {
        let mut gateway = ExpertGateway::new(10);
        let mut token = CapabilityToken::new(Uuid::new_v4(), CapabilityLevel::Expert, 3600);
        token.signature = "bad".to_string();
        assert!(matches!(
            gateway.register_token(token),
            Err(EscalationError::BadSignature)
        ));
    }

    #[test]
    fn test_escalate_with_valid_token() {
        let mut gateway = ExpertGateway::new(10);
        let agent_id = Uuid::new_v4();
        let token = CapabilityToken::new(agent_id, CapabilityLevel::Expert, 3600);
        gateway.register_token(token).unwrap();

        let task = ExpertTask {
            task_id: Uuid::new_v4(),
            description: "Test task".to_string(),
            complexity: 5,
            required_level: CapabilityLevel::Basic,
            timeout_ms: 1000,
            created_at: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs(),
        };

        let result = gateway.escalate(&task, agent_id).unwrap();
        match result {
            EscalationResult::Approved { task_id, .. } => {
                assert_eq!(task_id, task.task_id);
            }
            _ => panic!("Expected Approved"),
        }
    }

    #[test]
    fn test_escalate_insufficient_capability() {
        let mut gateway = ExpertGateway::new(10);
        let agent_id = Uuid::new_v4();
        let token = CapabilityToken::new(agent_id, CapabilityLevel::Basic, 3600);
        gateway.register_token(token).unwrap();

        let task = ExpertTask {
            task_id: Uuid::new_v4(),
            description: "Test task".to_string(),
            complexity: 5,
            required_level: CapabilityLevel::Expert,
            timeout_ms: 1000,
            created_at: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs(),
        };

        let result = gateway.escalate(&task, agent_id);
        assert!(matches!(
            result,
            Err(EscalationError::InsufficientCapability)
        ));
    }

    #[test]
    fn test_escalate_no_token() {
        let gateway = ExpertGateway::new(10);
        let task = ExpertTask {
            task_id: Uuid::new_v4(),
            description: "Test task".to_string(),
            complexity: 5,
            required_level: CapabilityLevel::Basic,
            timeout_ms: 1000,
            created_at: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs(),
        };

        let result = gateway.escalate(&task, Uuid::new_v4());
        assert!(matches!(result, Err(EscalationError::InvalidToken)));
    }

    #[test]
    fn test_revoke_token() {
        let mut gateway = ExpertGateway::new(10);
        let token = CapabilityToken::new(Uuid::new_v4(), CapabilityLevel::Expert, 3600);
        let token_id = token.token_id;
        gateway.register_token(token).unwrap();
        assert_eq!(gateway.active_token_count(), 1);

        gateway.revoke_token(token_id);
        assert_eq!(gateway.active_token_count(), 0);
    }

    #[test]
    fn test_cleanup_expired_tokens() {
        let mut gateway = ExpertGateway::new(10);
        let mut token = CapabilityToken::new(Uuid::new_v4(), CapabilityLevel::Expert, 3600);
        gateway.register_token(token.clone()).unwrap();

        token.expires_at = 0;
        gateway.active_tokens.push(token);

        assert_eq!(gateway.active_token_count(), 2);
        gateway.cleanup_expired();
        assert_eq!(gateway.active_token_count(), 1);
    }

    #[test]
    fn test_escalation_bounded_execution_time() {
        let mut gateway = ExpertGateway::new(10);
        let agent_id = Uuid::new_v4();
        let token = CapabilityToken::new(agent_id, CapabilityLevel::Expert, 3600);
        gateway.register_token(token).unwrap();

        let task = ExpertTask {
            task_id: Uuid::new_v4(),
            description: "Test task".to_string(),
            complexity: 5,
            required_level: CapabilityLevel::Basic,
            timeout_ms: 200,
            created_at: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs(),
        };

        let result = gateway.escalate(&task, agent_id).unwrap();
        match result {
            EscalationResult::Approved { execution_time_ms, .. } => {
                assert!(execution_time_ms <= 50);
            }
            _ => panic!("Expected Approved"),
        }
    }
}
