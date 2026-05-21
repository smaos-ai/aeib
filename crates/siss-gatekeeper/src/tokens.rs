use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionToken {
    pub token: String,
    pub expires_in: u64,    // seconds
    pub token_type: String, // "Bearer"
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Delegation {
    pub permission: String,        // "can_execute"
    pub resource_type: String,     // "tool"
    pub resource_ids: Vec<String>, // tool UUIDs
    pub constraints: DelegationConstraints,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DelegationConstraints {
    pub rate_limit: Option<String>, // "1000/minute"
    pub max_concurrent: Option<u32>,
    pub allowed_hardware: Option<Vec<String>>, // ["LocalMlx", "Hybrid"]
    pub max_duration_seconds: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CapabilityToken {
    pub token: String, // Signed envelope
    pub delegations: Vec<Delegation>,
    pub issued_at: DateTime<Utc>,
    pub valid_until: DateTime<Utc>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct HandshakeResponse {
    pub status: String, // "authenticated" or "denied"
    pub selected_scheme: Option<String>,
    pub session_token: Option<SessionToken>,
    pub capability_token: Option<CapabilityToken>,
    pub trust_policy_requirements: Option<TrustPolicyRequirements>,
    pub reason: Option<String>, // For denied responses
    pub detail: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct TrustPolicyRequirements {
    pub minimum_security_tier: u32,
    pub required_capabilities: Vec<String>,
    pub attestation_required: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IntentMandate {
    pub id: Uuid,
    pub budget_limit: i64,
    pub budget_spent: i64,
    pub risk_class: String,
    pub allowed_tools: Vec<Uuid>,
}

impl IntentMandate {
    pub fn budget_remaining(&self) -> i64 {
        self.budget_limit - self.budget_spent
    }

    pub fn is_budget_exhausted(&self) -> bool {
        self.budget_remaining() <= 0
    }

    pub fn can_use_tool(&self, tool_id: Uuid) -> bool {
        self.allowed_tools.contains(&tool_id)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthorizedJob {
    pub task_id: Uuid,
    pub mandate_id: Uuid,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_session_token_can_be_created() {
        let token = SessionToken {
            token: "jwt-token".to_string(),
            expires_in: 3600,
            token_type: "Bearer".to_string(),
        };
        assert_eq!(token.expires_in, 3600);
    }

    #[test]
    fn test_capability_token_can_be_created() {
        let delegation = Delegation {
            permission: "can_execute".to_string(),
            resource_type: "tool".to_string(),
            resource_ids: vec!["tool-1".to_string()],
            constraints: DelegationConstraints {
                rate_limit: Some("1000/minute".to_string()),
                max_concurrent: Some(5),
                allowed_hardware: Some(vec!["LocalMlx".to_string()]),
                max_duration_seconds: Some(300),
            },
        };
        let capability_token = CapabilityToken {
            token: "cap-token".to_string(),
            delegations: vec![delegation],
            issued_at: Utc::now(),
            valid_until: Utc::now() + chrono::Duration::hours(24),
        };
        assert_eq!(capability_token.delegations.len(), 1);
    }

    #[test]
    fn test_handshake_response_authenticated() {
        let response = HandshakeResponse {
            status: "authenticated".to_string(),
            selected_scheme: Some("Bearer".to_string()),
            session_token: Some(SessionToken {
                token: "token".to_string(),
                expires_in: 3600,
                token_type: "Bearer".to_string(),
            }),
            capability_token: Some(CapabilityToken {
                token: "cap".to_string(),
                delegations: vec![],
                issued_at: Utc::now(),
                valid_until: Utc::now() + chrono::Duration::hours(24),
            }),
            trust_policy_requirements: None,
            reason: None,
            detail: None,
        };
        assert_eq!(response.status, "authenticated");
    }
}
