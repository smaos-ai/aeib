use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum HardwareTier {
    /// S: Specialized (RTX 4060 8GB, Jetson Orin)
    Specialized,
    /// F: Full (RTX 4090, A100)
    Full,
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

    pub fn can_run_qwen_on_this_hardware(&self) -> bool {
        self.spec.gpu_vram_gb.is_some_and(|vram| vram >= 8)
    }

    pub fn get_hardware_tier(&self) -> HardwareTier {
        if let Some(vram) = self.spec.gpu_vram_gb {
            if (8..=16).contains(&vram) {
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
}
