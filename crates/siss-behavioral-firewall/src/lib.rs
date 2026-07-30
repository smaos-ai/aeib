pub mod checker;
pub mod context;
pub mod pipeline;
pub mod types;
pub mod verdict;
pub mod rebac;
pub mod ap2;
pub mod covenant_firewall;
pub mod temporal;
pub mod policy_engine;  // Now a module directory
pub mod policy;
pub mod audit;
pub mod missions;

// #[cfg(test)]
// mod tests_temporal;  // Legacy tests for old temporal API; replaced by wave2_temporal_guard_tests.rs

#[cfg(test)]
mod tests {
    pub mod audit_tests;
}

pub use rebac::{ReBAC, Relationship, RelationType, PolicyResource, PolicyAction, DenyReason, SovereignIdentity, ReBACError, pg};
pub use ap2::{AP2Evaluator, SovereignAttributes, SovereignAttributeCache, AttributePredicate, PolicyRule};
pub use temporal::{TemporalGuard, RateLimiter, TimeWindow, BlackoutDate};
pub use policy_engine::{
    Mandate,  // Legacy Mandate from policy/engine.rs
    MandateV2 as PolicyEngineMandate,  // New Mandate from mandate_verifier
    MandateDecision,
    AllowDeny,
    MandateVerifier,
    DefaultMandateVerifier,
    RequestContext,
    MandateCache,
    CycleDetector as PolicyEngineCycleDetector,
    Decision,
};
pub use policy::{PolicyEngine, PolicyComposer, CycleDetector};
pub use audit::{AuditLogger, AuditArchive, AuditEvent, EventType, MerkleArchive, S3Exporter, S3ArchiveMetadata};
