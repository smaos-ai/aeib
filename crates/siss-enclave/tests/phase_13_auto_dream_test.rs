use siss_enclave::memory::{
    CartographicOperators, ConsolidatedEntry, GrayFog, ObservationTier, RawObservation, ZonalMemory,
};
use std::time::Duration;

#[tokio::test]
async fn test_write_rejected_when_buffer_full() {
    let zonal = ZonalMemory::new(
        2,   // capacity=2
        100, // max_tokens_per_entry
        0.9, // jaccard_threshold
        100, // cycle_interval_ms
    );

    let obs1 = RawObservation::new("test1".to_string(), 0.8, ObservationTier::Semantic);
    let obs2 = RawObservation::new("test2".to_string(), 0.9, ObservationTier::Semantic);
    let obs3 = RawObservation::new("test3".to_string(), 0.7, ObservationTier::Semantic);

    // First two writes should succeed (buffer capacity=2)
    assert_eq!(zonal.write(obs1), true, "First write should succeed");
    assert_eq!(zonal.write(obs2), true, "Second write should succeed");

    // Third write should fail (buffer full, fail-closed)
    assert_eq!(
        zonal.write(obs3),
        false,
        "Third write should be rejected when full"
    );
}

#[test]
fn test_simplification_truncates_oversized_entry() {
    let ops = CartographicOperators::new(4, 0.9); // max_tokens=4

    // "hello world foo bar baz" is 23 chars = 5.75 tokens @ 0.25 tokens/char
    let obs = RawObservation::new(
        "hello world foo bar baz".to_string(),
        0.8,
        ObservationTier::Semantic,
    );
    assert!(obs.token_count() > 4, "Input should exceed max_tokens");

    let simplified = ops.simplify(vec![obs]);

    assert_eq!(simplified.len(), 1, "Should have one entry after simplify");
    // Content should be truncated to (4.0 / 0.25) = 16 chars
    assert_eq!(
        simplified[0].content.len(),
        16,
        "Content should be truncated to 16 chars"
    );
}

#[test]
fn test_aggregation_merges_near_duplicate_entries() {
    let ops = CartographicOperators::new(100, 0.6); // jaccard_threshold=0.6

    // Identical content, different confidence
    let obs_a = RawObservation::new(
        "the cat sat on the mat".to_string(),
        0.7,
        ObservationTier::Semantic,
    );
    let obs_b = RawObservation::new(
        "the cat sat on the mat".to_string(),
        0.9,
        ObservationTier::Semantic,
    );

    let aggregated = ops.aggregate(vec![obs_a, obs_b]);

    assert_eq!(
        aggregated.len(),
        1,
        "Should merge identical entries into one"
    );
    assert_eq!(
        aggregated[0].confidence, 0.9,
        "Should keep entry with higher confidence"
    );
}

#[test]
fn test_aggregation_preserves_distinct_entries() {
    let ops = CartographicOperators::new(100, 0.6); // jaccard_threshold=0.6

    // Very different content (low Jaccard similarity)
    let obs_a = RawObservation::new(
        "rust ownership model".to_string(),
        0.8,
        ObservationTier::Semantic,
    );
    let obs_b = RawObservation::new(
        "python dynamic typing".to_string(),
        0.7,
        ObservationTier::Semantic,
    );

    let aggregated = ops.aggregate(vec![obs_a, obs_b]);

    assert_eq!(aggregated.len(), 2, "Should preserve distinct entries");
}

