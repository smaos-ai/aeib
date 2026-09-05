//! L6 Error Handling: Hardware detection, resource constraints, and fallback paths
//! Graceful degradation when Qwen not available, fallback to smaller models

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Error, Debug, Clone, Serialize, Deserialize)]
pub enum L6Error {
    #[error("Hardware detection failed: {reason}. Recovery: {recovery}")]
    HardwareDetectionFailed {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Insufficient resources: {reason}. Recovery: {recovery}")]
    InsufficientResources {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Model loading failed: {model_name}. Recovery: {recovery}")]
    ModelLoadFailed {
        model_name: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error(
        "Memory constraint violated: {available_gb}GB < {required_gb}GB. Recovery: {recovery}"
    )]
    MemoryConstraint {
        available_gb: f32,
        required_gb: f32,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("GPU not available: {reason}. Recovery: {recovery}")]
    GpuNotAvailable {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Benchmark timeout: exceeded {timeout_ms}ms. Recovery: {recovery}")]
    BenchmarkTimeout {
        timeout_ms: u64,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error(
        "Throughput insufficient: {actual_tok_s} < {required_tok_s} tok/s. Recovery: {recovery}"
    )]
    ThroughputInsufficient {
        actual_tok_s: f32,
        required_tok_s: f32,
        recovery: String,
        timestamp: DateTime<Utc>,
    },
}

impl L6Error {
    pub fn reason(&self) -> String {
        match self {
            Self::HardwareDetectionFailed { reason, .. } => reason.clone(),
            Self::InsufficientResources { reason, .. } => reason.clone(),
            Self::ModelLoadFailed { model_name, .. } => format!("Cannot load {}", model_name),
            Self::MemoryConstraint {
                available_gb,
                required_gb,
                ..
            } => {
                format!("{}GB available, need {}GB", available_gb, required_gb)
            }
            Self::GpuNotAvailable { reason, .. } => reason.clone(),
            Self::BenchmarkTimeout { timeout_ms, .. } => {
                format!("Benchmark exceeded {}ms", timeout_ms)
            }
            Self::ThroughputInsufficient {
                actual_tok_s,
                required_tok_s,
                ..
            } => {
                format!("{} tok/s < {} required", actual_tok_s, required_tok_s)
            }
        }
    }

    pub fn timestamp(&self) -> DateTime<Utc> {
        match self {
            Self::HardwareDetectionFailed { timestamp, .. }
            | Self::InsufficientResources { timestamp, .. }
            | Self::ModelLoadFailed { timestamp, .. }
            | Self::MemoryConstraint { timestamp, .. }
            | Self::GpuNotAvailable { timestamp, .. }
            | Self::BenchmarkTimeout { timestamp, .. }
            | Self::ThroughputInsufficient { timestamp, .. } => *timestamp,
        }
    }

    pub fn recovery(&self) -> String {
        match self {
            Self::HardwareDetectionFailed { recovery, .. }
            | Self::InsufficientResources { recovery, .. }
            | Self::ModelLoadFailed { recovery, .. }
            | Self::MemoryConstraint { recovery, .. }
            | Self::GpuNotAvailable { recovery, .. }
            | Self::BenchmarkTimeout { recovery, .. }
            | Self::ThroughputInsufficient { recovery, .. } => recovery.clone(),
        }
    }
}

/// AuditEntry for hardware operations in L6
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct L6AuditEntry {
    pub timestamp: DateTime<Utc>,
    pub event_id: String,
    pub operation: String,
    pub hardware_tier: String,
    pub error: Option<String>,
    pub resource_available: Option<String>,
    pub resource_used: Option<String>,
}

impl L6AuditEntry {
    pub fn new(operation: String, hardware_tier: String) -> Self {
        Self {
            timestamp: Utc::now(),
            event_id: uuid::Uuid::new_v4().to_string(),
            operation,
            hardware_tier,
            error: None,
            resource_available: None,
            resource_used: None,
        }
    }

    pub fn with_error(mut self, error: L6Error) -> Self {
        self.error = Some(format!("{:?}", error));
        self
    }

    pub fn with_resources(mut self, available: String, used: String) -> Self {
        self.resource_available = Some(available);
        self.resource_used = Some(used);
        self
    }
}

/// Input validation for L6
pub fn validate_memory_gb(memory_gb: f32) -> Result<(), L6Error> {
    if memory_gb <= 0.0 {
        return Err(L6Error::InsufficientResources {
            reason: "Memory must be positive".to_string(),
            recovery: "Check system memory availability".to_string(),
            timestamp: Utc::now(),
        });
    }
    if memory_gb > 1024.0 {
        return Err(L6Error::InsufficientResources {
            reason: "Memory value exceeds realistic maximum (1024GB)".to_string(),
            recovery: "Check hardware detection logic".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

pub fn validate_model_name(model_name: &str) -> Result<(), L6Error> {
    if model_name.is_empty() {
        return Err(L6Error::ModelLoadFailed {
            model_name: model_name.to_string(),
            recovery: "Specify model name (e.g., 'qwen', 'mistral')".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

pub fn validate_throughput_requirement(tok_per_sec: f32) -> Result<(), L6Error> {
    if tok_per_sec <= 0.0 {
        return Err(L6Error::ThroughputInsufficient {
            actual_tok_s: 0.0,
            required_tok_s: tok_per_sec,
            recovery: "Set positive throughput requirement".to_string(),
            timestamp: Utc::now(),
        });
    }
    if tok_per_sec > 1000.0 {
        return Err(L6Error::ThroughputInsufficient {
            actual_tok_s: 0.0,
            required_tok_s: tok_per_sec,
            recovery: "Unrealistic throughput (>1000 tok/s)".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

pub fn validate_timeout_ms(timeout_ms: u64) -> Result<(), L6Error> {
    if timeout_ms == 0 {
        return Err(L6Error::BenchmarkTimeout {
            timeout_ms,
            recovery: "Set timeout > 0ms".to_string(),
            timestamp: Utc::now(),
        });
    }
    if timeout_ms > 300_000 {
        return Err(L6Error::BenchmarkTimeout {
            timeout_ms,
            recovery: "Timeout > 5 minutes is unrealistic".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_validate_memory_gb_negative() {
        let result = validate_memory_gb(-1.0);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_memory_gb_too_large() {
        let result = validate_memory_gb(2000.0);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_memory_gb_valid() {
        let result = validate_memory_gb(8.0);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_model_name_empty() {
        let result = validate_model_name("");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_model_name_valid() {
        let result = validate_model_name("qwen-39");
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_throughput_requirement_negative() {
        let result = validate_throughput_requirement(-5.0);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_throughput_requirement_unrealistic() {
        let result = validate_throughput_requirement(5000.0);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_timeout_ms_zero() {
        let result = validate_timeout_ms(0);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_timeout_ms_too_large() {
        let result = validate_timeout_ms(400_000);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_timeout_ms_valid() {
        let result = validate_timeout_ms(30_000);
        assert!(result.is_ok());
    }

    #[test]
    fn test_audit_entry_with_resources() {
        let entry = L6AuditEntry::new("model_load".to_string(), "tier_2".to_string());
        let entry = entry.with_resources("8GB available".to_string(), "6GB used".to_string());
        assert_eq!(entry.resource_available, Some("8GB available".to_string()));
        assert_eq!(entry.resource_used, Some("6GB used".to_string()));
    }

    #[test]
    fn test_audit_entry_with_error() {
        let entry = L6AuditEntry::new("model_load".to_string(), "tier_1".to_string());
        let error = L6Error::InsufficientResources {
            reason: "OOM".to_string(),
            recovery: "use smaller model".to_string(),
            timestamp: Utc::now(),
        };
        let entry = entry.with_error(error);
        assert!(entry.error.is_some());
    }
}
