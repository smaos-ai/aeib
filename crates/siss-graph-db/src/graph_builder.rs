use uuid::Uuid;
use std::collections::{HashMap, VecDeque};
use siss_context_cartography::llm_wiki_v2::SemanticFact;

#[derive(Clone, Debug, PartialEq)]
pub enum RelationType {
    SemanticSimilar,
    Contradicts,
    Supports,
    Related,
}

#[derive(Clone, Debug)]
pub struct GraphRelationship {
    pub source_id: Uuid,
    pub target_id: Uuid,
    pub relationship_type: RelationType,
    pub score: f64,
}

#[derive(Clone, Debug)]
pub struct GraphBuilder {
    pub relationships: Vec<GraphRelationship>,
    pub graph: HashMap<Uuid, Vec<(Uuid, f64)>>,
}

impl GraphBuilder {
    pub fn new() -> Self {
        Self {
            relationships: Vec::new(),
            graph: HashMap::new(),
        }
    }
}

pub fn extract_relationships(facts: &[SemanticFact]) -> Vec<GraphRelationship> {
    let mut relationships = Vec::new();

    for i in 0..facts.len() {
        for j in (i + 1)..facts.len() {
            let similarity = semantic_similarity(&facts[i].fact, &facts[j].fact);

            if similarity > 0.80 {
                let rel_type = determine_relationship_type(&facts[i].fact, &facts[j].fact);
                let type_weight = match rel_type {
                    RelationType::SemanticSimilar => 1.0,
                    RelationType::Contradicts => 0.8,
                    RelationType::Supports => 0.9,
                    RelationType::Related => 0.6,
                };
                let score = similarity * type_weight;

                relationships.push(GraphRelationship {
                    source_id: facts[i].id,
                    target_id: facts[j].id,
                    relationship_type: rel_type,
                    score: score.min(1.0).max(0.0),
                });
            }
        }
    }

    relationships
}

pub fn determine_relationship_type(fact_a: &str, fact_b: &str) -> RelationType {
    let a_lower = fact_a.to_lowercase();
    let b_lower = fact_b.to_lowercase();

    // Contradiction check
    let a_has_not = a_lower.contains("not");
    let b_has_not = b_lower.contains("not");
    if a_has_not != b_has_not && semantic_similarity(fact_a, fact_b) > 0.70 {
        return RelationType::Contradicts;
    }

    // Support check (keywords like "also", "support", "confirm")
    if b_lower.contains("also") || b_lower.contains("support") || b_lower.contains("confirm") {
        return RelationType::Supports;
    }

    // Default to semantic similarity
    RelationType::SemanticSimilar
}

pub fn build_graph(relationships: Vec<GraphRelationship>) -> HashMap<Uuid, Vec<(Uuid, f64)>> {
    let mut graph: HashMap<Uuid, Vec<(Uuid, f64)>> = HashMap::new();

    for rel in relationships {
        // Insert forward direction
        graph.entry(rel.source_id)
            .or_insert_with(Vec::new)
            .push((rel.target_id, rel.score));

        // Insert backward direction (bidirectional)
        graph.entry(rel.target_id)
            .or_insert_with(Vec::new)
            .push((rel.source_id, rel.score));
    }

    graph
}

pub fn traverse_graph(
    root_id: Uuid,
    graph: &HashMap<Uuid, Vec<(Uuid, f64)>>,
    max_depth: usize,
) -> Vec<(Uuid, f64)> {
    let mut results = Vec::new();
    let mut visited = std::collections::HashSet::new();
    let mut queue = VecDeque::new();

    visited.insert(root_id);
    queue.push_back((root_id, 1.0, 0));

    while let Some((current_id, relevance, depth)) = queue.pop_front() {
        if depth > max_depth {
            continue;
        }

        if let Some(neighbors) = graph.get(&current_id) {
            for (neighbor_id, edge_score) in neighbors {
                if !visited.contains(neighbor_id) {
                    let new_relevance = relevance * edge_score;

                    if new_relevance > 0.1 {
                        results.push((*neighbor_id, new_relevance));
                        visited.insert(*neighbor_id);
                        queue.push_back((*neighbor_id, new_relevance, depth + 1));
                    }
                }
            }
        }
    }

    // Sort by relevance descending
    results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
    results
}

// Helper: semantic similarity
fn semantic_similarity(fact1: &str, fact2: &str) -> f64 {
    let words1: std::collections::HashSet<&str> = fact1.split_whitespace().collect();
    let words2: std::collections::HashSet<&str> = fact2.split_whitespace().collect();

    let intersection = words1.intersection(&words2).count() as f64;
    let union = words1.union(&words2).count() as f64;

    if union == 0.0 {
        0.0
    } else {
        intersection / union
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_semantic_similarity_basic() {
        let sim = semantic_similarity("hello world", "hello world");
        assert_eq!(sim, 1.0, "Identical strings should have similarity 1.0");

        let sim2 = semantic_similarity("hello world", "goodbye");
        assert!(sim2 < 0.5, "Different strings should have lower similarity");
    }
}
