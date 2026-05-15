use std::time::Instant;

/// Snapshot of current OS resource metrics, sampled by the sidecar
#[derive(Debug, Clone)]
pub struct ResourceState {
    /// Unified memory utilization (0.0–1.0)
    pub unified_memory_pct: f64,

    /// Thermal slope: ΔC°/second (positive = heating)
    pub thermal_slope: f64,

    /// Metal command queue depth (number of pending MTLCommandBuffer)
    pub metal_queue_depth: u32,

    /// Per-core load average (0.0–1.0 per logical CPU core)
    pub per_core_load: Vec<f64>,

    /// Instant when this snapshot was captured
    pub sampled_at: Instant,
}

impl ResourceState {
    /// Create a new ResourceState with all metrics
    pub fn new(
        unified_memory_pct: f64,
        thermal_slope: f64,
        metal_queue_depth: u32,
        per_core_load: Vec<f64>,
    ) -> Self {
        Self {
            unified_memory_pct,
            thermal_slope,
            metal_queue_depth,
            per_core_load,
            sampled_at: Instant::now(),
        }
    }

    /// Convenience constructor for test mocks
    pub fn mock(unified_memory_pct: f64, thermal_slope: f64, metal_queue_depth: u32) -> Self {
        Self::new(
            unified_memory_pct,
            thermal_slope,
            metal_queue_depth,
            vec![0.5],
        )
    }
}
