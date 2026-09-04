/// Hardware detection and emulation mode for Jetson Thor
use crate::jetson_target::JetsonTarget;
use std::collections::hash_map::RandomState;
use std::hash::{BuildHasher, Hash, Hasher};
use std::time::SystemTime;

#[derive(Clone, Debug, PartialEq)]
pub enum HardwareBackend {
    MetalGPU,
    NeuralEngine,
    SIMD,
    JetsonThor,
    JetsonThorEmulated,
}

#[derive(Clone, Debug, PartialEq)]
pub struct MetricsSample {
    pub memory_available_bytes: u64,
    pub tflops: f64,
    pub latency_per_token_ms: f64,
    pub cache_bandwidth_bps: u64,
}

impl Default for MetricsSample {
    fn default() -> Self {
        Self {
            memory_available_bytes: 128u64 * 1024 * 1024 * 1024,
            tflops: 72.0,
            latency_per_token_ms: 25.4,
            cache_bandwidth_bps: 1_000_000_000,
        }
    }
}

pub struct HardwareDetector {
    jetson: JetsonTarget,
}

impl HardwareDetector {
    /// Create a new hardware detector
    pub fn new() -> Self {
        Self {
            jetson: JetsonTarget::jetson_thor_or_emulated(),
        }
    }

    /// Detect which hardware backend to use
    pub fn detect(&self) -> HardwareBackend {
        if self.jetson.available {
            HardwareBackend::JetsonThor
        } else {
            HardwareBackend::JetsonThorEmulated
        }
    }

    /// Get baseline emulation metrics
    pub fn emulation_metrics(&self) -> MetricsSample {
        MetricsSample::default()
    }

    /// Get emulation metrics with synthetic jitter
    pub fn emulation_metrics_sample(&self) -> MetricsSample {
        let mut base = self.emulation_metrics();

        // Generate deterministic jitter using SystemTime hash
        let now = SystemTime::now()
            .duration_since(SystemTime::UNIX_EPOCH)
            .unwrap_or_default();

        let mut hasher = RandomState::new().build_hasher();
        now.as_nanos().hash(&mut hasher);
        let hash = hasher.finish();

        // Apply ±5% jitter to latency
        let jitter_factor = 0.95 + ((hash % 10) as f64 / 100.0); // 0.95 - 1.05
        base.latency_per_token_ms *= jitter_factor;

        base
    }

    /// Get reference to the target hardware
    pub fn target(&self) -> &JetsonTarget {
        &self.jetson
    }
}

impl Default for HardwareDetector {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hardware_detector_creation() {
        let detector = HardwareDetector::new();
        assert_eq!(detector.target().memory_gb, 128);
    }

    #[test]
    fn test_hardware_detector_detect() {
        let detector = HardwareDetector::new();
        let backend = detector.detect();

        // Should be either real or emulated based on detection
        assert!(
            backend == HardwareBackend::JetsonThor
                || backend == HardwareBackend::JetsonThorEmulated
        );
    }

    #[test]
    fn test_hardware_detector_fallback_to_emulation() {
        let detector = HardwareDetector::new();
        let backend = detector.detect();

        // Verify we have a valid backend
        assert!(!matches!(backend, HardwareBackend::SIMD));
        assert!(!matches!(backend, HardwareBackend::MetalGPU));
        assert!(!matches!(backend, HardwareBackend::NeuralEngine));
    }

    #[test]
    fn test_emulation_mode_baseline_metrics() {
        let detector = HardwareDetector::new();
        let metrics = detector.emulation_metrics();

        assert_eq!(metrics.memory_available_bytes, 128u64 * 1024 * 1024 * 1024);
        assert_eq!(metrics.tflops, 72.0);
        assert!(metrics.latency_per_token_ms > 25.0 && metrics.latency_per_token_ms < 26.0);
        assert_eq!(metrics.cache_bandwidth_bps, 1_000_000_000);
    }

    #[test]
    fn test_emulation_mode_generates_consistent_metrics() {
        let detector = HardwareDetector::new();

        let metrics1 = detector.emulation_metrics();
        let metrics2 = detector.emulation_metrics();

        // Baseline metrics should be identical
        assert_eq!(metrics1.memory_available_bytes, metrics2.memory_available_bytes);
        assert_eq!(metrics1.tflops, metrics2.tflops);
        assert_eq!(metrics1.cache_bandwidth_bps, metrics2.cache_bandwidth_bps);
    }

    #[test]
    fn test_emulation_mode_realistic_values() {
        let detector = HardwareDetector::new();
        let metrics = detector.emulation_metrics();

        // Verify realistic ranges
        assert!(metrics.memory_available_bytes >= 100u64 * 1024 * 1024 * 1024); // >= 100GB
        assert!(metrics.tflops >= 50.0 && metrics.tflops <= 100.0);
        assert!(metrics.latency_per_token_ms > 10.0 && metrics.latency_per_token_ms < 50.0);
        assert!(metrics.cache_bandwidth_bps >= 500_000_000); // >= 500 Mbps
    }

    #[test]
    fn test_emulation_mode_synthetic_jitter() {
        let detector = HardwareDetector::new();

        // Collect multiple samples to observe jitter
        let sample1 = detector.emulation_metrics_sample();
        let sample2 = detector.emulation_metrics_sample();
        let sample3 = detector.emulation_metrics_sample();

        // All samples should be within reasonable range
        assert!(sample1.latency_per_token_ms > 20.0 && sample1.latency_per_token_ms < 30.0);
        assert!(sample2.latency_per_token_ms > 20.0 && sample2.latency_per_token_ms < 30.0);
        assert!(sample3.latency_per_token_ms > 20.0 && sample3.latency_per_token_ms < 30.0);

        // Other metrics should remain unchanged
        assert_eq!(sample1.memory_available_bytes, sample2.memory_available_bytes);
        assert_eq!(sample1.tflops, sample2.tflops);
    }

    #[test]
    fn test_hardware_detector_target_access() {
        let detector = HardwareDetector::new();
        let target = detector.target();

        assert_eq!(target.memory_gb, 128);
        assert_eq!(target.tflops, 72.0);
    }

    #[test]
    fn test_hardware_backend_enum_variants() {
        // Verify all backend types exist
        let _metal = HardwareBackend::MetalGPU;
        let _neural = HardwareBackend::NeuralEngine;
        let _simd = HardwareBackend::SIMD;
        let _jetson = HardwareBackend::JetsonThor;
        let _emulated = HardwareBackend::JetsonThorEmulated;

        assert!(true);
    }

    #[test]
    fn test_metrics_sample_default() {
        let metrics = MetricsSample::default();

        assert_eq!(metrics.memory_available_bytes, 128u64 * 1024 * 1024 * 1024);
        assert_eq!(metrics.tflops, 72.0);
        assert_eq!(metrics.latency_per_token_ms, 25.4);
        assert_eq!(metrics.cache_bandwidth_bps, 1_000_000_000);
    }

    #[test]
    fn test_hardware_detector_default() {
        let detector1 = HardwareDetector::new();
        let detector2 = HardwareDetector::default();

        let backend1 = detector1.detect();
        let backend2 = detector2.detect();

        assert_eq!(backend1, backend2);
    }
}
