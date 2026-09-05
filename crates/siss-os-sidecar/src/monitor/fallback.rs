use crate::resource_state::ResourceState;
use async_trait::async_trait;
use std::sync::Arc;
use std::sync::atomic::{AtomicU32, Ordering};
use std::time::Instant;

/// Cross-platform resource monitor using sysinfo crate
/// Does not provide Metal queue depth (always 0)
pub struct FallbackMonitor {
    sys: sysinfo::System,
    components: sysinfo::Components,
    prev_temp: f32,
    prev_sample_time: Instant,
    metal_queue_depth: Arc<AtomicU32>,
}

impl FallbackMonitor {
    /// Create a new FallbackMonitor
    pub fn new(metal_queue_depth: Arc<AtomicU32>) -> Self {
        Self {
            sys: sysinfo::System::new_all(),
            components: sysinfo::Components::new_with_refreshed_list(),
            prev_temp: 0.0,
            prev_sample_time: Instant::now(),
            metal_queue_depth,
        }
    }

    /// Create a test instance with default metal queue counter
    pub fn for_test() -> Self {
        Self::new(Arc::new(AtomicU32::new(0)))
    }
}

#[async_trait]
impl super::ResourceMonitor for FallbackMonitor {
    async fn sample(&mut self) -> anyhow::Result<ResourceState> {
        use sysinfo::{CpuRefreshKind, MemoryRefreshKind};

        // Memory
        self.sys
            .refresh_memory_specifics(MemoryRefreshKind::new().with_ram());
        let total = self.sys.total_memory() as f64;
        let used = self.sys.used_memory() as f64;
        let unified_memory_pct = if total > 0.0 {
            (used / total).min(1.0)
        } else {
            0.0
        };

        // CPU
        self.sys
            .refresh_cpu_specifics(CpuRefreshKind::new().with_cpu_usage());
        let per_core_load: Vec<f64> = self
            .sys
            .cpus()
            .iter()
            .map(|cpu| (cpu.cpu_usage() as f64 / 100.0).min(1.0))
            .collect();

        // Thermal
        self.components.refresh();
        let curr_temp = self
            .components
            .iter()
            .find(|c| c.label().to_lowercase().contains("cpu"))
            .map(|c| c.temperature())
            .unwrap_or(0.0);

        let now = Instant::now();
        let dt = now.duration_since(self.prev_sample_time).as_secs_f64();
        let thermal_slope = if dt > 0.0 {
            ((curr_temp - self.prev_temp) as f64 / dt)
                .max(-10.0)
                .min(10.0)
        } else {
            0.0
        };

        self.prev_temp = curr_temp;
        self.prev_sample_time = now;

        // Metal queue (always 0 on non-macOS)
        let metal_queue_depth = self.metal_queue_depth.load(Ordering::Relaxed);

        Ok(ResourceState::new(
            unified_memory_pct,
            thermal_slope,
            metal_queue_depth,
            per_core_load,
        ))
    }
}
