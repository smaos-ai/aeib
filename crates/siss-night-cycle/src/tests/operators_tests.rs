#[cfg(test)]
mod operators_tests {
    use uuid::Uuid;

    #[derive(Debug, Clone)]
    struct OntologyEntity {
        id: String,
        name: String,
        version: usize,
        confidence: f64,
    }

    #[derive(Debug)]
    struct OntologyState {
        entities: Vec<OntologyEntity>,
        confidence_threshold: f64,
    }

    #[derive(Debug)]
    struct OperatorResult {
        entities_processed: usize,
        entities_changed: usize,
        operator_name: &'static str,
    }

    trait NightCycleOperator {
        fn apply(&self, state: &mut OntologyState) -> OperatorResult;
    }

    struct PhiOperator;
    struct DeltaOperator;
    struct GammaOperator;

    impl NightCycleOperator for PhiOperator {
        fn apply(&self, state: &mut OntologyState) -> OperatorResult {
            let initial_len = state.entities.len();
            state.entities.sort_by(|a, b| a.id.cmp(&b.id));
            state.entities.dedup_by(|a, b| a.id == b.id);
            let final_len = state.entities.len();

            OperatorResult {
                entities_processed: initial_len,
                entities_changed: initial_len - final_len,
                operator_name: "Phi",
            }
        }
    }

    impl NightCycleOperator for DeltaOperator {
        fn apply(&self, state: &mut OntologyState) -> OperatorResult {
            let initial_len = state.entities.len();
            state.entities.sort_by(|a, b| {
                a.id.cmp(&b.id).then(b.version.cmp(&a.version))
            });
            state.entities.dedup_by(|a, b| a.id == b.id);
            let final_len = state.entities.len();

            OperatorResult {
                entities_processed: initial_len,
                entities_changed: initial_len - final_len,
                operator_name: "Delta",
            }
        }
    }

    impl NightCycleOperator for GammaOperator {
        fn apply(&self, state: &mut OntologyState) -> OperatorResult {
            let initial_len = state.entities.len();
            state.entities.retain(|e| e.confidence >= state.confidence_threshold);
            let final_len = state.entities.len();

            OperatorResult {
                entities_processed: initial_len,
                entities_changed: initial_len - final_len,
                operator_name: "Gamma",
            }
        }
    }

    #[test]
    fn test_phi_merges_duplicates() {
        let phi = PhiOperator;
        let mut state = OntologyState {
            entities: vec![
                OntologyEntity { id: "1".to_string(), name: "Entity A".to_string(), version: 1, confidence: 0.9 },
                OntologyEntity { id: "1".to_string(), name: "Entity A".to_string(), version: 1, confidence: 0.9 },
            ],
            confidence_threshold: 0.8,
        };

        let result = phi.apply(&mut state);
        assert_eq!(state.entities.len(), 1, "Phi should merge duplicates");
        assert_eq!(result.entities_changed, 1, "One entity should be removed");
    }

    #[test]
    fn test_delta_supersedes_old_version() {
        let delta = DeltaOperator;
        let mut state = OntologyState {
            entities: vec![
                OntologyEntity { id: "1".to_string(), name: "Entity A".to_string(), version: 1, confidence: 0.9 },
                OntologyEntity { id: "1".to_string(), name: "Entity A v2".to_string(), version: 2, confidence: 0.9 },
            ],
            confidence_threshold: 0.8,
        };

        let result = delta.apply(&mut state);
        assert_eq!(state.entities.len(), 1, "Delta should keep newest version only");
        assert_eq!(state.entities[0].version, 2, "Should keep v2");
    }

    #[test]
    fn test_gamma_filters_low_confidence() {
        let gamma = GammaOperator;
        let mut state = OntologyState {
            entities: vec![
                OntologyEntity { id: "1".to_string(), name: "High conf".to_string(), version: 1, confidence: 0.9 },
                OntologyEntity { id: "2".to_string(), name: "Low conf".to_string(), version: 1, confidence: 0.5 },
            ],
            confidence_threshold: 0.8,
        };

        let result = gamma.apply(&mut state);
        assert_eq!(state.entities.len(), 1, "Gamma should filter low-confidence");
        assert_eq!(result.entities_changed, 1, "One entity should be filtered");
    }

    #[test]
    fn test_operator_chain_phi_delta_gamma() {
        let phi = PhiOperator;
        let delta = DeltaOperator;
        let gamma = GammaOperator;

        let mut state = OntologyState {
            entities: vec![
                OntologyEntity { id: "1".to_string(), name: "A".to_string(), version: 1, confidence: 0.9 },
                OntologyEntity { id: "1".to_string(), name: "A".to_string(), version: 2, confidence: 0.9 },
                OntologyEntity { id: "2".to_string(), name: "B".to_string(), version: 1, confidence: 0.5 },
            ],
            confidence_threshold: 0.8,
        };

        phi.apply(&mut state);
        delta.apply(&mut state);
        let result = gamma.apply(&mut state);

        assert_eq!(state.entities.len(), 1, "Chain should result in 1 entity (high conf, latest version)");
    }

    #[test]
    fn test_empty_state_noop() {
        let phi = PhiOperator;
        let mut state = OntologyState {
            entities: vec![],
            confidence_threshold: 0.8,
        };

        let result = phi.apply(&mut state);
        assert_eq!(state.entities.len(), 0, "Empty state should remain empty");
        assert_eq!(result.entities_changed, 0, "No changes on empty state");
    }
}
