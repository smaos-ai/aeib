use crate::error::{OtelError, Result};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// W3C Trace Context header
/// Format: traceparent: 00-traceid-parentid-flags
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct W3CTraceContext {
    /// W3C trace ID (16 bytes hex)
    pub trace_id: String,
    /// Parent span ID (8 bytes hex)
    pub parent_id: String,
    /// Trace flags (sampled, debug)
    pub flags: u8,
    /// Version (00 for W3C v1)
    pub version: u8,
}

impl W3CTraceContext {
    /// Create new trace context
    pub fn new() -> Self {
        Self {
            trace_id: Self::generate_trace_id(),
            parent_id: Self::generate_span_id(),
            flags: 0x01, // Sampled
            version: 0x00,
        }
    }

    /// Parse traceparent header
    pub fn from_header(header: &str) -> Result<Self> {
        let parts: Vec<&str> = header.split('-').collect();
        if parts.len() != 4 {
            return Err(OtelError::TraceError("Invalid traceparent format".into()));
        }

        let version = u8::from_str_radix(parts[0], 16)
            .map_err(|_| OtelError::TraceError("Invalid version".into()))?;
        let flags = u8::from_str_radix(parts[3], 16)
            .map_err(|_| OtelError::TraceError("Invalid flags".into()))?;

        Ok(Self {
            trace_id: parts[1].to_string(),
            parent_id: parts[2].to_string(),
            flags,
            version,
        })
    }

    /// Serialize to W3C traceparent header
    pub fn to_header(&self) -> String {
        format!(
            "{:02x}-{}-{}-{:02x}",
            self.version, self.trace_id, self.parent_id, self.flags
        )
    }

    /// Check if trace is sampled
    pub fn is_sampled(&self) -> bool {
        (self.flags & 0x01) != 0
    }

    /// Generate new trace ID (16 hex chars)
    fn generate_trace_id() -> String {
        format!("{:032x}", rand::random::<u128>())
    }

    /// Generate new span ID (16 hex chars)
    fn generate_span_id() -> String {
        format!("{:016x}", rand::random::<u64>())
    }

    /// Create child span context
    pub fn child_span(&self) -> Self {
        Self {
            trace_id: self.trace_id.clone(),
            parent_id: Self::generate_span_id(),
            flags: self.flags,
            version: self.version,
        }
    }
}

impl Default for W3CTraceContext {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_w3c_creation() {
        let ctx = W3CTraceContext::new();
        assert_eq!(ctx.version, 0x00);
        assert!(ctx.is_sampled());
    }

    #[test]
    fn test_w3c_to_header() {
        let ctx = W3CTraceContext::new();
        let header = ctx.to_header();
        assert!(header.starts_with("00-"));
    }

    #[test]
    fn test_w3c_from_header() {
        let original = W3CTraceContext::new();
        let header = original.to_header();
        let parsed = W3CTraceContext::from_header(&header).unwrap();
        assert_eq!(parsed.version, original.version);
    }

    #[test]
    fn test_w3c_child_span() {
        let parent = W3CTraceContext::new();
        let child = parent.child_span();
        assert_eq!(child.trace_id, parent.trace_id);
        assert_ne!(child.parent_id, parent.parent_id);
    }

    #[test]
    fn test_w3c_invalid_header() {
        let result = W3CTraceContext::from_header("invalid");
        assert!(result.is_err());
    }
}
