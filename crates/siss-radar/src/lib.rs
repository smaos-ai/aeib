pub mod audit_integration;
pub mod cache_layer;
pub mod daily_brief_generator;
pub mod delta_detection;
pub mod models;

pub use audit_integration::{AuditIntegration, GovernanceEngine};
pub use cache_layer::{CacheLayer, LocalCache, RedisCache};
pub use daily_brief_generator::{BriefGenerator, UserBrief};
pub use delta_detection::DeltaDetector;
pub use models::{
    CommitInfo, DeltaDetectionResult, DeltaEvent, GovernanceStatus, PolicyViolation, RepoHost,
    RepoSnapshot, ViolationSeverity,
};
