pub mod biometric;
pub mod capsules;
pub mod config_evolution;
pub mod consolidator;
pub mod failure_analyzer;
pub mod ledger;
pub mod memtree;
pub mod metrics;
pub mod offline_verifier;
pub mod operators;
pub mod replay_engine;
pub mod tui;
pub mod watchdog;
pub mod vision_survival_protocol;

pub use biometric::{
    BiometricCapsule, DeviceData, DeviceType, PersonalMetabolicModel, AP2ResearchCapsule,
    ConsentLevel, GembaProof,
};
pub use config_evolution::ConfigEvolution;
pub use consolidator::NightCycleConsolidator;
pub use failure_analyzer::FailureAnalyzer;
pub use ledger::append_audit;
pub use memtree::{Capsule, MemTree, ScopeType};
pub use metrics::{MetricRow, MetricsDb};
pub use offline_verifier::OfflineVerifier;
pub use replay_engine::{
    StateTransitionRecord, ReplayLog, ReplayEngine, FileBasedReplayLog,
};
pub use tui::Dashboard;
pub use watchdog::RecoveryWatchdog;
pub use vision_survival_protocol::{VisionSurvivalProtocol, SyncCapsule, SyncStatus};
