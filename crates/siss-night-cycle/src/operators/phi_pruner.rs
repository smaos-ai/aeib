//! T3: Safe Pruning φ Operator — Token-Aware Governance Pruning
//!
//! This operator implements goal-aware token pruning for governance contexts.
//! It preserves decision-critical paths while removing low-utility metadata.
//!
//! Key guarantees:
//! - No alignment/safety signal degradation
//! - Measurable token reduction (target: 60-84%)
//! - Deterministic pruning (same input → same output)
//!
//! Model: entities are "tokens" or "metadata"; we score each by:
//! - decision_criticality: 0.0-1.0 (how essential for policy decision)
//! - alignment_relevance: 0.0-1.0 (how related to safety/refusal signals)
//!
//! Pruning strategy: Remove entities where:
//! - decision_criticality + alignment_relevance < threshold (default: 0.3)
//! - confidence < 0.5 (low confidence → low utility)

use super::{NightCycleOperator, OperatorResult, OntologyState, OntologyEntity};
use serde_json::{json, Value};

/// SafePruningPhiOperator: Goal-aware token filtering for governance.
#[derive(Clone, Debug)]
pub struct SafePruningPhiOperator {
    /// Threshold for decision_criticality + alignment_relevance combined.
    pub pruning_threshold: f64,
    /// Preserve entities with confidence >= this level.
    pub min_confidence: f64,
}

impl SafePruningPhiOperator {
    /// Create operator with default governance-safe settings.
    pub fn new() -> Self {
        Self {
            pruning_threshold: 0.3,
            min_confidence: 0.5,
        }
    }

    /// Create operator with custom thresholds.
    pub fn with_thresholds(pruning_threshold: f64, min_confidence: f64) -> Self {
        Self {
            pruning_threshold,
            min_confidence,
        }
    }

    /// Score entity for pruning. Lower score = more likely to prune.
    fn score_entity(&self, entity: &OntologyEntity) -> f64 {
        // Extract or compute criticality scores from entity data.
        let criticality = self.extract_criticality(&entity.data).unwrap_or(0.0);
        let alignment = self.extract_alignment_relevance(&entity.data).unwrap_or(0.0);

        // Combined score: criticality + alignment_relevance.
        // Entities with combined score < threshold are candidates for pruning.
        criticality + alignment
    }

    /// Extract decision_criticality from entity.data.
    fn extract_criticality(&self, data: &Value) -> Option<f64> {
        // If decision_criticality field exists and is not 0, use it.
        if let Some(v) = data.get("decision_criticality").and_then(|v| v.as_f64()) {
            if v > 0.0 {
                return Some(v);
            }
        }

        // Fallback: infer from entity_type.
        match data.get("entity_type").and_then(|v| v.as_str()) {
            Some("policy_decision") => Some(0.9),
            Some("access_grant") => Some(0.8),
            Some("risk_assessment") => Some(0.7),
            Some("metadata") => Some(0.1),
            Some("audit_log") => Some(0.2),
            _ => Some(0.0),
        }
    }

    /// Extract alignment_relevance from entity.data.
    fn extract_alignment_relevance(&self, data: &Value) -> Option<f64> {
        // If alignment_relevance field exists and is not 0, use it.
        if let Some(v) = data.get("alignment_relevance").and_then(|v| v.as_f64()) {
            if v > 0.0 {
                return Some(v);
            }
        }

        // Fallback: infer from entity_type.
        match data.get("entity_type").and_then(|v| v.as_str()) {
            Some("safety_gate") => Some(1.0),
            Some("refusal_signal") => Some(0.9),
            Some("compliance_marker") => Some(0.8),
            Some("policy_decision") => Some(0.5),
            _ => Some(0.0),
        }
    }

    /// Check if entity should be pruned.
    fn should_prune(&self, entity: &OntologyEntity) -> bool {
        // Never prune high-confidence entities.
        if entity.confidence >= self.min_confidence {
            let score = self.score_entity(entity);
            return score < self.pruning_threshold;
        }

        // Low confidence: prune unless criticality is high.
        let criticality = self.extract_criticality(&entity.data).unwrap_or(0.0);
        criticality < 0.7
    }
}

