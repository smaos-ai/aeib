use siss_observability::{
    MerkleTracer, TraceSpan, MetricsAggregator, TraceLogger, Metrics,
};
use uuid::Uuid;

// Group 1-5: Span recording and parent-child linkage
#[tokio::test]
async fn test_1_record_single_span() {
    let tracer = MerkleTracer::new();
    let span = TraceSpan::new(Uuid::new_v4(), None);

    assert!(tracer.record_span(span).await.is_ok());
    assert_eq!(tracer.span_count(), 1);
}

#[tokio::test]
async fn test_2_parent_child_relationship() {
    let tracer = MerkleTracer::new();
    let parent_id = Uuid::new_v4();
    let parent = TraceSpan::new(parent_id, None);

    tracer.record_span(parent).await.unwrap();

    let child = TraceSpan::new(Uuid::new_v4(), Some(parent_id));
    assert!(tracer.record_span(child).await.is_ok());
    assert_eq!(tracer.span_count(), 2);
}

#[tokio::test]
async fn test_3_trace_chain_reconstruction() {
    let tracer = MerkleTracer::new();

    let g_id = Uuid::new_v4();
    tracer.record_span(TraceSpan::new(g_id, None)).await.unwrap();

    let p_id = Uuid::new_v4();
    tracer.record_span(TraceSpan::new(p_id, Some(g_id))).await.unwrap();

    let c_id = Uuid::new_v4();
    tracer.record_span(TraceSpan::new(c_id, Some(p_id))).await.unwrap();

    let chain = tracer.get_trace_chain(c_id).unwrap();
    assert_eq!(chain.len(), 3);
    assert_eq!(chain[0].span_id, g_id);
    assert_eq!(chain[1].span_id, p_id);
    assert_eq!(chain[2].span_id, c_id);
}

#[tokio::test]
async fn test_4_multiple_children_single_parent() {
    let tracer = MerkleTracer::new();
    let parent_id = Uuid::new_v4();
    tracer.record_span(TraceSpan::new(parent_id, None)).await.unwrap();

    for _ in 0..5 {
        let child = TraceSpan::new(Uuid::new_v4(), Some(parent_id));
        tracer.record_span(child).await.unwrap();
    }

    assert_eq!(tracer.span_count(), 6);
}

#[tokio::test]
async fn test_5_get_span_by_id() {
    let tracer = MerkleTracer::new();
    let span_id = Uuid::new_v4();
    let span = TraceSpan::new(span_id, None);

    tracer.record_span(span).await.unwrap();
    let retrieved = tracer.get_span(span_id);

    assert!(retrieved.is_some());
    assert_eq!(retrieved.unwrap().span_id, span_id);
}

// Group 6-10: Metrics aggregation (latency, throughput, error rates)
#[tokio::test]
async fn test_6_record_single_metric() {
    let agg = MetricsAggregator::new();
    let span_id = Uuid::new_v4();
    let metric = Metrics {
        latency_ms: 50.0,
        throughput: 100.0,
        error_rate: 1.0,
        request_count: 1000,
        error_count: 10,
    };

    agg.record_metric(span_id, metric);
    assert_eq!(agg.metric_count(), 1);
}

#[tokio::test]
async fn test_7_aggregate_latency_metrics() {
    let agg = MetricsAggregator::new();
    let span_id = Uuid::new_v4();

    for latency in [10.0, 20.0, 30.0, 40.0, 50.0].iter() {
        let metric = Metrics {
            latency_ms: *latency,
            throughput: 100.0,
            error_rate: 0.0,
            request_count: 100,
            error_count: 0,
        };
        agg.record_metric(span_id, metric);
    }

    let result = agg.aggregate(span_id).unwrap();
    assert!((result.avg_latency_ms - 30.0).abs() < 0.1);
    assert_eq!(result.min_latency_ms, 10.0);
    assert_eq!(result.max_latency_ms, 50.0);
}

