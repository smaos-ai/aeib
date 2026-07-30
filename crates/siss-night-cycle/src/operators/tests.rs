#[cfg(test)]
mod tests {
    use crate::operators::{
        DeltaOperator, GammaOperator, NightCycleOperator, OntologyEntity, OntologyState,
        PhiOperator,
    };

    /// Helper: create test entity with id, timestamp, confidence
    fn test_entity(id: &str, timestamp: i64, confidence: f64) -> OntologyEntity {
        OntologyEntity {
            id: id.to_string(),
            timestamp,
            confidence,
            data: serde_json::json!({"value": id}),
        }
    }

    /// test_phi_merges_duplicates: PhiOperator detects duplicate entities (same id) and merges to one
    #[test]
    fn test_phi_merges_duplicates() {
        let mut state = OntologyState {
            entities: vec![
                test_entity("entity_1", 100, 0.8),
                test_entity("entity_1", 110, 0.9),
                test_entity("entity_2", 105, 0.75),
            ],
            confidence_threshold: 0.5,
        };

        let phi = PhiOperator;
        let result = phi.apply(&mut state);

        // Should merge 2 duplicates into 1, keep entity_2 → 2 entities remain
        assert_eq!(state.entities.len(), 2);
        assert_eq!(result.entities_processed, 3);
        assert_eq!(result.entities_changed, 1); // 1 merge operation
        assert_eq!(result.operator_name, "Phi");
    }

    /// test_phi_preserves_confidence: merged entity retains the highest confidence value
    #[test]
    fn test_phi_preserves_confidence() {
        let mut state = OntologyState {
            entities: vec![
                test_entity("node_1", 100, 0.5),
                test_entity("node_1", 110, 0.95),
                test_entity("node_1", 90, 0.3),
            ],
            confidence_threshold: 0.1,
        };

        let phi = PhiOperator;
        phi.apply(&mut state);

        assert_eq!(state.entities.len(), 1);
        assert!((state.entities[0].confidence - 0.95).abs() < f64::EPSILON);
    }

    /// test_delta_supersedes_old_version: DeltaOperator replaces old version (lower timestamp) with new
    #[test]
    fn test_delta_supersedes_old_version() {
        let mut state = OntologyState {
            entities: vec![
                test_entity("config_v1", 100, 0.8),
                test_entity("config_v2", 200, 0.9),
                test_entity("config_v1", 300, 0.85), // newer version of config_v1
            ],
            confidence_threshold: 0.5,
        };

        let delta = DeltaOperator;
        let result = delta.apply(&mut state);

        // Should keep only the newest version of each id by timestamp
        // config_v1@300, config_v2@200 → 2 entities
        assert_eq!(state.entities.len(), 2);

        let config_v1 = state.entities.iter().find(|e| e.id == "config_v1").unwrap();
        assert_eq!(config_v1.timestamp, 300); // newest

        assert_eq!(result.entities_processed, 3);
        assert_eq!(result.entities_changed, 1); // old config_v1@100 removed
        assert_eq!(result.operator_name, "Delta");
    }

    /// test_gamma_rejects_low_confidence: GammaOperator filters entities below threshold
    #[test]
    fn test_gamma_rejects_low_confidence() {
        let mut state = OntologyState {
            entities: vec![
                test_entity("high_conf", 100, 0.9),
                test_entity("low_conf", 110, 0.3),
                test_entity("mid_conf", 120, 0.7),
            ],
            confidence_threshold: 0.6,
        };

        let gamma = GammaOperator;
        let result = gamma.apply(&mut state);

        // Should keep only entities with confidence >= 0.6
        assert_eq!(state.entities.len(), 2);
        assert!(state.entities.iter().all(|e| e.confidence >= 0.6));

        assert_eq!(result.entities_processed, 3);
        assert_eq!(result.entities_changed, 1); // 1 entity removed (low_conf)
        assert_eq!(result.operator_name, "Gamma");
    }

