use chrono::{DateTime, Utc};
use uuid::Uuid;
use crate::llm_wiki_v2::SemanticFact;

#[derive(Clone, Debug)]
pub enum SourceType {
    Human,
    LLM,
    API,
    Document,
}

#[derive(Clone, Debug)]
pub struct ConfidenceSource {
    pub fact_id: Uuid,
    pub source_type: SourceType,
    pub source_url: String,
    pub timestamp: DateTime<Utc>,
}

pub fn compute_source_weight(source_type: SourceType) -> f64 {
    match source_type {
        SourceType::Human => 0.95,
        SourceType::LLM => 0.70,
        SourceType::API => 0.60,
        SourceType::Document => 0.75,
    }
}

pub fn compute_corroboration_boost(source_count: usize) -> f64 {
    if source_count <= 1 {
        0.0
    } else {
        let boost_per_source = 0.05;
        (boost_per_source * (source_count - 1) as f64).min(0.15)
    }
}

pub fn detect_contradiction(new_fact: &str, existing_facts: &[SemanticFact]) -> Option<Uuid> {
    for existing in existing_facts {
        if existing.is_stale {
            continue;
        }

        let similarity = semantic_similarity(&new_fact, &existing.fact);
        if similarity > 0.85 && contradicts(new_fact, &existing.fact) {
            return Some(existing.id);
        }
    }
    None
}

pub fn calculate_confidence(
    sources: &[ConfidenceSource],
    existing_facts: &[SemanticFact],
) -> (f64, Option<Uuid>) {
    if sources.is_empty() {
        return (0.0, None);
    }

    let base_confidence = sources.iter()
        .map(|s| compute_source_weight(s.source_type.clone()))
        .sum::<f64>() / sources.len() as f64;

    let corroboration_boost = compute_corroboration_boost(sources.len());
    let mut confidence = (base_confidence + corroboration_boost).min(1.0);

    // Apply Ebbinghaus decay based on first source timestamp
    let earliest_timestamp = sources.iter()
        .map(|s| s.timestamp)
        .min()
        .unwrap_or_else(Utc::now);

    let elapsed_secs = (Utc::now() - earliest_timestamp).num_seconds() as f64;
    let elapsed_days = elapsed_secs / 86400.0;
    let lambda = 7.0;
    confidence = confidence * (-elapsed_days / lambda).exp();
    confidence = confidence.max(0.0).min(1.0);

    let contradiction = None; // Placeholder: will detect when integrated with knowledge base

    (confidence, contradiction)
}

// Helper: semantic similarity (bag-of-words Jaccard)
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

// Helper: contradiction detection (simple negation check)
fn contradicts(fact1: &str, fact2: &str) -> bool {
    let f1_lower = fact1.to_lowercase();
    let f2_lower = fact2.to_lowercase();

    // Simple heuristic: if one has "not" and other doesn't, they contradict
    let f1_has_not = f1_lower.contains("not");
    let f2_has_not = f2_lower.contains("not");

    if f1_has_not != f2_has_not {
        return true;
    }

    false
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_semantic_similarity() {
        let fact1 = "The sky is blue and cloudless";
        let fact2 = "The sky is blue";
        let sim = semantic_similarity(fact1, fact2);
        assert!(sim > 0.5, "Similar facts should have high similarity");
    }
}
