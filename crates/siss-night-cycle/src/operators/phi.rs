use super::{NightCycleOperator, OperatorResult, OntologyState};
use std::collections::HashMap;

/// PhiOperator: Consolidation — merge duplicate entities by id, keep highest confidence
pub struct PhiOperator;

impl NightCycleOperator for PhiOperator {
    fn apply(&self, state: &mut OntologyState) -> OperatorResult {
        let initial_count = state.entities.len();
        let mut entities_changed = 0;

        // Group entities by id
        let mut groups: HashMap<String, Vec<usize>> = HashMap::new();
        for (idx, entity) in state.entities.iter().enumerate() {
            groups.entry(entity.id.clone()).or_default().push(idx);
        }

        // Merge duplicates: keep the one with highest confidence
        let mut indices_to_remove = Vec::new();
        for (_id, indices) in groups.iter() {
            if indices.len() > 1 {
                // Find index with highest confidence
                let max_idx = indices
                    .iter()
                    .max_by(|&&a, &&b| {
                        state.entities[a]
                            .confidence
                            .partial_cmp(&state.entities[b].confidence)
                            .unwrap_or(std::cmp::Ordering::Equal)
                    })
                    .copied()
                    .unwrap();

                // Mark all others for removal
                for &idx in indices.iter() {
                    if idx != max_idx {
                        indices_to_remove.push(idx);
                        entities_changed += 1;
                    }
                }
            }
        }

        // Remove in reverse order to maintain indices
        indices_to_remove.sort_by(|a, b| b.cmp(a));
        for idx in indices_to_remove {
            state.entities.remove(idx);
        }

        OperatorResult {
            entities_processed: initial_count,
            entities_changed,
            operator_name: "Phi",
        }
    }
}
