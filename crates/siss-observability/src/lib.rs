pub mod merkle_tracer;
pub mod metrics_aggregator;
pub mod trace_logger;

pub use merkle_tracer::{MerkleTracer, TraceSpan};
pub use metrics_aggregator::MetricsAggregator;
pub use trace_logger::{LogLevel, TraceLogger};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SpanStatus {
    Started,
    Running,
    Completed,
    Failed,
}

#[derive(Debug, Clone)]
pub struct Metrics {
    pub latency_ms: f64,
    pub throughput: f64,
    pub error_rate: f64,
    pub request_count: u64,
    pub error_count: u64,
}

impl Metrics {
    pub fn new() -> Self {
        Self {
            latency_ms: 0.0,
            throughput: 0.0,
            error_rate: 0.0,
            request_count: 0,
            error_count: 0,
        }
    }
}

impl Default for Metrics {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Debug, thiserror::Error)]
pub enum ObservabilityError {
    #[error("Merkle verification failed")]
    MerkleVerificationFailed,
    #[error("Trace not found: {0}")]
    TraceNotFound(String),
    #[error("Invalid span: {0}")]
    InvalidSpan(String),
    #[error("Integrity check failed: {0}")]
    IntegrityCheckFailed(String),
}

pub type Result<T> = std::result::Result<T, ObservabilityError>;
