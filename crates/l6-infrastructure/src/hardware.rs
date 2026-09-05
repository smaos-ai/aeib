use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum HardwareTier {
    /// S: Specialized (RTX 4060 8GB, Jetson Orin)
    Specialized,
    /// F: Full (RTX 4090, A100)
    Full,
    /// JT: Jetson Thor (128GB unified memory, 72 TFLOPS)
    JetsonThor,
    /// N/A: Not Applicable
    NotApplicable,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HardwareSpec {
    pub cpu_cores: u32,
    pub ram_gb: u32,
    pub gpu_name: Option<String>,
    pub gpu_vram_gb: Option<u32>,
}

/// Jetson Thor specifications for SMAOS Phase 2C deployment
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JetsonThorSpec {
    pub model: String,
    pub unified_memory_gb: u32,
    pub tflops_fp32: f64,
    pub tensor_cores: u32,
    pub memory_bandwidth_gbps: u32,
    pub max_power_watts: u32,
    pub nvme_slot_count: u8,
    pub ethernet_ports: u8,
    pub usb_ports: u8,
    pub pcie_lanes: u32,
}

pub struct HardwareDetector {
    spec: HardwareSpec,
}

impl HardwareDetector {
    pub fn new() -> Self {
        Self {
            spec: HardwareSpec {
                cpu_cores: 8,
                ram_gb: 16,
                gpu_name: Some("RTX 4060".to_string()),
                gpu_vram_gb: Some(8),
            },
        }
    }

    pub fn new_jetson_thor() -> Self {
        Self {
            spec: HardwareSpec {
                cpu_cores: 144,
                ram_gb: 128,
                gpu_name: Some("Jetson Thor".to_string()),
                gpu_vram_gb: Some(128),
            },
        }
    }

    pub fn can_run_qwen_on_this_hardware(&self) -> bool {
        self.spec.gpu_vram_gb.is_some_and(|vram| vram >= 8)
    }

    pub fn get_hardware_tier(&self) -> HardwareTier {
        if let Some(vram) = self.spec.gpu_vram_gb {
            if vram == 128 && self.spec.cpu_cores == 144 {
                HardwareTier::JetsonThor
            } else if (8..=16).contains(&vram) {
                HardwareTier::Specialized
            } else if vram > 16 {
                HardwareTier::Full
            } else {
                HardwareTier::NotApplicable
            }
        } else {
            HardwareTier::NotApplicable
        }
    }

    pub fn get_spec(&self) -> &HardwareSpec {
        &self.spec
    }

    /// Get Jetson Thor specifications for deployment
    pub fn get_jetson_thor_spec() -> JetsonThorSpec {
        JetsonThorSpec {
            model: "NVIDIA Jetson Thor".to_string(),
            unified_memory_gb: 128,
            tflops_fp32: 72.0,
            tensor_cores: 18432,
            memory_bandwidth_gbps: 3200,
            max_power_watts: 500,
            nvme_slot_count: 1,
            ethernet_ports: 1,
            usb_ports: 4,
            pcie_lanes: 16,
        }
    }

    /// Validate network binding to localhost only (egress control)
    pub fn validate_localhost_binding(bind_addr: &str) -> Result<(), String> {
        match bind_addr {
            "127.0.0.1" | "localhost" | "::1" => Ok(()),
            "0.0.0.0" | "::" => Err(
                "Network binding must be localhost-only for security. Got: {}".to_string(),
            ),
            addr => {
                if addr.starts_with("127.") || addr.starts_with("::1") {
                    Ok(())
                } else {
                    Err(format!(
                        "Non-localhost binding detected: {}. Only 127.0.0.1/localhost allowed.",
                        addr
                    ))
                }
            }
        }
    }

    /// Calculate NVMe SSD cache sizing for model storage
    pub fn calculate_cache_size_gb(num_models: u32, avg_model_size_gb: u32) -> u32 {
        let required = num_models * avg_model_size_gb;
        let overhead = (required / 10).max(50); // 10% overhead, min 50GB
        required + overhead
    }

    /// Storage requirements for Jetson Thor deployment
    pub fn get_jetson_storage_requirements() -> StorageRequirements {
        StorageRequirements {
            system_os_gb: 10,
            model_cache_gb: 200, // 2x 100GB Qwen models + overhead
            working_memory_gb: 50,
            audit_logs_retention_days: 365,
            log_storage_gb_per_day: 5,
            total_recommended_gb: 260,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StorageRequirements {
    pub system_os_gb: u32,
    pub model_cache_gb: u32,
    pub working_memory_gb: u32,
    pub audit_logs_retention_days: u32,
    pub log_storage_gb_per_day: u32,
    pub total_recommended_gb: u32,
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
    fn test_can_run_qwen() {
        let detector = HardwareDetector::new();
        assert!(detector.can_run_qwen_on_this_hardware());
    }

    #[test]
    fn test_hardware_tier() {
        let detector = HardwareDetector::new();
        assert_eq!(detector.get_hardware_tier(), HardwareTier::Specialized);
    }

    #[test]
    fn test_jetson_thor_creation() {
        let detector = HardwareDetector::new_jetson_thor();
        assert_eq!(detector.get_spec().ram_gb, 128);
        assert_eq!(detector.get_spec().cpu_cores, 144);
        assert_eq!(detector.get_hardware_tier(), HardwareTier::JetsonThor);
    }

    #[test]
    fn test_jetson_thor_spec() {
        let spec = HardwareDetector::get_jetson_thor_spec();
        assert_eq!(spec.unified_memory_gb, 128);
        assert_eq!(spec.tflops_fp32, 72.0);
        assert_eq!(spec.memory_bandwidth_gbps, 3200);
        assert!(spec.max_power_watts > 0);
    }

    #[test]
    fn test_localhost_binding_valid() {
        assert!(HardwareDetector::validate_localhost_binding("127.0.0.1").is_ok());
        assert!(HardwareDetector::validate_localhost_binding("localhost").is_ok());
        assert!(HardwareDetector::validate_localhost_binding("::1").is_ok());
    }

    #[test]
    fn test_localhost_binding_invalid() {
        assert!(HardwareDetector::validate_localhost_binding("0.0.0.0").is_err());
        assert!(HardwareDetector::validate_localhost_binding("::").is_err());
        assert!(HardwareDetector::validate_localhost_binding("192.168.1.1").is_err());
    }

    #[test]
    fn test_cache_size_calculation() {
        let size = HardwareDetector::calculate_cache_size_gb(2, 100);
        assert!(size >= 200); // 2 * 100
        assert!(size <= 220); // 200 + 10% overhead
    }

    #[test]
    fn test_storage_requirements() {
        let req = HardwareDetector::get_jetson_storage_requirements();
        assert_eq!(req.system_os_gb, 10);
        assert!(req.model_cache_gb > 0);
        assert!(req.total_recommended_gb >= req.model_cache_gb);
    }

    #[test]
    fn test_jetson_can_run_qwen() {
        let detector = HardwareDetector::new_jetson_thor();
        assert!(detector.can_run_qwen_on_this_hardware());
    }
}
