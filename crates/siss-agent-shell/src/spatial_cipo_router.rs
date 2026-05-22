/// Phase 55: Spatial CIPO Router — GUI Failure → LoRA Retraining Pipeline
/// Converts PixelProvenanceRecord failures into MemoryCrystal lessons for distillation.

use crate::distillation_gate::{DistillationConfig, DistillationGate, TrainingContract};
use crate::memory_crystallizer::MemoryCrystal;
use crate::pixel_provenance::PixelProvenanceRecord;
use chrono::Utc;
use siss_graph_core::node::memory::ConsolidationTier;
use siss_job_router::cipo::{CipoDistiller, CipoTrace};
use siss_job_router::confidence_scorer::RoutingTier;
use uuid::Uuid;

pub struct SpatialCipoRouter {
    pub distillation_config: DistillationConfig,
}

impl Default for SpatialCipoRouter {
    fn default() -> Self {
        SpatialCipoRouter {
            distillation_config: DistillationConfig {
                confidence_threshold: 0.09,
                max_examples: 100,
            },
        }
    }
}

impl SpatialCipoRouter {
    /// Convert a single failed GUI record into a MemoryCrystal via CIPO distillation.
    /// RULE 1: record.failure_reason.is_none() → None  (success records are ignored; fail-closed)
    /// RULE 2: Build CipoTrace { payload, gate_error_raw, tier_escalated_from, tier_escalated_to, timestamp }
    /// RULE 3: CipoDistiller::distill(&[trace]) → first RefinementSignal
    /// RULE 4: Map → MemoryCrystal { source_content, confidence, tier: Episodic }
    pub fn route_failure(record: &PixelProvenanceRecord) -> Option<MemoryCrystal> {
        let failure_reason = record.failure_reason.as_ref()?;

        let trace = CipoTrace {
            payload: record.action_type.clone(),
            slm_output: record
                .before_screenshot_path
                .clone()
                .unwrap_or_default(),
            gate_error_raw: failure_reason.clone(),
            tier_escalated_from: RoutingTier::Tier1RapidMLX,
            tier_escalated_to: RoutingTier::Tier3Opus,
            timestamp: record.recorded_at,
        };

        let signals = CipoDistiller::distill(&[trace]);
        let signal = signals.first()?;

        Some(MemoryCrystal {
            crystal_id: Uuid::new_v4(),
            source_content: signal.lesson.clone(),
            tier: ConsolidationTier::Episodic,
            confidence: signal.confidence,
            promoted_at: Utc::now(),
        })
    }

    /// Batch route failure records into a TrainingContract ready for LoRA queuing.
    /// RULE 5: Collect route_failure() results (skip None) → DistillationGate::extract
    /// RULE 6: TrainingContract.examples.is_empty() → None  (no contract if no qualifying data)
    pub fn distill_failures(&self, records: &[PixelProvenanceRecord]) -> Option<TrainingContract> {
        let crystals: Vec<MemoryCrystal> = records
            .iter()
            .filter_map(Self::route_failure)
            .collect();

        if crystals.is_empty() {
            return None;
        }

        let contract = DistillationGate::extract(&crystals, &self.distillation_config);

        if contract.examples.is_empty() {
            return None;
        }

        Some(contract)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_spatial_router_skips_success_records() {
        let record = PixelProvenanceRecord {
            provenance_id: Uuid::new_v4(),
            intent_mandate_id: Uuid::new_v4(),
            task_id: Uuid::new_v4(),
            agent_id: "test_agent".to_string(),
            phase: "PHASE_54".to_string(),
            action_type: "GuiClick".to_string(),
            action_x: Some(50.0),
            action_y: Some(50.0),
            ui_element_selector: Some("button#submit".to_string()),
            before_screenshot_path: Some("/tmp/before.png".to_string()),
            after_screenshot_path: Some("/tmp/after.png".to_string()),
            token_cost: 42,
            recorded_at: Utc::now(),
            failure_reason: None,
        };

        let result = SpatialCipoRouter::route_failure(&record);
        assert!(result.is_none());
    }

    #[test]
    fn test_spatial_router_routes_gui_failure() {
        let record = PixelProvenanceRecord {
            provenance_id: Uuid::new_v4(),
            intent_mandate_id: Uuid::new_v4(),
            task_id: Uuid::new_v4(),
            agent_id: "test_agent".to_string(),
            phase: "PHASE_54".to_string(),
            action_type: "GuiClick".to_string(),
            action_x: Some(50.0),
            action_y: Some(50.0),
            ui_element_selector: Some("button#submit".to_string()),
            before_screenshot_path: Some("/tmp/before.png".to_string()),
            after_screenshot_path: Some("/tmp/after.png".to_string()),
            token_cost: 42,
            recorded_at: Utc::now(),
            failure_reason: Some("element_not_found".to_string()),
        };

        let result = SpatialCipoRouter::route_failure(&record);
        assert!(result.is_some());
        let crystal = result.unwrap();
        assert_eq!(crystal.tier, ConsolidationTier::Episodic);
        assert!(crystal.source_content.contains("element_not_found"));
    }

    #[test]
    fn test_spatial_router_distills_empty_to_none() {
        let router = SpatialCipoRouter::default();
        let records = vec![];
        let result = router.distill_failures(&records);
        assert!(result.is_none());
    }
}
