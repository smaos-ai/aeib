use chrono::{DateTime, Utc, Duration};
use uuid::Uuid;
use siss_context_cartography::confidence_scorer::{
    SourceType, ConfidenceSource, calculate_confidence, compute_source_weight,
    compute_corroboration_boost, detect_contradiction,
};
use siss_context_cartography::llm_wiki_v2::SemanticFact;

// Test 1: Source trust weights vary by type
#[test]
fn test_source_trust_weights_vary_by_type() {
    let human_weight = compute_source_weight(SourceType::Human);
    let llm_weight = compute_source_weight(SourceType::LLM);
    let api_weight = compute_source_weight(SourceType::API);
    let document_weight = compute_source_weight(SourceType::Document);

    assert!(human_weight >= 0.90, "Human should have high weight");
    assert!(llm_weight >= 0.65 && llm_weight < human_weight, "LLM should be medium");
    assert!(api_weight >= 0.55 && api_weight < llm_weight, "API should be lower");
    assert!(document_weight >= 0.70 && document_weight < human_weight, "Document should be medium-high");

    // Determinism: same input always gives same output
    let human_weight_2 = compute_source_weight(SourceType::Human);
    assert_eq!(human_weight, human_weight_2, "Weights must be deterministic");
}

// Test 2: Corroboration increases confidence
#[test]
fn test_corroboration_increases_confidence() {
    let single_source_boost = compute_corroboration_boost(1);
    let three_source_boost = compute_corroboration_boost(3);
    let five_source_boost = compute_corroboration_boost(5);

    assert_eq!(single_source_boost, 0.0, "Single source should have no boost");
    assert!(three_source_boost > single_source_boost, "Three sources should boost");
    assert!(five_source_boost > three_source_boost, "More sources = more boost");
    assert!(five_source_boost <= 0.15, "Max boost should be capped at 0.15");
}

// Test 3: Contradiction marks fact stale
#[test]
fn test_contradiction_marks_fact_stale() {
    let old_fact = SemanticFact {
        id: Uuid::new_v4(),
        fact: "The sky is blue".to_string(),
        confidence_score: 0.80,
        created_at: Utc::now(),
        last_accessed_at: Utc::now(),
        access_count: 5,
        superseded_by: None,
        is_stale: false,
        sources: vec!["human_input".to_string()],
    };

    let new_contradicting_fact = "The sky is not blue".to_string();
    let existing_facts = vec![old_fact.clone()];

    let contradiction_result = detect_contradiction(&new_contradicting_fact, &existing_facts);

    assert!(contradiction_result.is_some(), "Should detect contradiction");
    let contradicted_id = contradiction_result.unwrap();
    assert_eq!(contradicted_id, old_fact.id, "Should return old fact ID");
}

// Test 4: Temporal decay with Ebbinghaus
#[test]
fn test_temporal_decay_with_ebbinghaus() {
    let created_7_days_ago = Utc::now() - Duration::days(7);

    let sources = vec![
        ConfidenceSource {
            fact_id: Uuid::new_v4(),
            source_type: SourceType::Human,
            source_url: "user_input".to_string(),
            timestamp: created_7_days_ago,
        }
    ];

    let existing_facts = vec![];
    let (confidence, _) = calculate_confidence(&sources, &existing_facts);

    // Expected: 0.95 * exp(-7/7) ≈ 0.95 * exp(-1) ≈ 0.35
    // Allow some floating point tolerance
    assert!(confidence > 0.30 && confidence < 0.40,
        "7-day decay should yield confidence ~0.35, got {}", confidence);
}

// Test 5: Confidence calculation is deterministic
#[test]
fn test_confidence_calculation_deterministic() {
    let sources = vec![
        ConfidenceSource {
            fact_id: Uuid::nil(),
            source_type: SourceType::LLM,
            source_url: "test".to_string(),
            timestamp: Utc::now(),
        },
        ConfidenceSource {
            fact_id: Uuid::nil(),
            source_type: SourceType::Document,
            source_url: "doc.pdf".to_string(),
            timestamp: Utc::now(),
        }
    ];

    let existing_facts = vec![];

    let mut results = Vec::new();
    for _ in 0..10 {
        let (confidence, contradiction) = calculate_confidence(&sources, &existing_facts);
        results.push((confidence, contradiction));
    }

    // All results should be identical
    for i in 1..results.len() {
        assert_eq!(results[0].0, results[i].0,
            "Confidence scores must be deterministic, iteration {} differs", i);
        assert_eq!(results[0].1, results[i].1,
            "Contradiction detection must be deterministic, iteration {} differs", i);
    }
}
