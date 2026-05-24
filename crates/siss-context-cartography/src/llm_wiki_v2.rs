use chrono::{DateTime, Utc, Duration};
use serde::{Serialize, Deserialize};
use std::collections::HashMap;
use uuid::Uuid;
use sha2::{Sha256, Digest};

/// Phase 80: LLM Wiki v2 Crystallization
/// Four-tier memory consolidation with Ebbinghaus decay, cryptographic supersession, and hybrid search.

// ====== Tier 1: Working Memory (unprocessed, volatile) ======

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct WorkingMemoryEntry {
    pub id: Uuid,
    pub fact: String,
    pub source: String,
    pub created_at: DateTime<Utc>,
    pub metadata: serde_json::Value,
}

// ====== Tier 2: Episodic Memory (session-scoped summaries) ======

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EpisodicMemory {
    pub id: Uuid,
    pub session_id: Uuid,
    pub summary: String,
    pub extracted_facts: Vec<String>,
    pub created_at: DateTime<Utc>,
    pub session_duration: Duration,
}

// ====== Tier 3: Semantic Memory (cross-session facts with Ebbinghaus decay) ======

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub enum MemoryTier {
    Working,
    Episodic,
    Semantic,
    Procedural,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SemanticFact {
    pub id: Uuid,
    pub fact: String,
    pub confidence_score: f64,  // [0.0, 1.0]
    pub created_at: DateTime<Utc>,
    pub last_accessed_at: DateTime<Utc>,
    pub access_count: u64,
    pub superseded_by: Option<Uuid>,  // Link to newer fact if contradicted
    pub is_stale: bool,
    pub sources: Vec<String>,  // Audit trail
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ProceduralMemory {
    pub id: Uuid,
    pub pattern: String,
    pub workflow: Vec<String>,
    pub success_rate: f64,
    pub created_at: DateTime<Utc>,
    pub last_executed_at: Option<DateTime<Utc>>,
}

// ====== Ebbinghaus Decay Function ======

/// Retention = initial_confidence * exp(-t / lambda)
/// where t = days since creation, lambda = 7 days (decay constant)
pub fn compute_ebbinghaus_retention(
    initial_confidence: f64,
    created_at: DateTime<Utc>,
    now: DateTime<Utc>,
) -> f64 {
    let elapsed_secs = (now - created_at).num_seconds() as f64;
    let elapsed_days = elapsed_secs / 86400.0;
    let lambda = 7.0;  // 7-day decay constant

    let retention = initial_confidence * (-elapsed_days / lambda).exp();
    retention.max(0.0).min(1.0)
}

/// Update confidence after access/reinforcement
pub fn reinforce_confidence(current_confidence: f64) -> f64 {
    (current_confidence + 0.1).min(1.0)  // Boost by 10% on access, capped at 1.0
}

/// Determine if a fact should be garbage collected (confidence < threshold)
pub fn is_gc_eligible(confidence: f64, threshold: f64) -> bool {
    confidence < threshold
}

// ====== Cryptographic Supersession ======

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SuppressionChain {
    pub old_fact_id: Uuid,
    pub new_fact_id: Uuid,
    pub contradiction_reason: String,
    pub superseded_at: DateTime<Utc>,
    pub old_fact_hash: String,
    pub new_fact_hash: String,
}

pub fn compute_fact_hash(fact: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(fact.as_bytes());
    format!("{:x}", hasher.finalize())
}

pub fn mark_fact_stale(fact: &mut SemanticFact, superseding_id: Uuid) {
    fact.is_stale = true;
    fact.superseded_by = Some(superseding_id);
}

// ====== Hybrid Search Fusion (BM25 + Vector + Graph Traversal) ======

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SearchResult {
    pub fact_id: Uuid,
    pub fact: String,
    pub bm25_score: f64,
    pub vector_similarity: f64,
    pub graph_relevance: f64,
    pub rrf_fused_score: f64,  // Reciprocal Rank Fusion
    pub confidence: f64,
}

/// BM25 keyword matching (simplified)
/// Score = log(N / df) where N = total docs, df = docs containing term
pub fn compute_bm25_score(query: &str, fact: &str, total_facts: u64) -> f64 {
    let query_lower = query.to_lowercase();
    let fact_lower = fact.to_lowercase();
    let query_terms: Vec<&str> = query_lower.split_whitespace().collect();

    let matches = query_terms.iter()
        .filter(|term| fact_lower.contains(*term))
        .count() as f64;

    if matches == 0.0 {
        return 0.0;
    }

    // Simplified BM25: log(N / df) where df ≈ 1 / matches
    let df = 1.0 / (matches + 1.0);
    ((total_facts as f64) / df).log10()
}

/// Vector similarity (cosine-like, treating facts as bag-of-words)
pub fn compute_vector_similarity(query: &str, fact: &str) -> f64 {
    let query_lower = query.to_lowercase();
    let fact_lower = fact.to_lowercase();
    let query_terms: Vec<&str> = query_lower.split_whitespace().collect();
    let fact_terms: Vec<&str> = fact_lower.split_whitespace().collect();

    let intersection = query_terms.iter()
        .filter(|t| fact_terms.contains(t))
        .count() as f64;

    let union = (query_terms.len() as f64 + fact_terms.len() as f64) - intersection;

    if union == 0.0 {
        return 0.0;
    }

    intersection / union
}

/// Graph relevance: scored by relationship to other facts
/// (placeholder: assumes well-connected facts are more relevant)
pub fn compute_graph_relevance(fact_id: Uuid, graph_connections: &HashMap<Uuid, Vec<Uuid>>) -> f64 {
    let connections = graph_connections.get(&fact_id).map(|v| v.len()).unwrap_or(0);
    (connections as f64).min(10.0) / 10.0  // Normalized to [0, 1]
}

/// Reciprocal Rank Fusion (RRF)
/// RRF(d) = sum over k methods of 1 / (60 + rank_k(d))
pub fn compute_rrf_score(bm25_rank: usize, vector_rank: usize, graph_rank: usize) -> f64 {
    let bm25_contrib = 1.0 / (60.0 + bm25_rank as f64);
    let vector_contrib = 1.0 / (60.0 + vector_rank as f64);
    let graph_contrib = 1.0 / (60.0 + graph_rank as f64);

    (bm25_contrib + vector_contrib + graph_contrib) / 3.0
}

// ====== Hybrid Search Engine ======

#[derive(Debug, Clone)]
pub struct HybridSearchEngine {
    pub facts: Vec<SemanticFact>,
    pub graph: HashMap<Uuid, Vec<Uuid>>,  // fact_id -> [related_fact_ids]
}

impl HybridSearchEngine {
    pub fn new() -> Self {
        Self {
            facts: Vec::new(),
            graph: HashMap::new(),
        }
    }

    pub fn add_fact(&mut self, fact: SemanticFact, related_facts: Vec<Uuid>) {
        self.graph.insert(fact.id, related_facts);
        self.facts.push(fact);
    }

    pub fn search(&self, query: &str, top_k: usize) -> Vec<SearchResult> {
        let mut results: Vec<SearchResult> = Vec::new();

        let total_facts = self.facts.len() as u64;

        // Compute scores for all facts
        for fact in self.facts.iter() {
            if fact.is_stale {
                continue;  // Skip stale facts
            }

            let bm25 = compute_bm25_score(query, &fact.fact, total_facts);
            let vector = compute_vector_similarity(query, &fact.fact);
            let graph = compute_graph_relevance(fact.id, &self.graph);

            // Compute RRF (rank-based fusion)
            // Lower rank = higher relevance; convert scores to ranks
            let bm25_rank = ((1.0 - bm25) * 100.0) as usize;
            let vector_rank = ((1.0 - vector) * 100.0) as usize;
            let graph_rank = ((1.0 - graph) * 100.0) as usize;

            let rrf = compute_rrf_score(bm25_rank, vector_rank, graph_rank);

            // Final score = RRF fused with current confidence (Ebbinghaus-decayed)
            let decayed_confidence = compute_ebbinghaus_retention(
                fact.confidence_score,
                fact.created_at,
                Utc::now(),
            );

            results.push(SearchResult {
                fact_id: fact.id,
                fact: fact.fact.clone(),
                bm25_score: bm25,
                vector_similarity: vector,
                graph_relevance: graph,
                rrf_fused_score: rrf,
                confidence: decayed_confidence,
            });
        }

        // Sort by RRF-fused score and return top-k
        results.sort_by(|a, b| b.rrf_fused_score.partial_cmp(&a.rrf_fused_score).unwrap());
        results.into_iter().take(top_k).collect()
    }

    pub fn supersede_fact(
        &mut self,
        old_fact_id: Uuid,
        new_fact: SemanticFact,
        reason: String,
    ) -> Result<SuppressionChain, String> {
        // Compute hashes first
        let old_fact_text = self.facts.iter()
            .find(|f| f.id == old_fact_id)
            .map(|f| f.fact.clone())
            .ok_or_else(|| format!("Fact not found: {}", old_fact_id))?;

        let old_hash = compute_fact_hash(&old_fact_text);
        let new_hash = compute_fact_hash(&new_fact.fact);
        let new_fact_id = new_fact.id;

        // Find and mark old fact as stale
        if let Some(old_fact) = self.facts.iter_mut().find(|f| f.id == old_fact_id) {
            mark_fact_stale(old_fact, new_fact_id);
        }

        // Add new fact
        self.add_fact(new_fact, Vec::new());

        Ok(SuppressionChain {
            old_fact_id,
            new_fact_id,
            contradiction_reason: reason,
            superseded_at: Utc::now(),
            old_fact_hash: old_hash,
            new_fact_hash: new_hash,
        })
    }

    pub fn garbage_collect(&mut self, confidence_threshold: f64) {
        self.facts.retain(|f| !is_gc_eligible(f.confidence_score, confidence_threshold));
    }

    pub fn reinforce_fact(&mut self, fact_id: Uuid) -> Result<(), String> {
        if let Some(fact) = self.facts.iter_mut().find(|f| f.id == fact_id) {
            fact.confidence_score = reinforce_confidence(fact.confidence_score);
            fact.last_accessed_at = Utc::now();
            fact.access_count += 1;
            Ok(())
        } else {
            Err(format!("Fact not found: {}", fact_id))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ebbinghaus_decay_reduces_confidence_over_time() {
        let now = Utc::now();
        let one_week_ago = now - Duration::days(7);
        let one_month_ago = now - Duration::days(30);

        let initial = 1.0;
        let after_1w = compute_ebbinghaus_retention(initial, one_week_ago, now);
        let after_1m = compute_ebbinghaus_retention(initial, one_month_ago, now);

        assert!(after_1w < initial);
        assert!(after_1m < after_1w);
        assert!(after_1w > 0.3);  // After 7 days at lambda=7, retention ≈ 37%
    }

    #[test]
    fn test_bm25_score_matches_relevant_queries() {
        let query = "cryptographic signature";
        let relevant_fact = "Ed25519 cryptographic signature verification";
        let irrelevant_fact = "agent discovery protocol";

        let relevant_score = compute_bm25_score(query, relevant_fact, 100);
        let irrelevant_score = compute_bm25_score(query, irrelevant_fact, 100);

        assert!(relevant_score > irrelevant_score);
    }

    #[test]
    fn test_vector_similarity_jaccard_distance() {
        let query = "consensus quorum voting";
        let similar = "quorum consensus voting agreement";
        let dissimilar = "heartbeat monitoring latency";

        let similar_score = compute_vector_similarity(query, similar);
        let dissimilar_score = compute_vector_similarity(query, dissimilar);

        assert!(similar_score > dissimilar_score);
    }

    #[test]
    fn test_rrf_fuses_three_ranking_streams() {
        let bm25_rank = 1;  // Top result
        let vector_rank = 3;
        let graph_rank = 5;

        let rrf = compute_rrf_score(bm25_rank, vector_rank, graph_rank);

        assert!(rrf > 0.0);
        assert!(rrf < 0.1);  // RRF scores are small
    }

    #[test]
    fn test_supersession_marks_old_fact_stale() {
        let mut engine = HybridSearchEngine::new();

        let old_id = Uuid::new_v4();
        let old_fact = SemanticFact {
            id: old_id,
            fact: "old consensus protocol".to_string(),
            confidence_score: 0.9,
            created_at: Utc::now(),
            last_accessed_at: Utc::now(),
            access_count: 5,
            superseded_by: None,
            is_stale: false,
            sources: vec!["phase-73".to_string()],
        };

        engine.add_fact(old_fact, Vec::new());

        let new_id = Uuid::new_v4();
        let new_fact = SemanticFact {
            id: new_id,
            fact: "new BFT consensus protocol".to_string(),
            confidence_score: 0.95,
            created_at: Utc::now(),
            last_accessed_at: Utc::now(),
            access_count: 0,
            superseded_by: None,
            is_stale: false,
            sources: vec!["phase-75".to_string()],
        };

        let result = engine.supersede_fact(old_id, new_fact, "BFT provides better guarantees".to_string());
        assert!(result.is_ok());

        let old = engine.facts.iter().find(|f| f.id == old_id).unwrap();
        assert!(old.is_stale);
        assert_eq!(old.superseded_by, Some(new_id));
    }

    #[test]
    fn test_hybrid_search_returns_stale_facts_filtered() {
        let mut engine = HybridSearchEngine::new();

        let fact1_id = Uuid::new_v4();
        let mut fact1 = SemanticFact {
            id: fact1_id,
            fact: "distributed consensus protocol".to_string(),
            confidence_score: 0.8,
            created_at: Utc::now(),
            last_accessed_at: Utc::now(),
            access_count: 3,
            superseded_by: None,
            is_stale: false,
            sources: vec!["wiki".to_string()],
        };

        let fact2_id = Uuid::new_v4();
        let fact2 = SemanticFact {
            id: fact2_id,
            fact: "old_protocol obsolete".to_string(),
            confidence_score: 0.2,
            created_at: Utc::now(),
            last_accessed_at: Utc::now(),
            access_count: 0,
            superseded_by: None,
            is_stale: true,  // Stale
            sources: vec!["archive".to_string()],
        };

        fact1.superseded_by = Some(fact2_id);

        engine.add_fact(fact1, Vec::new());
        engine.add_fact(fact2, Vec::new());

        let results = engine.search("consensus protocol", 10);

        // Stale facts should be filtered out
        assert!(!results.iter().any(|r| r.fact_id == fact2_id));
    }
}
