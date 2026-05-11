pub mod autoresearch_scheduler;
pub mod metrics_aggregator;
pub mod migrations;
pub mod observability_watcher;
pub mod pool;
pub mod recovery_event_broadcaster;
pub mod recovery_sweep_scheduler;
pub mod repo;
pub mod sweep_scheduler;
pub mod telemetry_handler;

#[cfg(feature = "axum")]
pub mod telemetry_axum_handlers;

pub mod trust_event_broadcaster;
pub mod wiki_writer;