#[tokio::test]
async fn test_8_error_rate_calculation() {
    let agg = MetricsAggregator::new();
    let span_id = Uuid::new_v4();

    let metric = Metrics {
        latency_ms: 50.0,
        throughput: 100.0,
        error_rate: 5.0,
        request_count: 1000,
        error_count: 50,
    };

    agg.record_metric(span_id, metric);
    let result = agg.aggregate(span_id).unwrap();

    assert!((result.error_rate - 5.0).abs() < 0.1);
}

#[tokio::test]
async fn test_9_p99_latency_percentile() {
    let agg = MetricsAggregator::new();
    let span_id = Uuid::new_v4();

    for i in 1..=100 {
        let metric = Metrics {
            latency_ms: i as f64,
            throughput: 100.0,
            error_rate: 0.0,
            request_count: 1,
            error_count: 0,
        };
        agg.record_metric(span_id, metric);
    }

    let result = agg.aggregate(span_id).unwrap();
    assert!(result.p99_latency_ms >= 99.0);
}

#[tokio::test]
async fn test_10_throughput_aggregation() {
    let agg = MetricsAggregator::new();
    let span_id = Uuid::new_v4();

    agg.record_metric(span_id, Metrics {
        latency_ms: 50.0,
        throughput: 1000.0,
        error_rate: 0.0,
        request_count: 100,
        error_count: 0,
    });

    agg.record_metric(span_id, Metrics {
        latency_ms: 60.0,
        throughput: 500.0,
        error_rate: 0.0,
        request_count: 100,
        error_count: 0,
    });

    let result = agg.aggregate(span_id).unwrap();
    assert!(result.throughput_rps > 0.0);
}

// Group 11-15: Merkle-chain verification, tamper detection
#[tokio::test]
async fn test_11_merkle_integrity_valid() {
    let tracer = MerkleTracer::new();

    tracer.record_span(TraceSpan::new(Uuid::new_v4(), None)).await.unwrap();
    let is_valid = tracer.verify_trace_integrity().await.unwrap();

    assert!(is_valid);
}

#[tokio::test]
async fn test_12_merkle_root_uniqueness() {
    let tracer = MerkleTracer::new();
    let root1 = tracer.get_merkle_root();

    tracer.record_span(TraceSpan::new(Uuid::new_v4(), None)).await.unwrap();
    let root2 = tracer.get_merkle_root();

    assert_ne!(root1, root2);
}

#[tokio::test]
async fn test_13_merkle_hash_deterministic() {
    let span_id = Uuid::new_v4();
    let parent_id = Uuid::new_v4();
    let previous_hash = [42u8; 32];

    let hash1 = TraceSpan::compute_hash(&span_id, Some(&parent_id), &previous_hash);
    let hash2 = TraceSpan::compute_hash(&span_id, Some(&parent_id), &previous_hash);

    assert_eq!(hash1, hash2);
}

#[tokio::test]
async fn test_14_tampering_detection_clean() {
    let tracer = MerkleTracer::new();

    tracer.record_span(TraceSpan::new(Uuid::new_v4(), None)).await.unwrap();
    tracer.record_span(TraceSpan::new(Uuid::new_v4(), None)).await.unwrap();

    let is_tampered = tracer.detect_tampering().unwrap();
    assert!(!is_tampered);
}

#[tokio::test]
async fn test_15_chain_integrity_multispan() {
    let tracer = MerkleTracer::new();
    let span1_id = Uuid::new_v4();
    let span2_id = Uuid::new_v4();
    let span3_id = Uuid::new_v4();

    tracer.record_span(TraceSpan::new(span1_id, None)).await.unwrap();
    tracer.record_span(TraceSpan::new(span2_id, Some(span1_id))).await.unwrap();
    tracer.record_span(TraceSpan::new(span3_id, Some(span2_id))).await.unwrap();

    let valid = tracer.verify_trace_integrity().await.unwrap();
    assert!(valid);
}

