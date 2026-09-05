#[cfg(test)]
mod integration_tests {
    use crate::{OtelConfig, TraceContext, SLAThreshold, SLAMonitor, Span};

    #[test]
    fn test_otel_trace_context_serialization() {
        let _config = OtelConfig::new("test-service".to_string()).unwrap();
        let trace = TraceContext::new();

        let serialized = serde_json::to_string(&trace).unwrap();
        let deserialized: TraceContext = serde_json::from_str(&serialized).unwrap();

        assert_eq!(trace.w3c.trace_id, deserialized.w3c.trace_id);
    }

    #[test]
    fn test_otel_multi_span_trace() {
        let mut trace = TraceContext::new();

        for i in 0..5 {
            let span = Span::new(
                format!("span-{}", i),
                trace.w3c.clone(),
            );
            trace.add_span(span);
        }

        assert_eq!(trace.spans.len(), 5);
    }

    #[test]
    fn test_sla_monitoring_integration() {
        let threshold = SLAThreshold::default();
        let monitor = SLAMonitor::new(threshold);

        for i in 0..10 {
            monitor.record_latency((i * 100) as u32);
        }

        let metrics = monitor.get_metrics();
        assert_eq!(metrics.latencies_ms.len(), 10);
    }

    #[test]
    fn test_otel_trace_with_events() {
        let mut trace = TraceContext::new();
        let mut span = Span::new("test-span".to_string(), trace.w3c.clone());

        span.add_event("event1".to_string());
        span.add_event("event2".to_string());
        span.add_event("event3".to_string());
        span.end();

        assert_eq!(span.events.len(), 3);
        assert!(span.duration_ms().is_some());
    }
}
