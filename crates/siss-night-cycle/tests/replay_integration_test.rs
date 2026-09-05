use serde_json::json;
/// Integration test for Night Cycle Deterministic Replay Engine
/// Demonstrates end-to-end replay workflow with φ/δ/γ operators
use siss_night_cycle::operators::{
    DeltaOperator, GammaOperator, NightCycleOperator, OntologyEntity, OntologyState, PhiOperator,
};
use siss_night_cycle::replay_engine::{FileBasedReplayLog, ReplayEngine};

fn create_entity(id: &str, timestamp: i64, confidence: f64) -> OntologyEntity {
    OntologyEntity {
        id: id.to_string(),
        timestamp,
        confidence,
        data: json!({"value": "test", "id": id}),
    }
}

#[test]
fn test_full_night_cycle_replay_workflow() {
    // Initialize replay engine
    let mut replay =
        FileBasedReplayLog::new("test_full_workflow.json").expect("Failed to create replay engine");

    // Create initial ontology state with duplicates and varying confidence
    let initial_entities = vec![
        create_entity("e1", 1000, 0.95),
        create_entity("e1", 1001, 0.90), // duplicate with lower confidence
        create_entity("e2", 1000, 0.85),
        create_entity("e3", 1000, 0.70),
        create_entity("e3", 1002, 0.75), // newer version of e3
    ];

    // === PHASE 1: PHI OPERATOR (Consolidation) ===
    let mut state = OntologyState {
        entities: initial_entities.clone(),
        confidence_threshold: 0.0,
    };

    let phi = PhiOperator;
    let result = phi.apply(&mut state);

    // Record phi transition
    replay
        .record_transition(
            "Phi".to_string(),
            initial_entities.clone(),
            state.entities.clone(),
            &result,
        )
        .expect("Failed to record Phi transition");

    println!(
        "Phi operator result: {} entities processed, {} changed",
        result.entities_processed, result.entities_changed
    );
    assert_eq!(state.entities.len(), 3); // Should consolidate duplicates by keeping highest confidence

    // === PHASE 2: DELTA OPERATOR (Supersession) ===
    let entities_before_delta = state.entities.clone();
    let delta = DeltaOperator;
    let result = delta.apply(&mut state);

    replay
        .record_transition(
            "Delta".to_string(),
            entities_before_delta.clone(),
            state.entities.clone(),
            &result,
        )
        .expect("Failed to record Delta transition");

    println!(
        "Delta operator result: {} entities processed, {} changed",
        result.entities_processed, result.entities_changed
    );

    // === PHASE 3: GAMMA OPERATOR (Causal Validation / Confidence Filtering) ===
    let entities_before_gamma = state.entities.clone();
    state.confidence_threshold = 0.75; // Filter entities below 75% confidence

    let gamma = GammaOperator;
    let result = gamma.apply(&mut state);

    replay
        .record_transition(
            "Gamma".to_string(),
            entities_before_gamma.clone(),
            state.entities.clone(),
            &result,
        )
        .expect("Failed to record Gamma transition");

    println!(
        "Gamma operator result: {} entities processed, {} changed",
        result.entities_processed, result.entities_changed
    );
    println!("Final state: {} entities", state.entities.len());

    // === VALIDATION ===

    // 1. Validate all constraints
    let validation = replay.validate_all();
    assert!(
        validation.is_ok(),
        "Validation failed: {:?}",
        validation.err()
    );

    // 2. Replay from empty and verify exact match
    let replayed_state = replay.replay().expect("Failed to replay to final state");

    assert_eq!(
        replayed_state.entities.len(),
        state.entities.len(),
        "Replayed state should match final state (entity count)"
    );

    for (i, entity) in state.entities.iter().enumerate() {
        let replayed_entity = &replayed_state.entities[i];
        assert_eq!(replayed_entity.id, entity.id, "Entity ID should match");
        assert_eq!(
            replayed_entity.timestamp, entity.timestamp,
            "Timestamp should match"
        );
        assert_eq!(
            replayed_entity.confidence, entity.confidence,
            "Confidence should match"
        );
    }

    // 3. Test replay to intermediate sequence (after Delta)
    let partial_state = replay
        .replay_to_sequence(1) // After Delta operator (sequence 1)
        .expect("Failed to replay to sequence 1");

    println!(
        "Partial state (after Delta): {} entities",
        partial_state.entities.len()
    );
    assert!(
        partial_state.entities.len() > 0,
        "Partial state should have entities"
    );

    // 4. Verify Merkle DAG
    let log = replay.get_log();
    assert_eq!(log.len(), 3, "Log should have 3 transitions");

    let merkle_result = log.validate_merkle_dag();
    assert!(
        merkle_result.is_ok(),
        "Merkle DAG validation failed: {:?}",
        merkle_result.err()
    );

    // 5. Verify Causality
    let causality_result = log.validate_causality();
    assert!(
        causality_result.is_ok(),
        "Causality validation failed: {:?}",
        causality_result.err()
    );

    println!("\n=== TEST PASSED ===");
    println!("Successfully replayed night cycle:");
    println!(
        "  - Phi (Consolidation): {} → {} entities",
        initial_entities.len(),
        entities_before_delta.len()
    );
    println!(
        "  - Delta (Supersession): {} → {} entities",
        entities_before_delta.len(),
        entities_before_gamma.len()
    );
    println!(
        "  - Gamma (Causal Validation): {} → {} entities",
        entities_before_gamma.len(),
        state.entities.len()
    );
    println!("  - Merkle DAG: Valid");
    println!("  - Causality: Valid");
    println!("  - Deterministic Replay: ✓ Exact match");

    // Cleanup
    let _ = std::fs::remove_file("test_full_workflow.json");
}

