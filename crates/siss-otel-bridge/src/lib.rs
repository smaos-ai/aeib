//! # SISS OTEL Bridge
//! W3C Trace Context propagation and SLA monitoring with Merkle trace stitching.
//!
//! Integration point for Phase 1 L8 (proof layer) - marked for Jun 2027.

pub mod trace;
pub mod context;
pub mod sla;
pub mod error;

pub use trace::{TraceContext, Span};
pub use context::W3CTraceContext;
pub use sla::{SLAMonitor, SLAThreshold};
pub use error::{OtelError, Result};

#[cfg(test)]
mod tests;

/// OTEL Bridge configuration
#[derive(Clone, Debug)]
pub struct OtelConfig {
    /// Service name
    pub service_name: String,
    /// Trace sampling rate (0.0-1.0)
    pub sample_rate: f64,
    /// Trace batch size
    pub batch_size: u32,
    /// Flush interval (ms)
    pub flush_interval_ms: u64,
}

impl OtelConfig {
    /// Create new OTEL config
    pub fn new(service_name: String) -> Result<Self> {
        if service_name.is_empty() {
            return Err(OtelError::InvalidConfig("empty service name".into()));
        }
        Ok(Self {
            service_name,
            sample_rate: 0.1,
            batch_size: 100,
            flush_interval_ms: 5000,
        })
    }

    /// Set sampling rate
    pub fn with_sample_rate(mut self, rate: f64) -> Result<Self> {
        if !(0.0..=1.0).contains(&rate) {
            return Err(OtelError::InvalidConfig("sample rate must be 0-1".into()));
        }
        self.sample_rate = rate;
        Ok(self)
    }
}

#[cfg(test)]
mod config_tests {
    use super::*;

    #[test]
    fn test_otel_config_validation() {
        assert!(OtelConfig::new("".to_string()).is_err());
        assert!(OtelConfig::new("test-service".to_string()).is_ok());
    }

    #[test]
    fn test_otel_sample_rate() {
        let config = OtelConfig::new("test".to_string()).unwrap();
        assert!(config.with_sample_rate(0.5).is_ok());

        let config = OtelConfig::new("test".to_string()).unwrap();
        assert!(config.with_sample_rate(1.5).is_err());
    }
}
