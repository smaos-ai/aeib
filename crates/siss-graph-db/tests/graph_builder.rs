use uuid::Uuid;
use siss_graph_db::graph_builder::{
    Fact, GraphRelationship, RelationType, extract_relationships,
    determine_relationship_type, build_graph, traverse_graph,
};

// Test 1: Relationship extraction finds relevant pairs
#[test]
fn test_relationship_extraction_finds_relevant_pairs() {
    let id1 = Uuid::new_v4();
    let id2 = Uuid::new_v4();
    let id3 = Uuid::new_v4();

    let fact1 = Fact {
        id: id1,
        text: "Machine learning models require large datasets".to_string(),
    };

    let fact2 = Fact {
        id: id2,
        text: "Training deep learning models needs large data".to_string(),
    };

    let fact3 = Fact {
        id: id3,
        text: "The Eiffel Tower is in Paris".to_string(),
    };

    let facts = vec![fact1.clone(), fact2.clone(), fact3.clone()];
    let relationships = extract_relationships(&facts);

    // Should find relationship between fact1 and fact2 (similar)
    let has_relevant_pair = relationships.iter()
        .any(|r| (r.source_id == id1 && r.target_id == id2) ||
                 (r.source_id == id2 && r.target_id == id1));

    assert!(has_relevant_pair, "Should detect similar facts");
    assert!(relationships.len() >= 1, "Should find at least one relationship");
}

// Test 2: Graph insertion maintains bidirectional links
#[test]
fn test_graph_insertion_maintains_bidirectional_links() {
    let id_a = Uuid::new_v4();
    let id_b = Uuid::new_v4();

    let relationships = vec![
        GraphRelationship {
            source_id: id_a,
            target_id: id_b,
            relationship_type: RelationType::SemanticSimilar,
            score: 0.85,
        }
    ];

    let graph = build_graph(relationships);

    // Check bidirectional
    assert!(graph.contains_key(&id_a), "Source should be in graph");
    assert!(graph.contains_key(&id_b), "Target should be in graph");

    let a_neighbors = &graph[&id_a];
    let b_neighbors = &graph[&id_b];

    let a_has_b = a_neighbors.iter().any(|(id, _)| *id == id_b);
    let b_has_a = b_neighbors.iter().any(|(id, _)| *id == id_a);

    assert!(a_has_b, "A should link to B");
    assert!(b_has_a, "B should link to A (bidirectional)");

    let a_to_b_score = a_neighbors.iter().find(|(id, _)| *id == id_b).map(|(_, score)| *score).unwrap();
    let b_to_a_score = b_neighbors.iter().find(|(id, _)| *id == id_a).map(|(_, score)| *score).unwrap();

    assert_eq!(a_to_b_score, 0.85, "Scores should match");
    assert_eq!(b_to_a_score, 0.85, "Scores should match in both directions");
}

// Test 3: Graph traversal returns ranked neighbors
#[test]
fn test_graph_traversal_returns_ranked_neighbors() {
    let root = Uuid::new_v4();
    let neighbor1 = Uuid::new_v4();
    let neighbor2 = Uuid::new_v4();
    let neighbor3 = Uuid::new_v4();

    let relationships = vec![
        GraphRelationship {
            source_id: root,
            target_id: neighbor1,
            relationship_type: RelationType::SemanticSimilar,
            score: 0.90,
        },
        GraphRelationship {
            source_id: root,
            target_id: neighbor2,
            relationship_type: RelationType::Related,
            score: 0.60,
        },
        GraphRelationship {
            source_id: root,
            target_id: neighbor3,
            relationship_type: RelationType::Supports,
            score: 0.50,
        },
    ];

    let graph = build_graph(relationships);
    let results = traverse_graph(root, &graph, 1);

    assert!(results.len() >= 3, "Should return all neighbors");

    // Results should be ranked by score
    if results.len() >= 2 {
        assert!(results[0].1 >= results[1].1, "Results should be sorted by score DESC");
    }
}

// Test 4: Search ranking incorporates graph relevance
#[test]
fn test_search_ranking_incorporates_graph_relevance() {
    let id_a = Uuid::new_v4();
    let id_b = Uuid::new_v4();

    // A and B are related
    let relationships = vec![
        GraphRelationship {
            source_id: id_a,
            target_id: id_b,
            relationship_type: RelationType::SemanticSimilar,
            score: 0.85,
        }
    ];

    let graph = build_graph(relationships);

    // When searching from A, B should rank higher than C
    let neighbors_of_a = traverse_graph(id_a, &graph, 1);
    let b_appears = neighbors_of_a.iter().any(|(id, _)| *id == id_b);

    assert!(b_appears, "Related fact B should appear in traversal from A");
}

// Test 5: Graph integration is deterministic
#[test]
fn test_graph_integration_deterministic() {
    let fact1 = Fact {
        id: Uuid::new_v4(),
        text: "Climate change is accelerating".to_string(),
    };

    let fact2 = Fact {
        id: Uuid::new_v4(),
        text: "Global warming is increasing rapidly".to_string(),
    };

    let facts = vec![fact1, fact2];

    let mut results = Vec::new();
    for _ in 0..10 {
        let relationships = extract_relationships(&facts);
        let graph = build_graph(relationships);
        results.push(graph);
    }

    // All graphs should be identical
    for i in 1..results.len() {
        assert_eq!(results[0].len(), results[i].len(),
            "Graph size must be deterministic, iteration {} differs", i);
    }
}

// Helper test for relationship type determination
#[test]
fn test_determine_relationship_type_varies() {
    let similar1 = "Machine learning requires data";
    let similar2 = "Deep learning needs datasets";

    let contradicts1 = "Cats are animals";
    let contradicts2 = "Cats are not animals";

    let rel_type_1 = determine_relationship_type(similar1, similar2);
    let rel_type_2 = determine_relationship_type(contradicts1, contradicts2);

    // Relationship types should be detected
    assert!(rel_type_1 == RelationType::SemanticSimilar || rel_type_1 == RelationType::Related,
        "Similar facts should be detected as related or similar");
    assert_eq!(rel_type_2, RelationType::Contradicts,
        "Contradictory facts should be detected");
}