#[test]
fn test_replay_bitwise_equality_with_complex_data() {
    let mut replay =
        FileBasedReplayLog::new("test_complex_data.json").expect("Failed to create replay engine");

    // Create entity with complex nested data
    let entity = OntologyEntity {
        id: "complex_e1".to_string(),
        timestamp: 987654321,
        confidence: 0.9876543210,
        data: json!({
            "nested": {
                "deeply": {
                    "value": "test",
                    "array": [1, 2, 3, 4, 5],
                    "bool": true,
                    "null_val": null
                }
            },
            "precision": 3.141592653589793
        }),
    };

    let entities = vec![entity.clone()];

    replay
        .record_transition(
            "Phi".to_string(),
            entities.clone(),
            entities.clone(),
            &siss_night_cycle::operators::OperatorResult {
                entities_processed: 1,
                entities_changed: 0,
                operator_name: "Phi",
            },
        )
        .expect("Failed to record transition");

    let replayed = replay.replay().expect("Failed to replay");

    // Verify bitwise equality
    assert_eq!(replayed.entities[0].id, entity.id);
    assert_eq!(replayed.entities[0].timestamp, entity.timestamp);
    assert_eq!(replayed.entities[0].confidence, entity.confidence);
    assert_eq!(replayed.entities[0].data, entity.data);

    println!("Complex data bitwise equality: ✓");

    // Cleanup
    let _ = std::fs::remove_file("test_complex_data.json");
}

#[test]
fn test_replay_persistence_across_sessions() {
    let db_path = "test_persistence.json";

    // Session 1: Create and record
    {
        let mut replay = FileBasedReplayLog::new(db_path).expect("Failed to create replay engine");

        let entity = create_entity("e1", 1000, 0.9);
        replay
            .record_transition(
                "Phi".to_string(),
                vec![],
                vec![entity.clone()],
                &siss_night_cycle::operators::OperatorResult {
                    entities_processed: 1,
                    entities_changed: 0,
                    operator_name: "Phi",
                },
            )
            .expect("Failed to record transition");

        assert_eq!(replay.get_log().len(), 1);
    }

    // Session 2: Load from disk and continue
    {
        let mut replay =
            FileBasedReplayLog::load_from_file(db_path).expect("Failed to load replay engine");

        assert_eq!(replay.get_log().len(), 1, "Should load persisted log");

        let entity = create_entity("e2", 1001, 0.85);
        replay
            .record_transition(
                "Delta".to_string(),
                vec![create_entity("e1", 1000, 0.9)],
                vec![create_entity("e1", 1000, 0.9), entity],
                &siss_night_cycle::operators::OperatorResult {
                    entities_processed: 2,
                    entities_changed: 1,
                    operator_name: "Delta",
                },
            )
            .expect("Failed to record second transition");

        assert_eq!(replay.get_log().len(), 2, "Should have 2 transitions total");
    }

    // Session 3: Verify full log
    {
        let replay =
            FileBasedReplayLog::load_from_file(db_path).expect("Failed to load replay engine");

        assert_eq!(replay.get_log().len(), 2);
        assert_eq!(replay.get_log().records[0].operator_name, "Phi");
        assert_eq!(replay.get_log().records[1].operator_name, "Delta");
    }

    println!("Persistence across sessions: ✓");

    // Cleanup
    let _ = std::fs::remove_file(db_path);
}
