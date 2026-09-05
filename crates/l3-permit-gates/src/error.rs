//! L3 Error Handling: Permit gate enforcement with deny-by-default strategy
//! All tool invocations fail safely if gate evaluation fails

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Error, Debug, Clone, Serialize, Deserialize)]
pub enum L3Error {
    #[error("Gate registration failed: {reason}. Recovery: {recovery}")]
    GateRegistrationFailed {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Tool binding invalid: {tool_name}. Recovery: {recovery}")]
    InvalidToolBinding {
        tool_name: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Policy gate lookup failed: {gate_id}. Recovery: {recovery}")]
    GateNotFound {
        gate_id: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Invocation blocked by policy: {reason}. Recovery: {recovery}")]
    InvocationBlocked {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Approval timeout: exceeded {timeout_ms}ms. Recovery: {recovery}")]
    ApprovalTimeout {
        timeout_ms: u64,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Approval chain invalid: {reason}. Recovery: {recovery}")]
    InvalidApprovalChain {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Tool parameter validation failed: {reason}. Recovery: {recovery}")]
    ParameterValidationFailed {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },
}

impl L3Error {
    pub fn reason(&self) -> String {
        match self {
            Self::GateRegistrationFailed { reason, .. } => reason.clone(),
            Self::InvalidToolBinding { tool_name, .. } => {
                format!("Tool {} not registered in gate registry", tool_name)
            }
            Self::GateNotFound { gate_id, .. } => format!("Gate {} not found", gate_id),
            Self::InvocationBlocked { reason, .. } => reason.clone(),
            Self::ApprovalTimeout { timeout_ms, .. } => {
                format!("Approval exceeded {}ms timeout", timeout_ms)
            }
            Self::InvalidApprovalChain { reason, .. } => reason.clone(),
            Self::ParameterValidationFailed { reason, .. } => reason.clone(),
        }
    }

    pub fn timestamp(&self) -> DateTime<Utc> {
        match self {
            Self::GateRegistrationFailed { timestamp, .. }
            | Self::InvalidToolBinding { timestamp, .. }
            | Self::GateNotFound { timestamp, .. }
            | Self::InvocationBlocked { timestamp, .. }
            | Self::ApprovalTimeout { timestamp, .. }
            | Self::InvalidApprovalChain { timestamp, .. }
            | Self::ParameterValidationFailed { timestamp, .. } => *timestamp,
        }
    }

    pub fn recovery(&self) -> String {
        match self {
            Self::GateRegistrationFailed { recovery, .. }
            | Self::InvalidToolBinding { recovery, .. }
            | Self::GateNotFound { recovery, .. }
            | Self::InvocationBlocked { recovery, .. }
            | Self::ApprovalTimeout { recovery, .. }
            | Self::InvalidApprovalChain { recovery, .. }
            | Self::ParameterValidationFailed { recovery, .. } => recovery.clone(),
        }
    }
}

/// AuditEntry for gate enforcement in L3
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct L3AuditEntry {
    pub timestamp: DateTime<Utc>,
    pub event_id: String,
    pub gate_id: String,
    pub tool_name: String,
    pub decision: String, // "ALLOWED" or "DENIED"
    pub error: Option<String>,
    pub approver: Option<String>,
    pub reason: String,
}

impl L3AuditEntry {
    pub fn new(gate_id: String, tool_name: String, decision: String) -> Self {
        Self {
            timestamp: Utc::now(),
            event_id: uuid::Uuid::new_v4().to_string(),
            gate_id,
            tool_name,
            decision,
            error: None,
            approver: None,
            reason: String::new(),
        }
    }

    pub fn with_error(mut self, error: L3Error) -> Self {
        self.error = Some(format!("{:?}", error));
        self
    }

    pub fn with_approver(mut self, approver: String, reason: String) -> Self {
        self.approver = Some(approver);
        self.reason = reason;
        self
    }
}

/// Input validation for L3
pub fn validate_gate_id(gate_id: &str) -> Result<(), L3Error> {
    if gate_id.is_empty() {
        return Err(L3Error::GateRegistrationFailed {
            reason: "Gate ID cannot be empty".to_string(),
            recovery: "Provide non-empty gate ID (e.g., 'tool-exec-1')".to_string(),
            timestamp: Utc::now(),
        });
    }
    if gate_id.len() > 255 {
        return Err(L3Error::GateRegistrationFailed {
            reason: "Gate ID exceeds 255 characters".to_string(),
            recovery: "Shorten gate ID".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

pub fn validate_tool_name(tool_name: &str) -> Result<(), L3Error> {
    if tool_name.is_empty() {
        return Err(L3Error::InvalidToolBinding {
            tool_name: tool_name.to_string(),
            recovery: "Provide non-empty tool name".to_string(),
            timestamp: Utc::now(),
        });
    }
    if !tool_name.chars().all(|c| c.is_alphanumeric() || c == '_') {
        return Err(L3Error::InvalidToolBinding {
            tool_name: tool_name.to_string(),
            recovery: "Tool name must contain only alphanumerics and underscores".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

pub fn validate_approval_decision(decision: &str) -> Result<(), L3Error> {
    if decision != "ALLOWED" && decision != "DENIED" && decision != "ESCALATED" {
        return Err(L3Error::InvalidApprovalChain {
            reason: format!("Invalid decision: {}", decision),
            recovery: "Use one of: ALLOWED, DENIED, ESCALATED".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

pub fn validate_invocation_parameters(params: &str) -> Result<(), L3Error> {
    if params.is_empty() {
        return Err(L3Error::ParameterValidationFailed {
            reason: "Parameters cannot be empty".to_string(),
            recovery: "Provide parameter JSON object or '{}' for no params".to_string(),
            timestamp: Utc::now(),
        });
    }
    if params.len() > 100_000 {
        return Err(L3Error::ParameterValidationFailed {
            reason: "Parameters exceed 100KB".to_string(),
            recovery: "Reduce parameter size or chunk request".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_validate_gate_id_empty() {
        let result = validate_gate_id("");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_gate_id_too_long() {
        let long_id = "a".repeat(300);
        let result = validate_gate_id(&long_id);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_tool_name_empty() {
        let result = validate_tool_name("");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_tool_name_invalid_chars() {
        let result = validate_tool_name("tool-name");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_tool_name_valid() {
        let result = validate_tool_name("tool_name_1");
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_approval_decision_invalid() {
        let result = validate_approval_decision("MAYBE");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_approval_decision_valid() {
        assert!(validate_approval_decision("ALLOWED").is_ok());
        assert!(validate_approval_decision("DENIED").is_ok());
        assert!(validate_approval_decision("ESCALATED").is_ok());
    }

    #[test]
    fn test_validate_invocation_parameters_empty() {
        let result = validate_invocation_parameters("");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_invocation_parameters_too_large() {
        let large_params = "x".repeat(100_001);
        let result = validate_invocation_parameters(&large_params);
        assert!(result.is_err());
    }

    #[test]
    fn test_audit_entry_with_approver() {
        let entry = L3AuditEntry::new(
            "gate-1".to_string(),
            "exec_tool".to_string(),
            "ALLOWED".to_string(),
        );
        let entry = entry.with_approver(
            "admin@example.com".to_string(),
            "Approved for compliance".to_string(),
        );
        assert_eq!(entry.approver, Some("admin@example.com".to_string()));
    }

    #[test]
    fn test_audit_entry_with_error() {
        let entry = L3AuditEntry::new(
            "gate-1".to_string(),
            "exec_tool".to_string(),
            "DENIED".to_string(),
        );
        let error = L3Error::InvocationBlocked {
            reason: "Policy violation".to_string(),
            recovery: "Review policy".to_string(),
            timestamp: Utc::now(),
        };
        let entry = entry.with_error(error);
        assert!(entry.error.is_some());
    }

    #[test]
    fn test_error_timestamp() {
        let error = L3Error::GateNotFound {
            gate_id: "gate-1".to_string(),
            recovery: "Register gate".to_string(),
            timestamp: Utc::now(),
        };
        assert!(error.timestamp() <= Utc::now());
    }
}