#[test]
fn test_layering_buckets_by_tier() {
    let ops = CartographicOperators::new(100, 0.9);

    let obs1 = RawObservation::new("obs1".to_string(), 0.8, ObservationTier::Semantic);
    let obs2 = RawObservation::new("obs2".to_string(), 0.8, ObservationTier::Semantic);
    let obs3 = RawObservation::new("obs3".to_string(), 0.7, ObservationTier::Episodic);
    let obs4 = RawObservation::new("obs4".to_string(), 0.9, ObservationTier::Procedural);

    let layered = ops.layer(vec![obs1, obs2, obs3, obs4]);

    assert_eq!(
        layered.get(&ObservationTier::Semantic).unwrap().len(),
        2,
        "Semantic should have 2 entries"
    );
    assert_eq!(
        layered.get(&ObservationTier::Episodic).unwrap().len(),
        1,
        "Episodic should have 1 entry"
    );
    assert_eq!(
        layered.get(&ObservationTier::Procedural).unwrap().len(),
        1,
        "Procedural should have 1 entry"
    );
    assert!(
        layered.get(&ObservationTier::Working).is_none(),
        "Working should not be present (no inputs)"
    );
}

#[tokio::test]
async fn test_auto_dream_consolidates_buffer_to_gray_fog() {
    let zonal = ZonalMemory::new(
        10,   // capacity=10
        100,  // max_tokens_per_entry
        0.95, // jaccard_threshold
        20,   // cycle_interval_ms
    );

    let obs1 = RawObservation::new("obs1".to_string(), 0.8, ObservationTier::Semantic);
    let obs2 = RawObservation::new("obs2".to_string(), 0.8, ObservationTier::Semantic);
    let obs3 = RawObservation::new("obs3".to_string(), 0.7, ObservationTier::Semantic);

    // Write three observations to buffer
    zonal.write(obs1);
    zonal.write(obs2);
    zonal.write(obs3);

    // Wait for multiple consolidation cycles (5 cycles @ 20ms = 100ms)
    tokio::time::sleep(Duration::from_millis(100)).await;

    let snapshot = zonal.fog_snapshot();
    assert!(
        snapshot.total_entries() >= 1,
        "Gray Fog should be populated after auto-dream consolidation"
    );
}

#[tokio::test]
async fn test_projection_respects_token_budget_and_sorts_by_confidence() {
    use uuid::Uuid;

    // Manually construct a GrayFog with seeded entries
    let mut layers = std::collections::HashMap::new();
    let entries = vec![
        ConsolidatedEntry {
            id: Uuid::new_v4(),
            content: "entry_a".to_string(),
            confidence: 0.9,
            tier: ObservationTier::Semantic,
            token_count: 50,
        },
        ConsolidatedEntry {
            id: Uuid::new_v4(),
            content: "entry_b".to_string(),
            confidence: 0.7,
            tier: ObservationTier::Episodic,
            token_count: 50,
        },
        ConsolidatedEntry {
            id: Uuid::new_v4(),
            content: "entry_c".to_string(),
            confidence: 0.5,
            tier: ObservationTier::Procedural,
            token_count: 50,
        },
    ];

    layers.insert(ObservationTier::Semantic, vec![entries[0].clone()]);
    layers.insert(ObservationTier::Episodic, vec![entries[1].clone()]);
    layers.insert(ObservationTier::Procedural, vec![entries[2].clone()]);

    let fog = GrayFog { layers };
    let zonal = ZonalMemory::with_fog(fog, 10);

    // Test 1: budget=80 should only fit highest-confidence entry (50 tokens)
    let result = zonal.project(80);
    assert_eq!(result.len(), 1, "Budget 80 should fit 1 entry");
    assert_eq!(result[0].confidence, 0.9, "Should get highest confidence");

    // Test 2: budget=100 should fit two entries (50+50=100 tokens)
    let result = zonal.project(100);
    assert_eq!(result.len(), 2, "Budget 100 should fit 2 entries");
    assert_eq!(result[0].confidence, 0.9, "First entry should be highest");
    assert_eq!(
        result[1].confidence, 0.7,
        "Second entry should be second-highest"
    );

    // Test 3: budget=150 should fit all three entries
    let result = zonal.project(150);
    assert_eq!(result.len(), 3, "Budget 150 should fit all 3 entries");
    assert_eq!(result[0].confidence, 0.9);
    assert_eq!(result[1].confidence, 0.7);
    assert_eq!(result[2].confidence, 0.5);
}
