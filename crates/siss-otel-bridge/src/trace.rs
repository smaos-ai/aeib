use crate::W3CTraceContext;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

/// Span event
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SpanEvent {
    pub name: String,
    pub timestamp: i64,
    pub attributes: std::collections::HashMap<String, String>,
}

/// Span in trace
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Span {
    pub trace_ctx: W3CTraceContext,
    pub span_id: String,
    pub name: String,
    pub start_time: i64,
    pub end_time: Option<i64>,
    pub status: String,
    pub events: Vec<SpanEvent>,
    pub attributes: std::collections::HashMap<String, String>,
}

impl Span {
    /// Create new span
    pub fn new(name: String, trace_ctx: W3CTraceContext) -> Self {
        Self {
            span_id: format!("{:016x}", rand::random::<u64>()),
            trace_ctx,
            name,
            start_time: chrono::Utc::now().timestamp_millis(),
            end_time: None,
            status: "UNSET".to_string(),
            events: Vec::new(),
            attributes: std::collections::HashMap::new(),
        }
    }

    /// Add event to span
    pub fn add_event(&mut self, name: String) {
        let event = SpanEvent {
            name,
            timestamp: chrono::Utc::now().timestamp_millis(),
            attributes: std::collections::HashMap::new(),
        };
        self.events.push(event);
    }

    /// End span
    pub fn end(&mut self) {
        self.end_time = Some(chrono::Utc::now().timestamp_millis());
        self.status = "OK".to_string();
    }

    /// Duration in ms
    pub fn duration_ms(&self) -> Option<i64> {
        self.end_time.map(|et| et - self.start_time)
    }

    /// Merkle hash of span (for proof stitching)
    pub fn merkle_hash(&self) -> Vec<u8> {
        let mut hasher = Sha256::new();
        hasher.update(self.trace_ctx.trace_id.as_bytes());
        hasher.update(self.span_id.as_bytes());
        hasher.update(self.start_time.to_le_bytes());
        if let Some(et) = self.end_time {
            hasher.update(et.to_le_bytes());
        }
        hasher.finalize().to_vec()
    }
}

/// Trace context
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TraceContext {
    pub w3c: W3CTraceContext,
    pub spans: Vec<Span>,
}

impl TraceContext {
    /// Create new trace
    pub fn new() -> Self {
        Self {
            w3c: W3CTraceContext::new(),
            spans: Vec::new(),
        }
    }

    /// Add span to trace
    pub fn add_span(&mut self, span: Span) {
        self.spans.push(span);
    }

    /// Total duration across all spans
    pub fn total_duration_ms(&self) -> i64 {
        self.spans
            .iter()
            .filter_map(|s| s.duration_ms())
            .sum()
    }
}

impl Default for TraceContext {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_span_creation() {
        let trace_ctx = W3CTraceContext::new();
        let span = Span::new("test-span".to_string(), trace_ctx);
        assert_eq!(span.name, "test-span");
        assert_eq!(span.status, "UNSET");
    }

    #[test]
    fn test_span_lifecycle() {
        let trace_ctx = W3CTraceContext::new();
        let mut span = Span::new("test".to_string(), trace_ctx);
        assert!(span.end_time.is_none());

        span.end();
        assert!(span.end_time.is_some());
        assert_eq!(span.status, "OK");
    }

    #[test]
    fn test_span_events() {
        let trace_ctx = W3CTraceContext::new();
        let mut span = Span::new("test".to_string(), trace_ctx);
        span.add_event("event1".to_string());
        span.add_event("event2".to_string());
        assert_eq!(span.events.len(), 2);
    }

    #[test]
    fn test_trace_context() {
        let mut trace = TraceContext::new();
        let span = Span::new("test".to_string(), trace.w3c.clone());
        trace.add_span(span);
        assert_eq!(trace.spans.len(), 1);
    }

    #[test]
    fn test_span_merkle_hash() {
        let trace_ctx = W3CTraceContext::new();
        let span = Span::new("test".to_string(), trace_ctx);
        let hash = span.merkle_hash();
        assert!(!hash.is_empty());
    }
}
