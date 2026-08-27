//! L4 Error Handling: Orchestration with retry logic and escalation
//! Handles LangGraph pilot state management, timeouts, and human escalation

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Error, Debug, Clone, Serialize, Deserialize)]
pub enum L4Error {
    #[error("Pilot initialization failed: {reason}. Recovery: {recovery}")]
    PilotInitFailed {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Orchestration timeout: exceeded {timeout_ms}ms. Recovery: {recovery}")]
    OrchestrationTimeout {
        timeout_ms: u64,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("State transition invalid: {from} -> {to}. Recovery: {recovery}")]
    InvalidStateTransition {
        from: String,
        to: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Layer execution failed in {layer}: {reason}. Recovery: {recovery}")]
    LayerExecutionFailed {
        layer: String,
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Checkpoint missing: {checkpoint_id}. Recovery: {recovery}")]
    CheckpointMissing {
        checkpoint_id: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Escalation failed: {reason}. Recovery: {recovery}")]
    EscalationFailed {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Request ID invalid: {reason}. Recovery: {recovery}")]
    InvalidRequestId {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },
}

impl L4Error {
    pub fn reason(&self) -> String {
        match self {
            Self::PilotInitFailed { reason, .. } => reason.clone(),
            Self::OrchestrationTimeout { timeout_ms, .. } => {
                format!("Orchestration exceeded {}ms", timeout_ms)
            }
            Self::InvalidStateTransition { from, to, .. } => {
                format!("Cannot transition from {} to {}", from, to)
            }
            Self::LayerExecutionFailed { layer, reason, .. } => {
                format!("{} execution failed: {}", layer, reason)
            }
            Self::CheckpointMissing { checkpoint_id, .. } => {
                format!("Checkpoint {} not in audit trail", checkpoint_id)
            }
            Self::EscalationFailed { reason, .. } => reason.clone(),
            Self::InvalidRequestId { reason, .. } => reason.clone(),
        }
    }

    pub fn timestamp(&self) -> DateTime<Utc> {
        match self {
            Self::PilotInitFailed { timestamp, .. }
            | Self::OrchestrationTimeout { timestamp, .. }
            | Self::InvalidStateTransition { timestamp, .. }
            | Self::LayerExecutionFailed { timestamp, .. }
            | Self::CheckpointMissing { timestamp, .. }
            | Self::EscalationFailed { timestamp, .. }
            | Self::InvalidRequestId { timestamp, .. } => *timestamp,
        }
    }

    pub fn recovery(&self) -> String {
        match self {
            Self::PilotInitFailed { recovery, .. }
            | Self::OrchestrationTimeout { recovery, .. }
            | Self::InvalidStateTransition { recovery, .. }
            | Self::LayerExecutionFailed { recovery, .. }
            | Self::CheckpointMissing { recovery, .. }
            | Self::EscalationFailed { recovery, .. }
            | Self::InvalidRequestId { recovery, .. } => recovery.clone(),
        }
    }
}

/// Retry configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RetryConfig {
    pub max_retries: u32,
    pub initial_backoff_ms: u64,
    pub max_backoff_ms: u64,
    pub backoff_multiplier: f64,
}

impl Default for RetryConfig {
    fn default() -> Self {
        Self {
            max_retries: 3,
            initial_backoff_ms: 100,
            max_backoff_ms: 5000,
            backoff_multiplier: 2.0,
        }
    }
}

/// AuditEntry for orchestration in L4
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct L4AuditEntry {
    pub timestamp: DateTime<Utc>,
    pub event_id: String,
    pub request_id: String,
    pub state: String,
    pub layer: String,
    pub error: Option<String>,
    pub retry_count: u32,
    pub escalated: bool,
}

impl L4AuditEntry {
    pub fn new(request_id: String, state: String, layer: String) -> Self {
        Self {
            timestamp: Utc::now(),
            event_id: uuid::Uuid::new_v4().to_string(),
            request_id,
            state,
            layer,
            error: None,
            retry_count: 0,
            escalated: false,
        }
    }

    pub fn with_error(mut self, error: L4Error) -> Self {
        self.error = Some(format!("{:?}", error));
        self
    }

    pub fn with_retry(mut self, count: u32) -> Self {
        self.retry_count = count;
        self
    }

    pub fn escalate(mut self) -> Self {
        self.escalated = true;
        self
    }
}

/// Input validation for L4
pub fn validate_request_id(request_id: &str) -> Result<(), L4Error> {
    if request_id.is_empty() {
        return Err(L4Error::InvalidRequestId {
            reason: "Request ID cannot be empty".to_string(),
            recovery: "Provide UUID v4 or unique identifier".to_string(),
            timestamp: Utc::now(),
        });
    }
    if request_id.len() > 255 {
        return Err(L4Error::InvalidRequestId {
            reason: "Request ID exceeds 255 characters".to_string(),
            recovery: "Use shorter ID (typically UUID is 36 chars)".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

pub fn validate_state(state: &str) -> Result<(), L4Error> {
    let valid_states = [
        "REQUEST",
        "L1_POLICY",
        "L2_KNOWLEDGE",
        "L3_PERMIT",
        "L4_ORCHESTRATION",
        "L5_COMMUNICATION",
        "L6_INFRASTRUCTURE",
        "L7_EVALUATION",
        "L8_PROOF",
        "COMPLETE",
    ];
    if !valid_states.contains(&state) {
        return Err(L4Error::InvalidStateTransition {
            from: "UNKNOWN".to_string(),
            to: state.to_string(),
            recovery: format!("Use valid state: {}", valid_states.join(", ")),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

pub fn validate_timeout(timeout_ms: u64) -> Result<(), L4Error> {
    if timeout_ms == 0 {
        return Err(L4Error::OrchestrationTimeout {
            timeout_ms,
            recovery: "Set timeout > 0ms (e.g., 30000)".to_string(),
            timestamp: Utc::now(),
        });
    }
    if timeout_ms > 600_000 {
        return Err(L4Error::OrchestrationTimeout {
            timeout_ms,
            recovery: "Timeout too large (max 600s)".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

pub fn validate_retry_config(config: &RetryConfig) -> Result<(), L4Error> {
    if config.max_retries > 10 {
        return Err(L4Error::PilotInitFailed {
            reason: "Max retries exceeds 10".to_string(),
            recovery: "Set max_retries <= 10".to_string(),
            timestamp: Utc::now(),
        });
    }
    if config.initial_backoff_ms == 0 {
        return Err(L4Error::PilotInitFailed {
            reason: "Initial backoff must be > 0".to_string(),
            recovery: "Set initial_backoff_ms >= 1".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_validate_request_id_empty() {
        let result = validate_request_id("");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_request_id_too_long() {
        let long_id = "a".repeat(300);
        let result = validate_request_id(&long_id);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_state_valid() {
        assert!(validate_state("REQUEST").is_ok());
        assert!(validate_state("L1_POLICY").is_ok());
        assert!(validate_state("COMPLETE").is_ok());
    }

    #[test]
    fn test_validate_state_invalid() {
        let result = validate_state("INVALID_STATE");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_timeout_zero() {
        let result = validate_timeout(0);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_timeout_too_large() {
        let result = validate_timeout(700_000);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_retry_config_too_many_retries() {
        let config = RetryConfig {
            max_retries: 20,
            ..Default::default()
        };
        let result = validate_retry_config(&config);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_retry_config_valid() {
        let config = RetryConfig::default();
        let result = validate_retry_config(&config);
        assert!(result.is_ok());
    }

    #[test]
    fn test_audit_entry_with_retry() {
        let entry = L4AuditEntry::new(
            "req-123".to_string(),
            "L1_POLICY".to_string(),
            "L1".to_string(),
        );
        let entry = entry.with_retry(2);
        assert_eq!(entry.retry_count, 2);
    }

    #[test]
    fn test_audit_entry_escalate() {
        let entry = L4AuditEntry::new(
            "req-123".to_string(),
            "L3_PERMIT".to_string(),
            "L3".to_string(),
        );
        let entry = entry.escalate();
        assert!(entry.escalated);
    }

    #[test]
    fn test_default_retry_config() {
        let config = RetryConfig::default();
        assert_eq!(config.max_retries, 3);
        assert_eq!(config.initial_backoff_ms, 100);
    }
}
