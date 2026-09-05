pub mod ap2;
pub mod audit;
pub mod checker;
pub mod context;
pub mod covenant_firewall;
pub mod missions;
pub mod pipeline;
pub mod policy;
pub mod policy_engine; // Now a module directory
pub mod rebac;
pub mod temporal;
pub mod types;
pub mod verdict;

// #[cfg(test)]
// mod tests_temporal;  // Legacy tests for old temporal API; replaced by wave2_temporal_guard_tests.rs

#[cfg(test)]
mod tests {
    pub mod audit_tests;
}

pub use ap2::{
    AP2Evaluator, AttributePredicate, PolicyRule, SovereignAttributeCache, SovereignAttributes,
};
pub use audit::{
    AuditArchive, AuditEvent, AuditLogger, EventType, MerkleArchive, S3ArchiveMetadata, S3Exporter,
};
pub use policy::{CycleDetector, PolicyComposer, PolicyEngine};
pub use policy_engine::{
    AllowDeny,
    CycleDetector as PolicyEngineCycleDetector,
    Decision,
    DefaultMandateVerifier,
    Mandate, // Legacy Mandate from policy/engine.rs
    MandateCache,
    MandateDecision,
    MandateV2 as PolicyEngineMandate, // New Mandate from mandate_verifier
    MandateVerifier,
    RequestContext,
};
pub use rebac::{
    DenyReason, PolicyAction, PolicyResource, ReBAC, ReBACError, RelationType, Relationship,
    SovereignIdentity, pg,
};
pub use temporal::{BlackoutDate, RateLimiter, TemporalGuard, TimeWindow};
