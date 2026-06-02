use super::{NightCycleOperator, OperatorResult, OntologyState};

/// GammaOperator: Causal Validation — filter out entities below confidence threshold
pub struct GammaOperator;

impl NightCycleOperator for GammaOperator {
    fn apply(&self, state: &mut OntologyState) -> OperatorResult {
        let initial_count = state.entities.len();

        // Filter: keep only entities with confidence >= threshold
        let threshold = state.confidence_threshold;
        state.entities.retain(|entity| entity.confidence >= threshold);

        let entities_changed = initial_count - state.entities.len();

        OperatorResult {
            entities_processed: initial_count,
            entities_changed,
            operator_name: "Gamma",
        }
    }
}