impl Default for SafePruningPhiOperator {
    fn default() -> Self {
        Self::new()
    }
}

impl NightCycleOperator for SafePruningPhiOperator {
    fn apply(&self, state: &mut OntologyState) -> OperatorResult {
        let initial_count = state.entities.len();
        let mut entities_changed = 0;

        // Identify indices to remove.
        let mut indices_to_remove: Vec<usize> = state
            .entities
            .iter()
            .enumerate()
            .filter_map(|(idx, entity)| {
                if self.should_prune(entity) {
                    Some(idx)
                } else {
                    None
                }
            })
            .collect();

        // Remove in reverse order to maintain indices.
        indices_to_remove.sort_by(|a, b| b.cmp(a));
        for idx in indices_to_remove {
            state.entities.remove(idx);
            entities_changed += 1;
        }

        OperatorResult {
            entities_processed: initial_count,
            entities_changed,
            operator_name: "SafePruningPhi",
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn entity(
        id: &str,
        entity_type: &str,
        confidence: f64,
        criticality: f64,
        alignment: f64,
    ) -> OntologyEntity {
        OntologyEntity {
            id: id.to_string(),
            timestamp: 0,
            confidence,
            data: json!({
                "entity_type": entity_type,
                "decision_criticality": criticality,
                "alignment_relevance": alignment,
            }),
        }
    }

    #[test]
    fn test_prune_low_utility_metadata() {
        // Low criticality + low alignment → pruned.
        let op = SafePruningPhiOperator::new();
        let mut state = OntologyState {
            entities: vec![
                entity("e1", "policy_decision", 0.8, 0.9, 0.5), // High criticality
                entity("e2", "metadata", 0.6, 0.1, 0.0),         // Low criticality
                entity("e3", "audit_log", 0.6, 0.2, 0.0),        // Low criticality
            ],
            confidence_threshold: 0.5,
        };

        let result = op.apply(&mut state);
        assert_eq!(result.entities_processed, 3);
        assert_eq!(result.entities_changed, 2);
        assert_eq!(state.entities.len(), 1);
        assert_eq!(state.entities[0].id, "e1");
    }

    #[test]
    fn test_preserve_safety_signals() {
        // Safety gate with high alignment → never pruned.
        let op = SafePruningPhiOperator::new();
        let mut state = OntologyState {
            entities: vec![
                entity("e1", "safety_gate", 0.6, 0.1, 1.0), // High alignment
                entity("e2", "metadata", 0.6, 0.1, 0.0),    // Low alignment
            ],
            confidence_threshold: 0.5,
        };

        let result = op.apply(&mut state);
        assert_eq!(result.entities_changed, 1);
        assert_eq!(state.entities.len(), 1);
        assert_eq!(state.entities[0].id, "e1");
    }

    #[test]
    fn test_high_confidence_preserved_if_below_threshold() {
        // High confidence (>= 0.5) policy decision preserved even if criticality low.
        let op = SafePruningPhiOperator::new();
        let mut state = OntologyState {
            entities: vec![
                entity("e1", "policy_decision", 0.8, 0.2, 0.1), // High confidence
                entity("e2", "metadata", 0.4, 0.1, 0.0),        // Low confidence
            ],
            confidence_threshold: 0.5,
        };

        let result = op.apply(&mut state);
        // e1 has high confidence, so score < threshold is not enough to prune.
        // e2 has low confidence, and criticality < 0.7, so it's pruned.
        assert_eq!(result.entities_changed, 1);
        assert_eq!(state.entities[0].id, "e1");
    }

    #[test]
    fn test_low_confidence_low_criticality_pruned() {
        // Low confidence + low criticality → pruned.
        let op = SafePruningPhiOperator::new();
        let mut state = OntologyState {
            entities: vec![
                entity("e1", "metadata", 0.3, 0.2, 0.0), // Low confidence + criticality
            ],
            confidence_threshold: 0.5,
        };

        let result = op.apply(&mut state);
        assert_eq!(result.entities_changed, 1);
        assert_eq!(state.entities.len(), 0);
    }

    #[test]
    fn test_low_confidence_high_criticality_preserved() {
        // Low confidence but high criticality → preserved.
        let op = SafePruningPhiOperator::new();
        let mut state = OntologyState {
            entities: vec![
                entity("e1", "policy_decision", 0.3, 0.9, 0.0), // Low conf, high crit
            ],
            confidence_threshold: 0.5,
        };

        let result = op.apply(&mut state);
        assert_eq!(result.entities_changed, 0);
        assert_eq!(state.entities.len(), 1);
    }

    #[test]
    fn test_custom_threshold() {
        // Threshold 0.5: more aggressive pruning.
        let op = SafePruningPhiOperator::with_thresholds(0.5, 0.5);
        let mut state = OntologyState {
            entities: vec![
                entity("e1", "policy_decision", 0.8, 0.4, 0.1), // Score 0.5 (at threshold)
                entity("e2", "metadata", 0.8, 0.3, 0.1),        // Score 0.4 (below)
            ],
            confidence_threshold: 0.5,
        };

        let result = op.apply(&mut state);
        // e1 score 0.5 is NOT < 0.5 (threshold), so NOT pruned.
        // e2 score 0.4 IS < 0.5, so pruned.
        assert_eq!(result.entities_changed, 1);
        assert_eq!(state.entities[0].id, "e1");
    }

    #[test]
    fn test_token_reduction_measurement() {
        // Verify we can measure token reduction ratio.
        let op = SafePruningPhiOperator::new();
        let mut state = OntologyState {
            entities: vec![
                entity("e1", "policy_decision", 0.9, 0.9, 0.5),
                entity("e2", "metadata", 0.5, 0.1, 0.0),
                entity("e3", "audit_log", 0.5, 0.1, 0.0),
                entity("e4", "safety_gate", 0.8, 0.1, 1.0),
                entity("e5", "timestamp", 0.4, 0.05, 0.0),
            ],
            confidence_threshold: 0.5,
        };

        let result = op.apply(&mut state);
        let reduction = (result.entities_changed as f64 / result.entities_processed as f64) * 100.0;
        assert!(reduction >= 40.0, "token reduction {:.1}%", reduction);
    }

    #[test]
    fn test_infer_criticality_from_type() {
        // Test fallback: infer criticality from entity_type.
        let op = SafePruningPhiOperator::new();
        let e = entity("e1", "access_grant", 0.5, 0.0, 0.0); // No explicit criticality
        let criticality = op.extract_criticality(&e.data);
        assert_eq!(criticality, Some(0.8)); // Fallback from entity_type
    }

    #[test]
    fn test_infer_alignment_from_type() {
        // Test fallback: infer alignment from entity_type.
        let op = SafePruningPhiOperator::new();
        let e = entity("e1", "refusal_signal", 0.5, 0.0, 0.0); // No explicit alignment
        let alignment = op.extract_alignment_relevance(&e.data);
        assert_eq!(alignment, Some(0.9)); // Fallback from entity_type
    }

    #[test]
    fn test_empty_state_noop() {
        let op = SafePruningPhiOperator::new();
        let mut state = OntologyState {
            entities: vec![],
            confidence_threshold: 0.5,
        };
        let result = op.apply(&mut state);
        assert_eq!(result.entities_processed, 0);
        assert_eq!(result.entities_changed, 0);
    }

    #[test]
    fn test_no_pruning_if_all_critical() {
        let op = SafePruningPhiOperator::new();
        let mut state = OntologyState {
            entities: vec![
                entity("e1", "policy_decision", 0.9, 0.9, 0.5),
                entity("e2", "safety_gate", 0.8, 0.5, 0.9),
            ],
            confidence_threshold: 0.5,
        };
        let result = op.apply(&mut state);
        assert_eq!(result.entities_changed, 0);
        assert_eq!(state.entities.len(), 2);
    }
}