// Group 16-20: Concurrent tracing, high-throughput logging, query performance
#[tokio::test]
async fn test_16_concurrent_span_recording() {
    let tracer = std::sync::Arc::new(MerkleTracer::new());
    let mut handles = vec![];

    for _ in 0..10 {
        let tracer_clone = tracer.clone();
        let handle = tokio::spawn(async move {
            let span = TraceSpan::new(Uuid::new_v4(), None);
            tracer_clone.record_span(span).await
        });
        handles.push(handle);
    }

    for handle in handles {
        assert!(handle.await.unwrap().is_ok());
    }

    assert_eq!(tracer.span_count(), 10);
}

#[tokio::test]
async fn test_17_high_throughput_metrics() {
    let agg = MetricsAggregator::new();
    let span_id = Uuid::new_v4();

    for i in 0..1000 {
        let metric = Metrics {
            latency_ms: (i % 100) as f64,
            throughput: 10000.0,
            error_rate: 0.5,
            request_count: 100,
            error_count: 1,
        };
        agg.record_metric(span_id, metric);
    }

    let result = agg.aggregate(span_id).unwrap();
    assert_eq!(result.total_requests, 100_000);
    assert!(result.throughput_rps > 0.0);
}

#[tokio::test]
async fn test_18_logger_concurrent_writes() {
    let logger = std::sync::Arc::new(TraceLogger::new());
    let mut handles = vec![];

    for i in 0..10 {
        let logger_clone = logger.clone();
        let handle = tokio::spawn(async move {
            let span_id = Uuid::new_v4();
            logger_clone.info(span_id, format!("Message {}", i), None);
        });
        handles.push(handle);
    }

    for handle in handles {
        handle.await.unwrap();
    }

    assert_eq!(logger.global_log_count(), 10);
}

#[tokio::test]
async fn test_19_query_all_spans() {
    let tracer = MerkleTracer::new();

    for _ in 0..50 {
        tracer.record_span(TraceSpan::new(Uuid::new_v4(), None)).await.unwrap();
    }

    let all_spans = tracer.get_all_spans();
    assert_eq!(all_spans.len(), 50);
}

#[tokio::test]
async fn test_20_integrated_tracing_and_logging() {
    let tracer = MerkleTracer::new();
    let logger = TraceLogger::new();
    let agg = MetricsAggregator::new();

    let span1_id = Uuid::new_v4();
    let span1 = TraceSpan::new(span1_id, None);
    tracer.record_span(span1).await.unwrap();

    logger.info(span1_id, "Span 1 started".to_string(), None);
    agg.record_metric(span1_id, Metrics {
        latency_ms: 45.0,
        throughput: 500.0,
        error_rate: 0.0,
        request_count: 500,
        error_count: 0,
    });

    let span2_id = Uuid::new_v4();
    let span2 = TraceSpan::new(span2_id, Some(span1_id));
    tracer.record_span(span2).await.unwrap();

    logger.info(span2_id, "Span 2 started".to_string(), Some("child".to_string()));
    agg.record_metric(span2_id, Metrics {
        latency_ms: 25.0,
        throughput: 1000.0,
        error_rate: 0.0,
        request_count: 1000,
        error_count: 0,
    });

    // Verify integration
    assert_eq!(tracer.span_count(), 2);
    assert_eq!(logger.global_log_count(), 2);
    assert_eq!(agg.metric_count(), 2);

    // Verify chain
    let chain = tracer.get_trace_chain(span2_id).unwrap();
    assert_eq!(chain.len(), 2);

    // Verify integrity
    let valid = tracer.verify_trace_integrity().await.unwrap();
    assert!(valid);

    // Verify metrics
    let m1 = agg.aggregate(span1_id).unwrap();
    assert_eq!(m1.total_requests, 500);

    let m2 = agg.aggregate(span2_id).unwrap();
    assert_eq!(m2.total_requests, 1000);
}
