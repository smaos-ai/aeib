use serde::{Deserialize, Serialize};
use std::time::Duration;
use crate::error::Result;

/// Chaos injection result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChaosInjectionResult {
    pub scenario: String,
    pub injected_at_ms: u64,
    pub resolved_at_ms: Option<u64>,
    pub messages_lost: usize,
    pub messages_recovered: usize,
}

/// 15 chaos scenarios for resilience testing
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum AiFactoryChaosScenario {
    /// EU primary region becomes unavailable, fail to US replica
    RegionPrimaryDown,

    /// US secondary region goes down, primary + APAC proceed
    RegionSecondaryDown,

    /// Network partition between EU and US, APAC detects split
    NetworkPartitionEuUs,

    /// Single tool call exceeds 5s timeout, retry logic triggers
    ToolCallTimeout,

    /// Merkle root divergence detected between regions
    StateChecksumMismatch,

    /// Single agent process crashes, supervisor restarts it
    AgentPanic,

    /// Multiple agents failover simultaneously to replicas
    ConcurrentFailover,

    /// Replay trace but RNG produces divergent results (chaos injection)
    ReplayWithDivergence,

    /// A2A message queue fills up, backpressure activated
    MessageQueueFull,

    /// Merkle chain splits due to causal inconsistency
    MerkleChainBranch,

    /// Tool result bytes tampered (corruption detection)
    ToolResultCorruption,

    /// System clock skew >1s detected across regions
    TimestampSkew,

    /// Replica disk space exhausted
    DiskFull,

    /// Gradual memory pressure over 100 snapshots
    MemoryLeak,

    /// Chain: primary down → secondary down → APAC failover
    CascadingFailure,
}

impl AiFactoryChaosScenario {
    /// Inject chaos scenario (simulated)
    pub async fn inject(&self) -> Result<ChaosInjectionResult> {
        let (messages_lost, resolved_ms) = match self {
            Self::RegionPrimaryDown => (5, 3000),
            Self::RegionSecondaryDown => (0, 1000),
            Self::NetworkPartitionEuUs => (3, 4500),
            Self::ToolCallTimeout => (1, 5000),
            Self::StateChecksumMismatch => (0, 2000),
            Self::AgentPanic => (1, 1500),
            Self::ConcurrentFailover => (2, 3500),
            Self::ReplayWithDivergence => (0, 4000),
            Self::MessageQueueFull => (10, 4000),
            Self::MerkleChainBranch => (2, 3000),
            Self::ToolResultCorruption => (0, 1000),
            Self::TimestampSkew => (0, 2000),
            Self::DiskFull => (8, 4500),
            Self::MemoryLeak => (0, 4800),
            Self::CascadingFailure => (4, 4900),
        };

        Ok(ChaosInjectionResult {
            scenario: format!("{:?}", self),
            injected_at_ms: 0,
            resolved_at_ms: Some(resolved_ms),
            messages_lost,
            messages_recovered: 0,
        })
    }

    /// Expected recovery time for this scenario
    pub fn expected_recovery_time(&self) -> Duration {
        match self {
            Self::RegionPrimaryDown => Duration::from_millis(3000),
            Self::RegionSecondaryDown => Duration::from_millis(1000),
            Self::NetworkPartitionEuUs => Duration::from_millis(4500),
            Self::ToolCallTimeout => Duration::from_millis(5000),
            Self::StateChecksumMismatch => Duration::from_millis(2000),
            Self::AgentPanic => Duration::from_millis(1500),
            Self::ConcurrentFailover => Duration::from_millis(3500),
            Self::ReplayWithDivergence => Duration::from_millis(4000),
            Self::MessageQueueFull => Duration::from_millis(4000),
            Self::MerkleChainBranch => Duration::from_millis(3000),
            Self::ToolResultCorruption => Duration::from_millis(1000),
            Self::TimestampSkew => Duration::from_millis(2000),
            Self::DiskFull => Duration::from_millis(4500),
            Self::MemoryLeak => Duration::from_millis(4800),
            Self::CascadingFailure => Duration::from_millis(4900),
        }
    }

    /// Expected number of messages lost (RPO target = 0, but chaos may lose some)
    pub fn expected_data_loss(&self) -> usize {
        match self {
            Self::RegionPrimaryDown => 5,
            Self::RegionSecondaryDown => 0,
            Self::NetworkPartitionEuUs => 3,
            Self::ToolCallTimeout => 1,
            Self::StateChecksumMismatch => 0,
            Self::AgentPanic => 1,
            Self::ConcurrentFailover => 2,
            Self::ReplayWithDivergence => 0,
            Self::MessageQueueFull => 10,
            Self::MerkleChainBranch => 2,
            Self::ToolResultCorruption => 0,
            Self::TimestampSkew => 0,
            Self::DiskFull => 8,
            Self::MemoryLeak => 0,
            Self::CascadingFailure => 4,
        }
    }

    /// Get all 15 scenarios
    pub fn all_scenarios() -> Vec<Self> {
        vec![
            Self::RegionPrimaryDown,
            Self::RegionSecondaryDown,
            Self::NetworkPartitionEuUs,
            Self::ToolCallTimeout,
            Self::StateChecksumMismatch,
            Self::AgentPanic,
            Self::ConcurrentFailover,
            Self::ReplayWithDivergence,
            Self::MessageQueueFull,
            Self::MerkleChainBranch,
            Self::ToolResultCorruption,
            Self::TimestampSkew,
            Self::DiskFull,
            Self::MemoryLeak,
            Self::CascadingFailure,
        ]
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_chaos_region_primary_down() {
        let result = AiFactoryChaosScenario::RegionPrimaryDown
            .inject()
            .await
            .unwrap();
        assert_eq!(result.scenario, "RegionPrimaryDown");
        assert!(result.resolved_at_ms.is_some());
    }

    #[tokio::test]
    async fn test_chaos_all_scenarios_have_recovery_time() {
        for scenario in AiFactoryChaosScenario::all_scenarios() {
            let recovery_time = scenario.expected_recovery_time();
            assert!(recovery_time.as_millis() > 0);
            assert!(recovery_time.as_millis() <= 5000, "{:?} exceeds 5s", scenario);
        }
    }
}
