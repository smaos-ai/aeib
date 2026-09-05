//! L1 Error Handling: Policy evaluation failures with graceful degradation
//! Implements deny-by-default for unrecognized policies, full audit trail

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Error, Debug, Clone, Serialize, Deserialize)]
pub enum L1Error {
    #[error("Policy validation failed: {reason}. Recovery: {recovery}")]
    PolicyValidationFailed {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Policy not found: {policy_id}. Recovery: {recovery}")]
    PolicyNotFound {
        policy_id: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Article reference invalid: {article}. Recovery: {recovery}")]
    InvalidArticleReference {
        article: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Compliance level out of bounds: {level}. Recovery: {recovery}")]
    ComplianceLevelBounds {
        level: u8,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Request parsing failed: {reason}. Recovery: {recovery}")]
    RequestParseFailed {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Policy timeout: operation exceeded {timeout_ms}ms. Recovery: {recovery}")]
    PolicyTimeout {
        timeout_ms: u64,
        recovery: String,
        timestamp: DateTime<Utc>,
    },
}

impl L1Error {
    pub fn reason(&self) -> String {
        match self {
            Self::PolicyValidationFailed { reason, .. } => reason.clone(),
            Self::PolicyNotFound { policy_id, .. } => {
                format!("Policy {} not in registry", policy_id)
            }
            Self::InvalidArticleReference { article, .. } => {
                format!("Article {} not EU AI Act compliant", article)
            }
            Self::ComplianceLevelBounds { level, .. } => {
                format!("Compliance level {} outside 0-100 range", level)
            }
            Self::RequestParseFailed { reason, .. } => reason.clone(),
            Self::PolicyTimeout { timeout_ms, .. } => {
                format!("Policy evaluation exceeded {}ms", timeout_ms)
            }
        }
    }

    pub fn timestamp(&self) -> DateTime<Utc> {
        match self {
            Self::PolicyValidationFailed { timestamp, .. }
            | Self::PolicyNotFound { timestamp, .. }
            | Self::InvalidArticleReference { timestamp, .. }
            | Self::ComplianceLevelBounds { timestamp, .. }
            | Self::RequestParseFailed { timestamp, .. }
            | Self::PolicyTimeout { timestamp, .. } => *timestamp,
        }
    }

    pub fn recovery(&self) -> String {
        match self {
            Self::PolicyValidationFailed { recovery, .. }
            | Self::PolicyNotFound { recovery, .. }
            | Self::InvalidArticleReference { recovery, .. }
            | Self::ComplianceLevelBounds { recovery, .. }
            | Self::RequestParseFailed { recovery, .. }
            | Self::PolicyTimeout { recovery, .. } => recovery.clone(),
        }
    }
}

/// AuditEntry for error tracking in L1
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct L1AuditEntry {
    pub timestamp: DateTime<Utc>,
    pub event_id: String,
    pub error: Option<String>,
    pub policy_id: String,
    pub decision: String,
    pub compliance_level: u8,
}

impl L1AuditEntry {
    pub fn new(policy_id: String, decision: String, compliance_level: u8) -> Self {
        Self {
            timestamp: Utc::now(),
            event_id: uuid::Uuid::new_v4().to_string(),
            error: None,
            policy_id,
            decision,
            compliance_level,
        }
    }

    pub fn with_error(mut self, error: L1Error) -> Self {
        self.error = Some(format!("{:?}", error));
        self
    }
}

/// Input validation for L1
pub fn validate_policy_id(policy_id: &str) -> Result<(), L1Error> {
    if policy_id.is_empty() {
        return Err(L1Error::PolicyValidationFailed {
            reason: "Policy ID cannot be empty".to_string(),
            recovery: "Provide non-empty policy ID (e.g., 'compliance', 'safety')".to_string(),
            timestamp: Utc::now(),
        });
    }
    if policy_id.len() > 255 {
        return Err(L1Error::PolicyValidationFailed {
            reason: "Policy ID exceeds 255 characters".to_string(),
            recovery: "Shorten policy ID to under 255 characters".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

pub fn validate_article_reference(article: &str) -> Result<(), L1Error> {
    if !article.starts_with("Article ") {
        return Err(L1Error::InvalidArticleReference {
            article: article.to_string(),
            recovery: "Use format 'Article N' (e.g., 'Article 50')".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

pub fn validate_compliance_level(level: u8) -> Result<(), L1Error> {
    if level > 100 {
        return Err(L1Error::ComplianceLevelBounds {
            level,
            recovery: "Use compliance level 0-100 (inclusive)".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

pub fn validate_request(request: &str) -> Result<(), L1Error> {
    if request.is_empty() {
        return Err(L1Error::RequestParseFailed {
            reason: "Request cannot be empty".to_string(),
            recovery: "Provide non-empty request text".to_string(),
            timestamp: Utc::now(),
        });
    }
    if request.len() > 10_000 {
        return Err(L1Error::RequestParseFailed {
            reason: "Request exceeds 10KB".to_string(),
            recovery: "Chunk request into smaller parts or summarize".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_validate_policy_id_empty() {
        let result = validate_policy_id("");
        assert!(result.is_err());
        if let Err(L1Error::PolicyValidationFailed { recovery, .. }) = result {
            assert!(recovery.contains("non-empty"));
        }
    }

    #[test]
    fn test_validate_policy_id_too_long() {
        let long_id = "a".repeat(300);
        let result = validate_policy_id(&long_id);
        assert!(result.is_err());
        if let Err(L1Error::PolicyValidationFailed { recovery, .. }) = result {
            assert!(recovery.contains("Shorten"));
        }
    }

    #[test]
    fn test_validate_article_reference_invalid_format() {
        let result = validate_article_reference("ARTICLE 50");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_article_reference_valid() {
        let result = validate_article_reference("Article 50");
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_compliance_level_bounds() {
        let result = validate_compliance_level(150);
        assert!(result.is_err());
        if let Err(L1Error::ComplianceLevelBounds { recovery, .. }) = result {
            assert!(recovery.contains("0-100"));
        }
    }

    #[test]
    fn test_validate_request_empty() {
        let result = validate_request("");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_request_too_large() {
        let large_request = "x".repeat(11_000);
        let result = validate_request(&large_request);
        assert!(result.is_err());
    }

    #[test]
    fn test_audit_entry_with_error() {
        let entry = L1AuditEntry::new("test_policy".to_string(), "allow".to_string(), 100);
        let error = L1Error::PolicyValidationFailed {
            reason: "test".to_string(),
            recovery: "retry".to_string(),
            timestamp: Utc::now(),
        };
        let entry_with_error = entry.with_error(error);
        assert!(entry_with_error.error.is_some());
    }

    #[test]
    fn test_error_timestamp() {
        let error = L1Error::PolicyValidationFailed {
            reason: "test".to_string(),
            recovery: "retry".to_string(),
            timestamp: Utc::now(),
        };
        let ts = error.timestamp();
        assert!(ts <= Utc::now());
    }
}
