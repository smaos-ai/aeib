/// CIPO Engine: Extract CIPO signals from daily WorkflowCapsules
///
/// Consumes batches of WorkflowCapsules and distills them into RefinementSignals
/// that teach local SLMs to handle previously failing tasks.

use chrono::Utc;
use siss_job_router::cipo::{CipoDistiller, CipoTrace, RefinementSignal};
use siss_job_router::confidence_scorer::RoutingTier;
use siss_telemetry_loop::WorkflowCapsule;
use thiserror::Error;
use uuid::Uuid;

/// Error type for CIPO extraction operations
#[derive(Error, Debug)]
pub enum CipoError {
    #[error("Empty batch")]
    EmptyBatch,

    #[error("Distillation failed: {0}")]
    DistillationFailed(String),
}

/// Batch of WorkflowCapsules to extract CIPO signals from
#[derive(Debug, Clone)]
pub struct CapsuleBatch {
    pub capsules: Vec<WorkflowCapsule>,
    pub session_id: Uuid,
}

/// CIPO Engine orchestrates signal extraction from capsule batches
pub struct CipoEngine;

impl CipoEngine {
    /// Extract RefinementSignals from a batch of WorkflowCapsules
    pub fn extract_signals(batch: &CapsuleBatch) -> Result<Vec<RefinementSignal>, CipoError> {
        if batch.capsules.is_empty() {
            return Err(CipoError::EmptyBatch);
        }

        let traces: Vec<CipoTrace> = batch
            .capsules
            .iter()
            .map(|capsule| CipoTrace {
                payload: capsule.tool_name.clone(),
                slm_output: String::new(),
                gate_error_raw: String::new(),
                tier_escalated_from: RoutingTier::Tier1RapidMLX,
                tier_escalated_to: RoutingTier::Tier2Sonnet,
                timestamp: Utc::now(),
            })
            .collect();

        let signals = CipoDistiller::distill(&traces);
        Ok(signals)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_empty_batch_returns_error() {
        let batch = CapsuleBatch {
            capsules: vec![],
            session_id: Uuid::new_v4(),
        };

        let result = CipoEngine::extract_signals(&batch);
        assert!(result.is_err());
        match result {
            Err(CipoError::EmptyBatch) => {},
            _ => panic!("Expected EmptyBatch error"),
        }
    }

    #[test]
    fn test_single_capsule_produces_signal() {
        let capsule = WorkflowCapsule {
            capsule_id: Uuid::new_v4(),
            session_id: Uuid::new_v4(),
            tool_name: "test_tool".to_string(),
            routed_memory_ids: vec![],
            timestamp_utc: Utc::now().to_rfc3339(),
        };

        let batch = CapsuleBatch {
            capsules: vec![capsule],
            session_id: Uuid::new_v4(),
        };

        let result = CipoEngine::extract_signals(&batch);
        assert!(result.is_ok());
        let signals = result.unwrap();
        assert_eq!(signals.len(), 1);
    }

    #[test]
    fn test_five_capsules_distill_to_signals() {
        let session_id = Uuid::new_v4();
        let capsules: Vec<WorkflowCapsule> = (0..5)
            .map(|i| WorkflowCapsule {
                capsule_id: Uuid::new_v4(),
                session_id,
                tool_name: format!("tool_{}", i),
                routed_memory_ids: vec![],
                timestamp_utc: Utc::now().to_rfc3339(),
            })
            .collect();

        let batch = CapsuleBatch {
            capsules,
            session_id,
        };

        let result = CipoEngine::extract_signals(&batch);
        assert!(result.is_ok());
        let signals = result.unwrap();
        assert!(signals.len() >= 1);
    }
}
