pub mod autoresearch_scheduler;
pub mod causal_extractor;
pub mod chain_extractor;
pub mod forecast_engine;
pub mod metrics_aggregator;
pub mod migrations;
pub mod observability_watcher;
pub mod pool;
pub mod recovery_event_broadcaster;
pub mod recovery_extractor;
pub mod recovery_sweep_scheduler;
pub mod repo;
pub mod rce;

#[cfg(feature = "axum")]
pub mod rce_axum_handlers;

pub mod signal_acceleration;
pub mod signal_reinforcement;
pub mod signal_tier_promotion;
pub mod sweep_scheduler;
pub mod telemetry_handler;

#[cfg(feature = "axum")]
pub mod telemetry_axum_handlers;

pub mod trust_event_broadcaster;
pub mod wiki_writer;

pub use signal_acceleration::accelerate_signal_decay_for_false_positive;
pub use signal_reinforcement::reinforce_signals_for_feedback;
pub use signal_tier_promotion::{
    apply_decay_with_tier, demote_signal_to_episodic_on_failure,
    promote_signal_to_semantic_on_validation,
};
