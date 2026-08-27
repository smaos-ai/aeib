//! L2 Error Handling: Knowledge database operations with graceful fallback
//! Handles vector search, keyword search, and database connectivity failures

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Error, Debug, Clone, Serialize, Deserialize)]
pub enum L2Error {
    #[error("Database connection failed: {reason}. Recovery: {recovery}")]
    DatabaseConnectionFailed {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Search query invalid: {reason}. Recovery: {recovery}")]
    InvalidSearchQuery {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Vector embedding failed: {reason}. Recovery: {recovery}")]
    EmbeddingFailed {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Search timeout: exceeded {timeout_ms}ms. Recovery: {recovery}")]
    SearchTimeout {
        timeout_ms: u64,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Policy not found in knowledge base: {policy_id}. Recovery: {recovery}")]
    PolicyNotFound {
        policy_id: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("RRF ranking failed: {reason}. Recovery: {recovery}")]
    RRFRankingFailed {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Database query failed: {reason}. Recovery: {recovery}")]
    QueryFailed {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },
}

impl L2Error {
    pub fn reason(&self) -> String {
        match self {
            Self::DatabaseConnectionFailed { reason, .. } => reason.clone(),
            Self::InvalidSearchQuery { reason, .. } => reason.clone(),
            Self::EmbeddingFailed { reason, .. } => reason.clone(),
            Self::SearchTimeout { timeout_ms, .. } => {
                format!("Search exceeded {}ms limit", timeout_ms)
            }
            Self::PolicyNotFound { policy_id, .. } => format!("Policy {} not indexed", policy_id),
            Self::RRFRankingFailed { reason, .. } => reason.clone(),
            Self::QueryFailed { reason, .. } => reason.clone(),
        }
    }

    pub fn timestamp(&self) -> DateTime<Utc> {
        match self {
            Self::DatabaseConnectionFailed { timestamp, .. }
            | Self::InvalidSearchQuery { timestamp, .. }
            | Self::EmbeddingFailed { timestamp, .. }
            | Self::SearchTimeout { timestamp, .. }
            | Self::PolicyNotFound { timestamp, .. }
            | Self::RRFRankingFailed { timestamp, .. }
            | Self::QueryFailed { timestamp, .. } => *timestamp,
        }
    }

    pub fn recovery(&self) -> String {
        match self {
            Self::DatabaseConnectionFailed { recovery, .. }
            | Self::InvalidSearchQuery { recovery, .. }
            | Self::EmbeddingFailed { recovery, .. }
            | Self::SearchTimeout { recovery, .. }
            | Self::PolicyNotFound { recovery, .. }
            | Self::RRFRankingFailed { recovery, .. }
            | Self::QueryFailed { recovery, .. } => recovery.clone(),
        }
    }
}

/// AuditEntry for search operations in L2
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct L2AuditEntry {
    pub timestamp: DateTime<Utc>,
    pub event_id: String,
    pub query: String,
    pub search_type: String, // "keyword" or "vector" or "rrf"
    pub error: Option<String>,
    pub result_count: usize,
    pub latency_ms: u64,
}

impl L2AuditEntry {
    pub fn new(query: String, search_type: String) -> Self {
        Self {
            timestamp: Utc::now(),
            event_id: uuid::Uuid::new_v4().to_string(),
            query,
            search_type,
            error: None,
            result_count: 0,
            latency_ms: 0,
        }
    }

    pub fn with_error(mut self, error: L2Error) -> Self {
        self.error = Some(format!("{:?}", error));
        self
    }

    pub fn with_results(mut self, result_count: usize, latency_ms: u64) -> Self {
        self.result_count = result_count;
        self.latency_ms = latency_ms;
        self
    }
}

/// Input validation for L2
pub fn validate_search_query(query: &str) -> Result<(), L2Error> {
    if query.is_empty() {
        return Err(L2Error::InvalidSearchQuery {
            reason: "Search query cannot be empty".to_string(),
            recovery: "Provide non-empty search terms (min 1 char, max 1000)".to_string(),
            timestamp: Utc::now(),
        });
    }
    if query.len() > 1000 {
        return Err(L2Error::InvalidSearchQuery {
            reason: "Search query exceeds 1000 characters".to_string(),
            recovery: "Shorten query or use multiple searches".to_string(),
            timestamp: Utc::now(),
        });
    }
    if query.contains('\0') {
        return Err(L2Error::InvalidSearchQuery {
            reason: "Search query contains null bytes".to_string(),
            recovery: "Remove null bytes from query".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

pub fn validate_policy_id(policy_id: &str) -> Result<(), L2Error> {
    if policy_id.is_empty() {
        return Err(L2Error::InvalidSearchQuery {
            reason: "Policy ID cannot be empty".to_string(),
            recovery: "Provide valid policy ID".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

pub fn validate_limit(limit: usize) -> Result<(), L2Error> {
    if limit == 0 {
        return Err(L2Error::InvalidSearchQuery {
            reason: "Limit must be > 0".to_string(),
            recovery: "Set limit to positive integer (e.g., 10)".to_string(),
            timestamp: Utc::now(),
        });
    }
    if limit > 1000 {
        return Err(L2Error::InvalidSearchQuery {
            reason: "Limit exceeds maximum of 1000".to_string(),
            recovery: "Reduce limit to <= 1000".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

pub fn validate_connection_string(conn_str: &str) -> Result<(), L2Error> {
    if conn_str.is_empty() {
        return Err(L2Error::DatabaseConnectionFailed {
            reason: "Connection string is empty".to_string(),
            recovery: "Provide valid PostgreSQL connection string".to_string(),
            timestamp: Utc::now(),
        });
    }
    if !conn_str.starts_with("postgres://") && !conn_str.starts_with("postgresql://") {
        return Err(L2Error::DatabaseConnectionFailed {
            reason: "Invalid connection string format".to_string(),
            recovery: "Use format: postgresql://user:pass@host:5432/db".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_validate_search_query_empty() {
        let result = validate_search_query("");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_search_query_too_long() {
        let long_query = "a".repeat(1001);
        let result = validate_search_query(&long_query);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_search_query_null_bytes() {
        let query = "test\0query";
        let result = validate_search_query(query);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_policy_id_empty() {
        let result = validate_policy_id("");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_limit_zero() {
        let result = validate_limit(0);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_limit_too_large() {
        let result = validate_limit(1001);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_connection_string_invalid_format() {
        let result = validate_connection_string("mysql://localhost");
        assert!(result.is_err());
    }

    #[test]
    fn test_audit_entry_with_results() {
        let entry = L2AuditEntry::new("test query".to_string(), "keyword".to_string());
        let entry = entry.with_results(5, 42);
        assert_eq!(entry.result_count, 5);
        assert_eq!(entry.latency_ms, 42);
    }

    #[test]
    fn test_audit_entry_with_error() {
        let entry = L2AuditEntry::new("test query".to_string(), "keyword".to_string());
        let error = L2Error::QueryFailed {
            reason: "test".to_string(),
            recovery: "retry".to_string(),
            timestamp: Utc::now(),
        };
        let entry = entry.with_error(error);
        assert!(entry.error.is_some());
    }

    #[test]
    fn test_error_recovery_message() {
        let error = L2Error::SearchTimeout {
            timeout_ms: 500,
            recovery: "increase timeout or optimize query".to_string(),
            timestamp: Utc::now(),
        };
        let recovery = error.recovery();
        assert!(recovery.contains("optimize"));
    }
}
