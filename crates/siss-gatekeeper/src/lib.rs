pub mod agent_communication_platform;
pub mod acp {
    pub use crate::agent_communication_platform::*;
}
pub mod anomaly_detection;
pub mod c2pa_compat {
    pub use siss_c2pa::*;
}
pub mod ap2_policies;
pub mod attestation;
pub mod behavior_scorer;
pub mod commerce;
pub mod compliance;
pub mod constraint_resolver;
pub mod constraint_solver;
pub mod contract_state_store;
pub mod delegation;
pub mod delegation_routing;
pub mod edge_actuation;
pub mod evaluator;
pub mod evm_executor;
pub mod facility_mandate;
pub mod federation_resolver;
pub mod latency;
pub mod nonce;
pub mod payload;
pub mod pipeline;
pub mod policy;
pub mod pricing;
pub mod refresh;
pub mod reputation_blender;
pub mod signer;
pub mod sneakernet_ingress;
pub mod tokens;
pub mod transitive_resolver;
pub mod types;
pub mod router;
pub mod vision_api;
pub mod baseline_capsule;
pub mod capsules;

// Re-export research gateway types for convenience
pub use pipeline::research::{ResearchQuery, ResearchResult, ResearchSource};
pub use pricing::BlastMatrixCache;
pub use vision_api::{
    RiskLevel, HumanGatePolicy, HumanGateProof, GovernRequest,
    PreExecuteCheckResult, VisionAPI, DecisionContext, DecisionGate
};

// Re-export Federal Compliance Capsule Pack types
pub use compliance::{
    ComplianceCapsule, ApprovalLevel, SafetyGateResult, SafetyGateType,
    SafetyGateValidator, SafetyGateValidationResult,
    HumanGateRequest, HumanGateAttestation,
    MerkleAuditEntry, EXEC_LOG,
    AP2SettlementRecord, CreatorPayoutSimulation, SettlementStatus
};
