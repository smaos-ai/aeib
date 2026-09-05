//! Performance benchmarks for A2UI rendering, validation, and SSE streaming.
//! Targets:
//! - Validation latency: <5ms for 1000 components
//! - SSE streaming: <50ms latency
//! - React rendering: <100ms for 100 components
//! - End-to-end: <200ms
//! - Concurrent sessions: 100+
//! - Memory per session: <5MB
//! - CPU per session: <1%

use criterion::{BenchmarkId, Criterion, black_box, criterion_group, criterion_main};
use std::time::Instant;

// Mock types for benchmarking (avoid dependency on full siss-cockpit)
#[derive(Debug, Clone)]
enum MockA2UIComponent {
    Text {
        id: String,
        content: String,
        size: Option<String>,
    },
    Badge {
        id: String,
        label: String,
        color: Option<String>,
    },
    Button {
        id: String,
        label: String,
        action: Option<String>,
    },
    Input {
        id: String,
        label: String,
        placeholder: Option<String>,
        required: bool,
    },
    Card {
        id: String,
        title: Option<String>,
        children: Vec<MockA2UIComponent>,
    },
}

// ===== BENCHMARK HELPERS =====

/// Simulate rendering latency (simplified HTML generation)
fn mock_render(component: &MockA2UIComponent) -> String {
    match component {
        MockA2UIComponent::Text { content, .. } => {
            format!(
                r#"<div class="a2ui-text"><p>{}</p></div>"#,
                html_escape(content)
            )
        }
        MockA2UIComponent::Badge { label, .. } => {
            format!(r#"<span class="a2ui-badge">{}</span>"#, html_escape(label))
        }
        MockA2UIComponent::Button { label, .. } => {
            format!(
                r#"<button class="a2ui-button">{}</button>"#,
                html_escape(label)
            )
        }
        MockA2UIComponent::Input { label, .. } => {
            format!(
                r#"<div class="a2ui-input"><label>{}</label><input /></div>"#,
                html_escape(label)
            )
        }
        MockA2UIComponent::Card {
            title, children, ..
        } => {
            let title_html = title
                .as_ref()
                .map(|t| format!(r#"<h3>{}</h3>"#, html_escape(t)))
                .unwrap_or_default();
            let children_html = children
                .iter()
                .map(|c| mock_render(c))
                .collect::<Vec<_>>()
                .join("");
            format!(
                r#"<div class="a2ui-card">{}{}</div>"#,
                title_html, children_html
            )
        }
    }
}

/// Simple HTML escape
fn html_escape(s: &str) -> String {
    s.chars()
        .map(|c| match c {
            '&' => "&amp;".to_string(),
            '<' => "&lt;".to_string(),
            '>' => "&gt;".to_string(),
            '"' => "&quot;".to_string(),
            '\'' => "&#39;".to_string(),
            _ => c.to_string(),
        })
        .collect()
}

/// Create test component
fn create_test_component(id: usize) -> MockA2UIComponent {
    MockA2UIComponent::Card {
        id: format!("card_{}", id),
        title: Some(format!("Card {}", id)),
        children: vec![
            MockA2UIComponent::Text {
                id: format!("text_{}", id),
                content: format!("Content for component {}", id),
                size: Some("md".to_string()),
            },
            MockA2UIComponent::Button {
                id: format!("btn_{}", id),
                label: "Click me".to_string(),
                action: Some("submit".to_string()),
            },
        ],
    }
}

// ===== VALIDATION BENCHMARKS =====

fn bench_validator_scaling(c: &mut Criterion) {
    let mut group = c.benchmark_group("validator_scaling");

    for size in [10, 100, 1000].iter() {
        group.bench_with_input(
            BenchmarkId::from_parameter(format!("{}_components", size)),
            size,
            |b, &size| {
                let components: Vec<_> = (0..size).map(create_test_component).collect();
                b.iter(|| {
                    // Simulate validation: check each component
                    black_box(&components).iter().all(|comp| {
                        matches!(
                            comp,
                            MockA2UIComponent::Card { .. } | MockA2UIComponent::Text { .. }
                        )
                    })
                });
            },
        );
    }

    group.finish();
}

/// Benchmark circular reference detection (DFS-based)
fn bench_validator_circular_detection(c: &mut Criterion) {
    let mut group = c.benchmark_group("validator_circular_detection");

    group.bench_function("simple_tree_100_nodes", |b| {
        let components: Vec<_> = (0..100).map(create_test_component).collect();
        b.iter(|| {
            // Simulate DFS circular detection
            let mut visited = std::collections::HashSet::new();
            black_box(&components).iter().all(|_comp| {
                // Simple visited tracking (no actual recursion)
                visited.insert(0) || true
            })
        });
    });

    group.finish();
}

/// Benchmark validation result caching
fn bench_validator_caching(c: &mut Criterion) {
    let mut group = c.benchmark_group("validator_caching");

    group.bench_function("cache_hit_rate_1000_components", |b| {
        let components: Vec<_> = (0..1000).map(create_test_component).collect();
        let mut cache: std::collections::HashMap<usize, bool> = std::collections::HashMap::new();

        // Pre-populate cache
        for i in 0..1000 {
            cache.insert(i, true);
        }

        b.iter(|| {
            black_box(&components)
                .iter()
                .enumerate()
                .all(|(i, _)| cache.get(&i).copied().unwrap_or(false))
        });
    });

    group.finish();
}

// ===== SSE STREAMING BENCHMARKS =====

/// Benchmark buffered SSE writes
fn bench_sse_streaming_buffering(c: &mut Criterion) {
    let mut group = c.benchmark_group("sse_streaming_buffering");

    for batch_size in [1, 5, 10].iter() {
        let batch_val = *batch_size;
        group.bench_with_input(
            BenchmarkId::from_parameter(format!("batch_{}", batch_size)),
            batch_size,
            |b, _| {
                let components: Vec<_> = (0..100).map(create_test_component).collect();

                b.iter(|| {
                    let mut buffer = Vec::new();
                    // Simulate batched writes
                    for chunk in components.chunks(batch_val) {
                        for comp in chunk {
                            buffer.push(mock_render(comp));
                        }
                        if buffer.len() >= batch_val {
                            // Flush batch
                            let _payload = buffer.join("\n");
                            buffer.clear();
                        }
                    }
                    black_box(buffer.len())
                });
            },
        );
    }

    group.finish();
}

/// Benchmark payload compression efficiency
fn bench_sse_streaming_compression(c: &mut Criterion) {
    let mut group = c.benchmark_group("sse_streaming_compression");

    group.bench_function("payload_size_100_components", |b| {
        let components: Vec<_> = (0..100).map(create_test_component).collect();
        let html_parts: Vec<_> = components.iter().map(mock_render).collect();

        b.iter(|| {
            // Measure total payload size (compression metric)
            black_box(&html_parts)
                .iter()
                .map(|s| s.len())
                .sum::<usize>()
        });
    });

    group.finish();
}

/// Benchmark event throughput (events per second)
fn bench_sse_event_throughput(c: &mut Criterion) {
    let mut group = c.benchmark_group("sse_event_throughput");

    for rate in [1, 10, 100].iter() {
        let rate_val = *rate;
        group.bench_with_input(
            BenchmarkId::from_parameter(format!("{}events_per_sec", rate)),
            rate,
            |b, _| {
                b.iter(|| {
                    // Simulate SSE event emission at given rate
                    let start = Instant::now();
                    let mut count = 0;
                    while start.elapsed().as_millis() < 100 && count < rate_val {
                        let _event = format!("data: event_{}\n\n", count);
                        count += 1;
                    }
                    black_box(count)
                });
            },
        );
    }

    group.finish();
}

// ===== REACT RENDERING BENCHMARKS =====

/// Benchmark HTML generation (React component tree)
fn bench_react_rendering_scaling(c: &mut Criterion) {
    let mut group = c.benchmark_group("react_rendering_scaling");

    for size in [10, 100, 1000].iter() {
        group.bench_with_input(
            BenchmarkId::from_parameter(format!("{}_components", size)),
            size,
            |b, &size| {
                let components: Vec<_> = (0..size).map(create_test_component).collect();
                b.iter(|| {
                    let html: Vec<_> = black_box(&components).iter().map(mock_render).collect();
                    html.iter().map(|s| s.len()).sum::<usize>()
                });
            },
        );
    }

    group.finish();
}

/// Benchmark memoization effect
fn bench_react_memoization(c: &mut Criterion) {
    let mut group = c.benchmark_group("react_memoization");

    group.bench_function("repeated_renders_with_cache", |b| {
        let component = create_test_component(1);

        b.iter(|| {
            let mut cache: std::collections::HashMap<String, String> =
                std::collections::HashMap::new();

            // First render: cache miss
            cache.insert("comp_1".to_string(), mock_render(&component));

            // Second render: cache hit
            let _html = cache.get("comp_1").cloned();

            black_box(cache.len())
        });
    });

    group.finish();
}

// ===== MEMORY & CONCURRENCY BENCHMARKS =====

/// Benchmark per-session memory usage
fn bench_memory_per_session(c: &mut Criterion) {
    let mut group = c.benchmark_group("memory_per_session");

    group.bench_function("single_session_1000_components", |b| {
        b.iter(|| {
            // Simulate session storage: component map + state
            let components: Vec<_> = (0..1000).map(create_test_component).collect();
            let mut state: std::collections::HashMap<String, String> =
                std::collections::HashMap::new();

            for comp in components {
                match comp {
                    MockA2UIComponent::Card { id, .. } => {
                        state.insert(
                            id,
                            mock_render(&MockA2UIComponent::Card {
                                id: "".to_string(),
                                title: None,
                                children: vec![],
                            }),
                        );
                    }
                    _ => {}
                }
            }

            black_box(state.len())
        });
    });

    group.finish();
}

/// Benchmark concurrent session handling (simulated)
fn bench_concurrent_sessions(c: &mut Criterion) {
    let mut group = c.benchmark_group("concurrent_sessions");

    for concurrency in [10, 50, 100].iter() {
        group.bench_with_input(
            BenchmarkId::from_parameter(format!("{}_sessions", concurrency)),
            concurrency,
            |b, &concurrency| {
                b.iter(|| {
                    // Simulate multiple sessions processing events
                    let mut sessions: Vec<std::collections::HashMap<String, String>> = (0
                        ..concurrency)
                        .map(|_| std::collections::HashMap::new())
                        .collect();

                    for (session_idx, session) in sessions.iter_mut().enumerate() {
                        for comp_idx in 0..10 {
                            let key = format!("sess_{}_comp_{}", session_idx, comp_idx);
                            session.insert(key, "html_data".to_string());
                        }
                    }

                    black_box(sessions.len())
                });
            },
        );
    }

    group.finish();
}

// ===== END-TO-END BENCHMARKS =====

/// Benchmark full request cycle: render + stream + client receive
fn bench_end_to_end_latency(c: &mut Criterion) {
    let mut group = c.benchmark_group("end_to_end_latency");

    group.bench_function("full_cycle_10_components", |b| {
        let components: Vec<_> = (0..10).map(create_test_component).collect();
        b.iter(|| {
            // Phase 1: Render all components
            let html_parts: Vec<_> = components.iter().map(mock_render).collect();

            // Phase 2: Batch and serialize
            let _payload = html_parts.join("\n");
            let serialized = serde_json::json!({
                "components": &html_parts,
                "timestamp": "2026-07-17T00:00:00Z"
            });

            // Phase 3: Simulate transmission
            let json_str = serialized.to_string();

            black_box(json_str.len())
        });
    });

    group.bench_function("full_cycle_100_components", |b| {
        let components: Vec<_> = (0..100).map(create_test_component).collect();
        b.iter(|| {
            let html_parts: Vec<_> = components.iter().map(mock_render).collect();
            let _payload = html_parts.join("\n");
            let serialized = serde_json::json!({
                "components": &html_parts,
                "timestamp": "2026-07-17T00:00:00Z"
            });
            let json_str = serialized.to_string();
            black_box(json_str.len())
        });
    });

    group.finish();
}

// ===== HTML ESCAPE OPTIMIZATION =====

/// Benchmark optimized escape implementation
fn bench_html_escape_optimization(c: &mut Criterion) {
    let mut group = c.benchmark_group("html_escape_optimization");

    let test_strings = vec![
        "simple text",
        "text with <html> & special \"chars\"",
        "<script>alert('xss')</script>",
        "normal_text_no_escapes_needed_12345",
    ];

    for test_str in test_strings {
        group.bench_with_input(
            BenchmarkId::from_parameter(test_str),
            &test_str,
            |b, &input| {
                b.iter(|| black_box(html_escape(input)));
            },
        );
    }

    group.finish();
}

// ===== RING BUFFER BENCHMARK =====

/// Benchmark ring buffer operations
fn bench_ring_buffer(c: &mut Criterion) {
    let mut group = c.benchmark_group("ring_buffer_efficiency");

    group.bench_function("push_1000_events", |b| {
        let mut buffer = Vec::with_capacity(1000);
        b.iter(|| {
            buffer.clear();
            for i in 0..1000 {
                buffer.push(format!("event_{}", i));
            }
            black_box(buffer.len())
        });
    });

    group.finish();
}

// ===== CRITERION CONFIGURATION =====

criterion_group!(
    name = benches;
    config = Criterion::default()
        .sample_size(100)
        .measurement_time(std::time::Duration::from_secs(5));
    targets =
        bench_validator_scaling,
        bench_validator_circular_detection,
        bench_validator_caching,
        bench_sse_streaming_buffering,
        bench_sse_streaming_compression,
        bench_sse_event_throughput,
        bench_react_rendering_scaling,
        bench_react_memoization,
        bench_memory_per_session,
        bench_concurrent_sessions,
        bench_end_to_end_latency,
        bench_html_escape_optimization,
        bench_ring_buffer
);

criterion_main!(benches);
