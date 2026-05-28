//! Inbound pipeline: σ (selection) → ϕ (simplification) → π⁺ (projection)
//!
//! Operators that ensure no raw data bypasses the cartographic filters before
//! entering an agent's active context window. The pipeline guarantees:
//! - σ: confidence threshold enforced (below-threshold → BlackFog, permanently excluded)
//! - ϕ: token budget enforced (budget-cut entries → GrayFog, known but obscured)
//! - π⁺: classification into VisibleField, GrayFog, BlackFog for agent awareness

use crate::zones::{classify_zones, ZonalContextMap};
use crate::types::MemoryEntry;
use serde_json;

/// Inbound cartographic pipeline: σ ∘ ϕ ∘ π⁺
///
/// Takes already-retrieved candidates (before budget trim) and the budgeted visible set,
/// applies selection/simplification/projection, and returns a classified map.
///
/// Invariant: The result partitions all_candidates into zones such that
/// visible.len() + gray_fog.len() + black_fog_count == all_candidates.len()
pub fn apply_inbound_pipeline(
    all_candidates: Vec<MemoryEntry>,
    visible: Vec<MemoryEntry>,
    confidence_threshold: f64,
    token_budget: i64,
    budget_used: i64,
) -> ZonalContextMap {
    classify_zones(all_candidates, visible, confidence_threshold, token_budget, budget_used)
}

/// π⁺ projection: serialize ZonalContextMap for TaskContext.visible_field injection.
///
/// Transforms the classified memory map into a JSON representation ready to enter
/// the executor's active context. Returns Null on serialization failure (fail-closed).
pub fn project_to_task_context(map: &ZonalContextMap) -> serde_json::Value {
    serde_json::to_value(map).unwrap_or(serde_json::Value::Null)
}

#[cfg(test)]
mod tests {
    use super::*;
    use siss_graph_core::node::memory::ConsolidationTier;
    use uuid::Uuid;

    fn make_entry(content: &str, confidence: f64, tier: ConsolidationTier) -> MemoryEntry {
        MemoryEntry {
            memory_id: Uuid::new_v4(),
            content: content.into(),
            confidence_score: confidence,
            tier,
            affective_signature: None,
        }
    }

    #[test]
    fn test_apply_inbound_pipeline_preserves_visible_field() {
        let entries = vec![
            make_entry("high1", 0.9, ConsolidationTier::Semantic),
            make_entry("high2", 0.9, ConsolidationTier::Semantic),
        ];
        let visible = entries.clone();

        let map = apply_inbound_pipeline(entries, visible, 0.1, 1000, 4);

        assert_eq!(map.visible.len(), 2);
    }

    #[test]
    fn test_project_to_task_context_serializes_to_json() {
        let entries = vec![make_entry("test", 0.9, ConsolidationTier::Semantic)];
        let map = apply_inbound_pipeline(entries.clone(), entries, 0.1, 1000, 1);

        let json = project_to_task_context(&map);

        assert!(json.is_object());
    }
}
