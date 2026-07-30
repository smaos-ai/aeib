use std::time::Duration;
use crate::chaos_scenarios::AiFactoryChaosScenario;
use crate::state_snapshot::StateSnapshot;
use crate::error::{AiFactoryError, Result};

const RTO_SLA_MS: u64 = 5000;  // 5 seconds

/// Recovery validator for RTO<5s and RPO=0 compliance
pub struct RecoveryValidator;

impl RecoveryValidator {
    /// Validate RTO (Recovery Time Objective): all scenarios must recover in <5 seconds
    pub async fn validate_rto(scenario: &AiFactoryChaosScenario) -> Result<bool> {
        let recovery_time = scenario.expected_recovery_time();
        let rto_limit = Duration::from_millis(RTO_SLA_MS);

        if recovery_time > rto_limit {
            return Err(AiFactoryError::RtoViolation(recovery_time));
        }

        Ok(true)
    }

    /// Validate RTO for all scenarios
    pub async fn validate_rto_all_scenarios() -> Result<bool> {
        for scenario in AiFactoryChaosScenario::all_scenarios() {
            Self::validate_rto(&scenario).await?;
        }
        Ok(true)
    }

    /// Validate RPO (Recovery Point Objective): no messages lost during failover
    pub async fn validate_rpo(expected_loss: usize) -> Result<bool> {
        if expected_loss > 0 {
            return Err(AiFactoryError::RpoViolation(expected_loss));
        }
        Ok(true)
    }

    /// Validate state consistency: pre/post snapshots have same merkle root (after recovery)
    pub async fn validate_state_consistency(
        snapshot_before: &StateSnapshot,
        snapshot_after: &StateSnapshot,
    ) -> Result<bool> {
        // After recovery, we expect the merkle roots to match
        // (assuming the recovery process properly restored state)
        if snapshot_before.merkle_root != snapshot_after.merkle_root {
            return Err(AiFactoryError::StateConsistencyError(
                format!(
                    "Merkle root mismatch: before={}, after={}",
                    hex::encode(snapshot_before.merkle_root),
                    hex::encode(snapshot_after.merkle_root),
                ),
            ));
        }

        // Verify both snapshots' merkle roots are valid
        if !snapshot_before.verify_merkle_root() {
            return Err(AiFactoryError::StateConsistencyError(
                "Before snapshot merkle root verification failed".to_string(),
            ));
        }

        if !snapshot_after.verify_merkle_root() {
            return Err(AiFactoryError::StateConsistencyError(
                "After snapshot merkle root verification failed".to_string(),
            ));
        }

        Ok(true)
    }

    /// Check if scenario is within RTO SLA
    pub fn is_within_rto_sla(recovery_ms: u64) -> bool {
        recovery_ms <= RTO_SLA_MS
    }

    /// Get RTO SLA in milliseconds
    pub fn get_rto_sla_ms() -> u64 {
        RTO_SLA_MS
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;
    use crate::state_snapshot::AgentState;
    use uuid::Uuid;
    use chrono::Utc;

    #[tokio::test]
    async fn test_validate_rto_primary_down() {
        let result = RecoveryValidator::validate_rto(&AiFactoryChaosScenario::RegionPrimaryDown)
            .await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_validate_rto_all_scenarios() {
        let result = RecoveryValidator::validate_rto_all_scenarios().await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_validate_rpo_zero_loss() {
        let result = RecoveryValidator::validate_rpo(0).await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_validate_state_consistency() {
        let agent_id = Uuid::new_v4();
        let mut agents = HashMap::new();
        agents.insert(
            agent_id,
            AgentState {
                agent_id,
                state_hash: [42u8; 32],
                message_count: 100,
                last_execution: Utc::now(),
            },
        );

        let snapshot1 = StateSnapshot::new(agents.clone());
        let snapshot2 = StateSnapshot::new(agents);

        let result = RecoveryValidator::validate_state_consistency(&snapshot1, &snapshot2).await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_is_within_rto_sla() {
        assert!(RecoveryValidator::is_within_rto_sla(3000));
        assert!(RecoveryValidator::is_within_rto_sla(5000));
        assert!(!RecoveryValidator::is_within_rto_sla(5001));
    }
}