    /// test_operator_chain_phi_delta_gamma: chain all three operators in sequence
    #[test]
    fn test_operator_chain_phi_delta_gamma() {
        let mut state = OntologyState {
            entities: vec![
                test_entity("entity_1", 100, 0.8),
                test_entity("entity_1", 110, 0.9), // dup, phi merges
                test_entity("config", 150, 0.3),   // gamma filters
                test_entity("config", 200, 0.95),  // newer, delta keeps
                test_entity("entity_2", 120, 0.75),
            ],
            confidence_threshold: 0.6,
        };

        let phi = PhiOperator;
        let delta = DeltaOperator;
        let gamma = GammaOperator;

        phi.apply(&mut state);
        delta.apply(&mut state);
        gamma.apply(&mut state);

        // After phi: entity_1 merged (4 remain)
        // After delta: config@150 removed, config@200 kept (still 4)
        // After gamma: config@200 kept (0.95 >= 0.6), config@150 already gone
        // Final: entity_1 (merged), config@200, entity_2 → 3 entities
        assert_eq!(state.entities.len(), 3);

        // All remaining should be high confidence
        assert!(state.entities.iter().all(|e| e.confidence >= 0.6));
    }

    /// test_empty_state_noop: operators on empty state do nothing, no panic
    #[test]
    fn test_empty_state_noop() {
        let mut state = OntologyState {
            entities: vec![],
            confidence_threshold: 0.5,
        };

        let phi = PhiOperator;
        let delta = DeltaOperator;
        let gamma = GammaOperator;

        let result_phi = phi.apply(&mut state);
        let result_delta = delta.apply(&mut state);
        let result_gamma = gamma.apply(&mut state);

        assert_eq!(state.entities.len(), 0);
        assert_eq!(result_phi.entities_processed, 0);
        assert_eq!(result_delta.entities_processed, 0);
        assert_eq!(result_gamma.entities_processed, 0);
    }

    /// test_delta_preserves_metadata: superseded entity retains all fields of the newest version
    #[test]
    fn test_delta_preserves_metadata() {
        use serde_json::json;

        let mut state = OntologyState {
            entities: vec![
                OntologyEntity {
                    id: "doc_1".to_string(),
                    timestamp: 50,
                    confidence: 0.7,
                    data: json!({"version": "old", "author": "alice"}),
                },
                OntologyEntity {
                    id: "doc_1".to_string(),
                    timestamp: 200,
                    confidence: 0.88,
                    data: json!({"version": "new", "author": "bob", "extra": true}),
                },
            ],
            confidence_threshold: 0.5,
        };

        let delta = DeltaOperator;
        delta.apply(&mut state);

        assert_eq!(state.entities.len(), 1);
        let kept = &state.entities[0];
        assert_eq!(kept.timestamp, 200);
        assert!((kept.confidence - 0.88).abs() < f64::EPSILON);
        assert_eq!(kept.data["version"], "new");
        assert_eq!(kept.data["author"], "bob");
        assert_eq!(kept.data["extra"], true);
    }

    /// test_gamma_scores_correctly: entities at exactly the threshold boundary are retained
    #[test]
    fn test_gamma_scores_correctly() {
        let threshold = 0.6_f64;
        let mut state = OntologyState {
            entities: vec![
                test_entity("at_threshold", 100, threshold),
                test_entity("above_threshold", 110, threshold + 0.01),
                test_entity("below_threshold", 120, threshold - 0.01),
            ],
            confidence_threshold: threshold,
        };

        let gamma = GammaOperator;
        let result = gamma.apply(&mut state);

        assert_eq!(
            state.entities.len(),
            2,
            "entities at and above threshold are kept"
        );
        assert_eq!(
            result.entities_changed, 1,
            "exactly one below-threshold entity removed"
        );
        assert!(
            state.entities.iter().all(|e| e.confidence >= threshold),
            "no entity below threshold survives"
        );
        assert!(state.entities.iter().any(|e| e.id == "at_threshold"));
    }
}
