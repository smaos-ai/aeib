//! siss-ai-factory: Sovereign AI Factory with deterministic replay, chaos testing, and multi-region failover.
//!
//! # Overview
//! This crate provides:
//! - DeterministicReplayer: deterministic execution replay with merkle-rooted state snapshots
//! - StateSnapshot: immutable, merkle-rooted agent state across 3 regions (EU primary, US/APAC replicas)
//! - AiFactoryChaosScenario: 15 chaos injection scenarios (region down, network partition, etc.)
//! - RecoveryValidator: RTO<5s and RPO=0 SLA compliance verification
//! - MachineRegistry: 3x Mac Studio enrollment and health monitoring
//!
//! # Integration Points
//! - Phase 28 (Cross-Region Failover): RTO/RPO validation, Aurora Global Merkle replication
//! - Phase 27 (Swarm Coordinator): Agent delegation, message routing, cycle detection
//! - Phase 30 (Multi-Currency): Settlement atomicity patterns (all-or-nothing state)
//! - Phase 25 (ReBAC): Policy enforcement during recovery

pub mod deterministic_replayer;
pub mod state_snapshot;
pub mod chaos_scenarios;
pub mod recovery_validator;
pub mod machine_registry;
pub mod expert_router;
pub mod expert_cache;

pub use deterministic_replayer::{DeterministicReplayer, ExecutionTrace, ExecutionResult, ToolCall, ToolResult};
pub use state_snapshot::{StateSnapshot, AgentState};
pub use chaos_scenarios::{AiFactoryChaosScenario, ChaosInjectionResult};
pub use recovery_validator::RecoveryValidator;
pub use machine_registry::{MachineRegistry, MachineMeta, HealthReport};
pub use expert_router::{ExpertRouter, ExpertDomain, ModelId};
pub use expert_cache::{ExpertCache, MockInferenceModel};

pub mod error;
pub use error::{AiFactoryError, Result};
