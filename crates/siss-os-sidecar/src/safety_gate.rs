use crate::resource_state::ResourceState;
use async_trait::async_trait;

/// Decision from SafetyGate: allow or deny the proposed operation (e.g., atomic swap)
#[derive(Debug, Clone, PartialEq)]
pub enum Decision {
    /// Operation can proceed safely
    Allow,

    /// Operation denied; includes explanation
    Deny { reason: String },
}

/// Trait for synchronous admission control gate
#[async_trait]
pub trait AdmissionGate: Send + Sync {
    /// Evaluate a proposed operation against current system state
    /// Returns immediately without blocking (uses cached state)
    fn admit_swap(&self) -> Decision;
}

/// Safety gate that enforces hard resource limits before model hot-swap
pub struct SafetyGate {
    /// Hard limit: unified memory utilization (default: 0.25 from EnclaveConfig)
    max_memory_pct: f64,

    /// Hard limit: thermal slope in C°/second (default: 2.0)
    max_thermal_slope: f64,

    /// Hard limit: pending Metal command queue depth (default: 32)
    max_metal_queue_depth: u32,

    /// Current resource state (updated by background monitor)
    current_state: std::sync::Arc<tokio::sync::Mutex<ResourceState>>,
}

impl SafetyGate {
    /// Create a new SafetyGate with default thresholds
    pub fn new(current_state: std::sync::Arc<tokio::sync::Mutex<ResourceState>>) -> Self {
        Self {
            max_memory_pct: 0.25,
            max_thermal_slope: 2.0,
            max_metal_queue_depth: 32,
            current_state,
        }
    }

    /// Create a new SafetyGate with custom thresholds
    pub fn with_thresholds(
        max_memory_pct: f64,
        max_thermal_slope: f64,
        max_metal_queue_depth: u32,
        current_state: std::sync::Arc<tokio::sync::Mutex<ResourceState>>,
    ) -> Self {
        Self {
            max_memory_pct,
            max_thermal_slope,
            max_metal_queue_depth,
            current_state,
        }
    }

    /// Test helper: create a SafetyGate with a static ResourceState
    pub fn for_test(state: ResourceState) -> Self {
        Self {
            max_memory_pct: 0.25,
            max_thermal_slope: 2.0,
            max_metal_queue_depth: 32,
            current_state: std::sync::Arc::new(tokio::sync::Mutex::new(state)),
        }
    }
}

#[async_trait]
impl AdmissionGate for SafetyGate {
    fn admit_swap(&self) -> Decision {
        let state = match self.current_state.try_lock() {
            Ok(guard) => guard.clone(),
            Err(_) => {
                return Decision::Deny {
                    reason: "State lock contention".to_string(),
                };
            }
        };

        // Check memory pressure
        if state.unified_memory_pct > self.max_memory_pct {
            return Decision::Deny {
                reason: format!(
                    "Memory pressure too high: {:.1}% (max {:.1}%)",
                    state.unified_memory_pct * 100.0,
                    self.max_memory_pct * 100.0
                ),
            };
        }

        // Check thermal slope
        if state.thermal_slope > self.max_thermal_slope {
            return Decision::Deny {
                reason: format!(
                    "Thermal slope too steep: {:.2}°C/s (max {:.2}°C/s)",
                    state.thermal_slope, self.max_thermal_slope
                ),
            };
        }

        // Check Metal queue depth
        if state.metal_queue_depth > self.max_metal_queue_depth {
            return Decision::Deny {
                reason: format!(
                    "Metal queue saturated: {} pending (max {})",
                    state.metal_queue_depth, self.max_metal_queue_depth
                ),
            };
        }

        Decision::Allow
    }
}
