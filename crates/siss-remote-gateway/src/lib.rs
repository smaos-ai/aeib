use chrono::Utc;
use serde::{Deserialize, Serialize};
use thiserror::Error;
use uuid::Uuid;

// ApprovalAction enum with Approve and Reject variants
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum ApprovalAction {
    Approve,
    Reject,
}

// GatewayStatus enum with Approved, Rejected, and Pending variants
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum GatewayStatus {
    Approved,
    Rejected,
    Pending,
}

// ApprovalRequest struct
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApprovalRequest {
    pub capsule_id: Uuid,
    pub mandate_id: Uuid,
    pub operator: String,
    pub action: ApprovalAction,
}

// ApprovalResponse struct
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApprovalResponse {
    pub capsule_id: Uuid,
    pub status: GatewayStatus,
    pub timestamp_utc: String,
}

// GatewayError enum
#[derive(Debug, Error, PartialEq)]
pub enum GatewayError {
    #[error("Unauthorized")]
    Unauthorized,
    #[error("Internal error: {0}")]
    Internal(String),
}

// RemoteGateway struct
#[derive(Debug, Clone)]
pub struct RemoteGateway {
    #[allow(dead_code)]
    expected_token: String,
}

impl RemoteGateway {
    /// Creates a new RemoteGateway instance with the expected token.
    pub fn new(expected_token: String) -> Self {
        RemoteGateway { expected_token }
    }

    /// Validates the presented token against the expected token.
    /// Returns Err(Unauthorized) if presented is empty or doesn't match expected_token.
    pub fn validate_token(&self, presented: &str) -> Result<(), GatewayError> {
        if presented.is_empty() || presented != self.expected_token {
            return Err(GatewayError::Unauthorized);
        }
        Ok(())
    }

    /// Processes an approval request.
    /// First validates the token, then maps the action to status.
    /// Returns ApprovalResponse with capsule_id, status, and timestamp_utc.
    pub fn process_approval(
        &self,
        req: ApprovalRequest,
        token: &str,
    ) -> Result<ApprovalResponse, GatewayError> {
        self.validate_token(token)?;
        let status = match req.action {
            ApprovalAction::Approve => GatewayStatus::Approved,
            ApprovalAction::Reject => GatewayStatus::Rejected,
        };
        let response = ApprovalResponse {
            capsule_id: req.capsule_id,
            status,
            timestamp_utc: Utc::now().to_rfc3339(),
        };
        Ok(response)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_missing_token_returns_unauthorized() {
        let gateway = RemoteGateway::new("secret".to_string());
        let result = gateway.validate_token("");
        assert_eq!(result, Err(GatewayError::Unauthorized));
    }

    #[test]
    fn test_approve_action_returns_approved_status() {
        let gateway = RemoteGateway::new("secret".to_string());
        let req = ApprovalRequest {
            capsule_id: Uuid::new_v4(),
            mandate_id: Uuid::new_v4(),
            operator: "mobile_operator".to_string(),
            action: ApprovalAction::Approve,
        };
        let result = gateway.process_approval(req.clone(), "secret");
        assert!(result.is_ok());
        let response = result.unwrap();
        assert_eq!(response.status, GatewayStatus::Approved);
        assert_eq!(response.capsule_id, req.capsule_id);
    }

    #[test]
    fn test_reject_action_returns_rejected_status() {
        let gateway = RemoteGateway::new("secret".to_string());
        let req = ApprovalRequest {
            capsule_id: Uuid::new_v4(),
            mandate_id: Uuid::new_v4(),
            operator: "mobile_operator".to_string(),
            action: ApprovalAction::Reject,
        };
        let result = gateway.process_approval(req.clone(), "secret");
        assert!(result.is_ok());
        let response = result.unwrap();
        assert_eq!(response.status, GatewayStatus::Rejected);
        assert_eq!(response.capsule_id, req.capsule_id);
    }
}
