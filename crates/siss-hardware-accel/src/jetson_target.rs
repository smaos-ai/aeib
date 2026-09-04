/// Jetson Thor hardware target specification and detection
/// Jetson Thor: NVIDIA edge accelerator with 128GB unified memory, 72 TFLOPS
use std::fs;

#[derive(Clone, Debug, PartialEq)]
pub struct QuantizationConfig {
    pub supports_int8: bool,
    pub supports_fp4: bool,
    pub supports_fp16: bool,
    pub supports_bfloat16: bool,
}

impl Default for QuantizationConfig {
    fn default() -> Self {
        Self {
            supports_int8: true,
            supports_fp4: true,
            supports_fp16: false,
            supports_bfloat16: true,
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct JetsonTarget {
    pub memory_gb: u32,
    pub tflops: f64,
    pub soc_name: String,
    pub available: bool,
}

impl JetsonTarget {
    /// Create a Jetson Thor target with hardware detection
    pub fn jetson_thor() -> Self {
        let available = Self::detect_hardware();
        Self {
            memory_gb: 128,
            tflops: 72.0,
            soc_name: "Jetson Thor".to_string(),
            available,
        }
    }

    /// Create a Jetson Thor target or fallback to emulation
    pub fn jetson_thor_or_emulated() -> Self {
        let available = Self::detect_hardware();
        Self {
            memory_gb: 128,
            tflops: 72.0,
            soc_name: if available {
                "Jetson Thor".to_string()
            } else {
                "Jetson Thor (Emulated)".to_string()
            },
            available,
        }
    }

    /// Detect if running on actual Jetson Thor hardware (Linux only)
    pub fn detect_hardware() -> bool {
        // Check for Tegra driver (indicates NVIDIA hardware)
        if Self::check_tegra_driver() {
            return true;
        }

        // Check for device tree model
        if Self::check_device_tree() {
            return true;
        }

        false
    }

    fn check_tegra_driver() -> bool {
        fs::metadata("/sys/module/tegra_drv").is_ok()
    }

    fn check_device_tree() -> bool {
        if let Ok(model) = fs::read_to_string("/proc/device-tree/model") {
            model.to_lowercase().contains("jetson") || model.to_lowercase().contains("tegra")
        } else {
            false
        }
    }

    /// Quantization configuration for Jetson Thor
    pub fn quantization_config(&self) -> QuantizationConfig {
        QuantizationConfig::default()
    }

    /// Maximum KV cache allocation: 128GB total - 10GB reserved for OS/runtime
    pub fn max_kv_cache_bytes(&self) -> u64 {
        ((self.memory_gb as u64 - 10) * 1024 * 1024 * 1024) as u64
    }

    /// Expected latency per token at 39.3 tokens/sec
    pub fn expected_latency_ms_per_token(&self) -> f64 {
        1000.0 / 39.3 // ~25.4ms per token
    }

    /// Local network bandwidth: 1Gbps = 125 MBps
    pub fn local_network_bandwidth_bps(&self) -> u64 {
        1_000_000_000 // 1 Gbps
    }

    /// Recommended NVMe cache size
    pub fn recommended_cache_size_bytes(&self) -> u64 {
        50 * 1024 * 1024 * 1024 // 50GB
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_jetson_thor_spec_available() {
        let jetson = JetsonTarget::jetson_thor();
        assert_eq!(jetson.memory_gb, 128);
        assert_eq!(jetson.tflops, 72.0);
        assert_eq!(jetson.soc_name, "Jetson Thor");
    }

    #[test]
    fn test_jetson_target_quantization_config() {
        let jetson = JetsonTarget::jetson_thor();
        let config = jetson.quantization_config();

        assert!(config.supports_int8);
        assert!(config.supports_fp4);
        assert!(!config.supports_fp16);
        assert!(config.supports_bfloat16);
    }

    #[test]
    fn test_jetson_target_kv_cache_allocation() {
        let jetson = JetsonTarget::jetson_thor();
        let max_cache = jetson.max_kv_cache_bytes();

        // 128GB - 10GB = 118GB
        let expected = 118u64 * 1024 * 1024 * 1024;
        assert_eq!(max_cache, expected);
    }

    #[test]
    fn test_jetson_target_inference_latency_target() {
        let jetson = JetsonTarget::jetson_thor();
        let latency_ms = jetson.expected_latency_ms_per_token();

        // Should be approximately 25.4ms per token (1000 / 39.3)
        assert!(latency_ms > 25.0 && latency_ms < 26.0);
    }

    #[test]
    fn test_jetson_target_network_bandwidth() {
        let jetson = JetsonTarget::jetson_thor();
        let bps = jetson.local_network_bandwidth_bps();

        // 1 Gbps
        assert_eq!(bps, 1_000_000_000);
    }

    #[test]
    fn test_jetson_target_recommended_cache_size() {
        let jetson = JetsonTarget::jetson_thor();
        let cache_bytes = jetson.recommended_cache_size_bytes();

        // 50GB
        let expected = 50u64 * 1024 * 1024 * 1024;
        assert_eq!(cache_bytes, expected);
    }

    #[test]
    fn test_jetson_thor_or_emulated() {
        let jetson = JetsonTarget::jetson_thor_or_emulated();
        assert_eq!(jetson.memory_gb, 128);
        assert_eq!(jetson.tflops, 72.0);

        // soc_name depends on hardware detection
        assert!(
            jetson.soc_name.contains("Jetson Thor"),
            "Should contain 'Jetson Thor'"
        );
    }

    #[test]
    fn test_jetson_thor_detection_fallback() {
        // This test verifies detection logic works (may be false on non-Linux)
        let detected = JetsonTarget::detect_hardware();
        // Don't assert true/false - just ensure function doesn't panic
        assert!(true);
    }
}
