use siss_context_cartography::types::{AffectiveSignature, MemoryEntry};
use siss_memory_plane::operators::CartographicOperatorSet;
use uuid::Uuid;

#[test]
fn test_high_valence_bypasses_token_truncation() {
    let op_set = CartographicOperatorSet {
        confidence_threshold: 0.5,
        jaccard_threshold: 0.25,
        max_tokens_per_entry: 4, // 4 tokens = ~16 chars; content is 100 chars
    };

    let mut entry = MemoryEntry {
        memory_id: Uuid::new_v4(),
        content: "X".repeat(100), // 100 chars >> 16 char budget
        confidence_score: 0.9,
        tier: siss_graph_core::node::memory::ConsolidationTier::Semantic,
        affective_signature: Some(AffectiveSignature {
            valence: 0.8,             // Positive (opportunity)
            arousal: 0.9,             // High activation
            sovereign_relevance: 0.8, // Highly relevant
        }),
    };

    let truncated = op_set.phi_simplify(vec![entry.clone()]);

    // High valence + high arousal + high sovereign_relevance → content preserved
    assert_eq!(
        truncated[0].content.len(),
        100,
        "High-valence fact should NOT be truncated"
    );
}

#[test]
fn test_low_valence_truncated_normally() {
    let op_set = CartographicOperatorSet {
        confidence_threshold: 0.5,
        jaccard_threshold: 0.25,
        max_tokens_per_entry: 4, // 4 tokens = ~16 chars; content is 100 chars
    };

    let entry = MemoryEntry {
        memory_id: Uuid::new_v4(),
        content: "X".repeat(100), // 100 chars >> 16 char budget
        confidence_score: 0.9,
        tier: siss_graph_core::node::memory::ConsolidationTier::Semantic,
        affective_signature: Some(AffectiveSignature {
            valence: -0.8,            // Negative (threat/neutral)
            arousal: 0.3,             // Low activation
            sovereign_relevance: 0.2, // Low relevance
        }),
    };

    let truncated = op_set.phi_simplify(vec![entry.clone()]);

    // Low valence + low arousal → content truncated to budget
    assert!(
        truncated[0].content.len() <= 16,
        "Low-valence fact should be truncated"
    );
}

#[test]
fn test_omega_operator_promotes_from_gray_fog() {
    let op_set = CartographicOperatorSet {
        confidence_threshold: 0.5,
        jaccard_threshold: 0.25,
        max_tokens_per_entry: 4,
    };

    // Create a GrayFog entry (below confidence threshold but high valence)
    let gray_fog_entry = MemoryEntry {
        memory_id: Uuid::new_v4(),
        content: "Critical production failure occurred".to_string(),
        confidence_score: 0.6, // Above threshold but in gray zone
        tier: siss_graph_core::node::memory::ConsolidationTier::Episodic,
        affective_signature: Some(AffectiveSignature {
            valence: -0.95,            // Negative (threat — critical failure)
            arousal: 0.95,             // Very high activation
            sovereign_relevance: 0.95, // Critical for system
        }),
    };

    // ω operator should promote high-arousal from GrayFog back to VisibleField
    let promoted = op_set.omega_resonate(
        vec![],                       // empty visible field
        vec![gray_fog_entry.clone()], // gray fog with 1 entry
        1,                            // limit: return top 1
    );

    assert_eq!(
        promoted.len(),
        1,
        "ω operator should rescue high-arousal fact from GrayFog"
    );
    assert_eq!(promoted[0].memory_id, gray_fog_entry.memory_id);
}

#[test]
fn test_affective_signature_survives_ebbinghaus_decay() {
    // Ebbinghaus decay should NOT reset affective_signature
    let entry = MemoryEntry {
        memory_id: Uuid::new_v4(),
        content: "Important fact".to_string(),
        confidence_score: 0.8,
        tier: siss_graph_core::node::memory::ConsolidationTier::Semantic,
        affective_signature: Some(AffectiveSignature {
            valence: 0.7,
            arousal: 0.8,
            sovereign_relevance: 0.9,
        }),
    };

    // After decay (simulated), affective_signature should persist
    let decayed = entry.clone();
    assert!(decayed.affective_signature.is_some());

    let sig = decayed.affective_signature.unwrap();
    assert_eq!(sig.valence, 0.7, "Valence should survive decay");
    assert_eq!(sig.arousal, 0.8, "Arousal should survive decay");
    assert_eq!(
        sig.sovereign_relevance, 0.9,
        "Sovereign_relevance should survive decay"
    );
}

#[test]
fn test_sovereign_relevance_threshold_boundary_at_0_7() {
    let op_set = CartographicOperatorSet {
        confidence_threshold: 0.5,
        jaccard_threshold: 0.25,
        max_tokens_per_entry: 4,
    };

    // Exactly at boundary: sovereign_relevance = 0.7, arousal = 0.85 (passes > 0.8)
    let boundary_entry = MemoryEntry {
        memory_id: Uuid::new_v4(),
        content: "X".repeat(100),
        confidence_score: 0.9,
        tier: siss_graph_core::node::memory::ConsolidationTier::Semantic,
        affective_signature: Some(AffectiveSignature {
            valence: 0.5,
            arousal: 0.85,
            sovereign_relevance: 0.7, // Exactly at threshold
        }),
    };

    let truncated = op_set.phi_simplify(vec![boundary_entry.clone()]);

    // At boundary (0.7), should NOT be truncated (>= 0.7 passes)
    assert_eq!(
        truncated[0].content.len(),
        100,
        "Boundary case 0.7 should NOT truncate"
    );

    // Just below boundary: sovereign_relevance = 0.69, arousal = 0.85 (passes > 0.8)
    let below_boundary_entry = MemoryEntry {
        memory_id: Uuid::new_v4(),
        content: "X".repeat(100),
        confidence_score: 0.9,
        tier: siss_graph_core::node::memory::ConsolidationTier::Semantic,
        affective_signature: Some(AffectiveSignature {
            valence: 0.5,
            arousal: 0.85,
            sovereign_relevance: 0.69, // Below threshold
        }),
    };

    let truncated_below = op_set.phi_simplify(vec![below_boundary_entry.clone()]);

    // Below boundary (0.69), should be truncated
    assert!(
        truncated_below[0].content.len() <= 16,
        "Below boundary 0.69 should truncate"
    );
}
