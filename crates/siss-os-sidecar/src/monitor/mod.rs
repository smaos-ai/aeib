use crate::resource_state::ResourceState;
use async_trait::async_trait;
use std::time::Duration;

mod fallback;
#[cfg(target_os = "macos")]
mod macos;

pub use fallback::FallbackMonitor;
#[cfg(target_os = "macos")]
pub use macos::MacOsMonitor;

/// Trait for background OS resource monitoring
#[async_trait]
pub trait ResourceMonitor: Send + Sync {
    /// Collect a fresh ResourceState snapshot from the operating system
    async fn sample(&mut self) -> anyhow::Result<ResourceState>;

    /// Recommended polling interval for accurate readings
    /// Typically 500ms–1000ms (CPU metrics require ≥200ms gap on macOS)
    fn poll_interval(&self) -> Duration {
        Duration::from_millis(500)
    }
}
